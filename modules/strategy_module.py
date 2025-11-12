"""Strategy module for trading signal generation.

This module implements:
- Swing level calculations (support/resistance)
- Technical indicators
- Entry/exit signal generation
- Risk management integration
- Strategy backtesting capabilities

Currently implements swing trading strategies.
"""
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple, Callable
from datetime import datetime, timedelta
from enum import Enum

from config import config
from modules.data_module import get_data_manager
from modules.logging_config import logger


class SignalType(Enum):
    """Trading signal types."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    EXIT_LONG = "EXIT_LONG"
    EXIT_SHORT = "EXIT_SHORT"


class Signal:
    """Trading signal container."""

    def __init__(self, symbol: str, signal_type: SignalType, price: float,
                 timestamp: datetime = None, confidence: float = 1.0,
                 metadata: Dict[str, Any] = None):
        """Initialize trading signal.

        Args:
            symbol: Trading symbol
            signal_type: Type of signal
            price: Signal price
            timestamp: Signal timestamp
            confidence: Signal confidence (0-1)
            metadata: Additional signal data
        """
        self.symbol = symbol
        self.signal_type = signal_type
        self.price = price
        self.timestamp = timestamp or datetime.now()
        self.confidence = confidence
        self.metadata = metadata or {}

    def __str__(self) -> str:
        return f"{self.signal_type.value} {self.symbol} @ {self.price:.2f} ({self.confidence:.2f})"


class SwingStrategy:
    """Swing trading strategy implementation."""

    def __init__(self, symbol: str, lookback_period: int = 20):
        """Initialize swing strategy.

        Args:
            symbol: Trading symbol
            lookback_period: Period for swing calculations
        """
        self.symbol = symbol
        self.lookback_period = lookback_period
        self.data_manager = get_data_manager()
        self.logger = logger

        # Strategy parameters
        self.swing_threshold = 0.005  # 0.5% swing threshold
        self.min_swing_points = 3
        self.risk_reward_ratio = 2.0

        # State tracking
        self.current_position = None  # 'long', 'short', or None
        self.entry_price = None
        self.stop_loss = None
        self.take_profit = None
        self.swing_levels = []

    def calculate_swing_levels(self, data: pd.DataFrame) -> Dict[str, List[float]]:
        """Calculate swing support and resistance levels.

        Args:
            data: Historical price data

        Returns:
            dict: Support and resistance levels
        """
        try:
            if data is None or data.empty:
                return {'support': [], 'resistance': []}

            # Use close prices for swing calculation
            prices = data['close'].values
            highs = data['high'].values
            lows = data['low'].values

            # Find local minima (support) and maxima (resistance)
            support_levels = []
            resistance_levels = []

            for i in range(self.min_swing_points, len(prices) - self.min_swing_points):
                # Check for local minimum (support)
                if all(lows[i] <= lows[i-j] for j in range(1, self.min_swing_points + 1)) and \
                   all(lows[i] <= lows[i+j] for j in range(1, self.min_swing_points + 1)):
                    support_levels.append(lows[i])

                # Check for local maximum (resistance)
                if all(highs[i] >= highs[i-j] for j in range(1, self.min_swing_points + 1)) and \
                   all(highs[i] >= highs[i+j] for j in range(1, self.min_swing_points + 1)):
                    resistance_levels.append(highs[i])

            # Remove duplicates and sort
            support_levels = sorted(list(set(support_levels)))
            resistance_levels = sorted(list(set(resistance_levels)))

            # Filter levels within recent range
            recent_high = highs[-self.lookback_period:].max()
            recent_low = lows[-self.lookback_period:].min()

            support_levels = [level for level in support_levels if recent_low <= level <= recent_high]
            resistance_levels = [level for level in resistance_levels if recent_low <= level <= recent_high]

            self.swing_levels = {
                'support': support_levels[-5:],  # Keep last 5 levels
                'resistance': resistance_levels[-5:]
            }

            return self.swing_levels

        except Exception as e:
            self.logger.error(f"❌ Error calculating swing levels: {str(e)}")
            return {'support': [], 'resistance': []}

    def generate_signals(self, data: pd.DataFrame) -> List[Signal]:
        """Generate trading signals based on swing levels.

        Args:
            data: Historical price data

        Returns:
            list: List of trading signals
        """
        signals = []

        try:
            if data is None or data.empty or len(data) < self.lookback_period:
                return signals

            current_price = data['close'].iloc[-1]
            prev_price = data['close'].iloc[-2] if len(data) > 1 else current_price

            # Calculate swing levels
            swing_levels = self.calculate_swing_levels(data)

            # Get nearest support and resistance
            nearest_support = self._get_nearest_level(current_price, swing_levels['support'], 'below')
            nearest_resistance = self._get_nearest_level(current_price, swing_levels['resistance'], 'above')

            # Generate signals based on swing levels
            signal = self._analyze_swing_signals(
                current_price, prev_price, nearest_support, nearest_resistance
            )

            if signal:
                signals.append(signal)

            # Check for exit signals
            if self.current_position:
                exit_signal = self._check_exit_conditions(current_price, data)
                if exit_signal:
                    signals.append(exit_signal)

        except Exception as e:
            self.logger.error(f"❌ Error generating signals: {str(e)}")

        return signals

    def _get_nearest_level(self, price: float, levels: List[float], direction: str) -> Optional[float]:
        """Get nearest level in specified direction.

        Args:
            price: Current price
            levels: List of levels
            direction: 'above' or 'below'

        Returns:
            float: Nearest level or None
        """
        if not levels:
            return None

        if direction == 'below':
            candidates = [level for level in levels if level < price]
            return max(candidates) if candidates else None
        else:  # above
            candidates = [level for level in levels if level > price]
            return min(candidates) if candidates else None

    def _analyze_swing_signals(self, current_price: float, prev_price: float,
                             support: Optional[float], resistance: Optional[float]) -> Optional[Signal]:
        """Analyze price action for swing signals.

        Args:
            current_price: Current price
            prev_price: Previous price
            support: Nearest support level
            resistance: Nearest resistance level

        Returns:
            Signal: Trading signal or None
        """
        try:
            # Calculate price change
            price_change = (current_price - prev_price) / prev_price

            # Bullish signal: Break above resistance or bounce off support
            if support and current_price > support * (1 + self.swing_threshold):
                if not self.current_position or self.current_position == 'short':
                    stop_loss = support * 0.98  # 2% below support
                    take_profit = current_price * (1 + (self.risk_reward_ratio * abs(current_price - stop_loss) / current_price))

                    return Signal(
                        symbol=self.symbol,
                        signal_type=SignalType.BUY,
                        price=current_price,
                        confidence=0.7,
                        metadata={
                            'support_level': support,
                            'stop_loss': stop_loss,
                            'take_profit': take_profit,
                            'strategy': 'swing_bounce'
                        }
                    )

            # Bearish signal: Break below support or rejection at resistance
            elif resistance and current_price < resistance * (1 - self.swing_threshold):
                if not self.current_position or self.current_position == 'long':
                    stop_loss = resistance * 1.02  # 2% above resistance
                    take_profit = current_price * (1 - (self.risk_reward_ratio * abs(current_price - stop_loss) / current_price))

                    return Signal(
                        symbol=self.symbol,
                        signal_type=SignalType.SELL,
                        price=current_price,
                        confidence=0.7,
                        metadata={
                            'resistance_level': resistance,
                            'stop_loss': stop_loss,
                            'take_profit': take_profit,
                            'strategy': 'swing_rejection'
                        }
                    )

            return None

        except Exception as e:
            self.logger.error(f"❌ Error analyzing swing signals: {str(e)}")
            return None

    def _check_exit_conditions(self, current_price: float, data: pd.DataFrame) -> Optional[Signal]:
        """Check for position exit conditions.

        Args:
            current_price: Current price
            data: Price data

        Returns:
            Signal: Exit signal or None
        """
        if not self.current_position or not self.entry_price:
            return None

        try:
            # Stop loss hit
            if self.current_position == 'long' and current_price <= self.stop_loss:
                return Signal(
                    symbol=self.symbol,
                    signal_type=SignalType.EXIT_LONG,
                    price=current_price,
                    confidence=1.0,
                    metadata={'reason': 'stop_loss_hit', 'entry_price': self.entry_price}
                )
            elif self.current_position == 'short' and current_price >= self.stop_loss:
                return Signal(
                    symbol=self.symbol,
                    signal_type=SignalType.EXIT_SHORT,
                    price=current_price,
                    confidence=1.0,
                    metadata={'reason': 'stop_loss_hit', 'entry_price': self.entry_price}
                )

            # Take profit hit
            if self.current_position == 'long' and current_price >= self.take_profit:
                return Signal(
                    symbol=self.symbol,
                    signal_type=SignalType.EXIT_LONG,
                    price=current_price,
                    confidence=1.0,
                    metadata={'reason': 'take_profit_hit', 'entry_price': self.entry_price}
                )
            elif self.current_position == 'short' and current_price <= self.take_profit:
                return Signal(
                    symbol=self.symbol,
                    signal_type=SignalType.EXIT_SHORT,
                    price=current_price,
                    confidence=1.0,
                    metadata={'reason': 'take_profit_hit', 'entry_price': self.entry_price}
                )

            # Time-based exit (if position held too long)
            # Additional exit conditions can be added here

            return None

        except Exception as e:
            self.logger.error(f"❌ Error checking exit conditions: {str(e)}")
            return None

    def update_position(self, signal: Signal):
        """Update position based on signal.

        Args:
            signal: Trading signal
        """
        try:
            if signal.signal_type == SignalType.BUY:
                self.current_position = 'long'
                self.entry_price = signal.price
                self.stop_loss = signal.metadata.get('stop_loss')
                self.take_profit = signal.metadata.get('take_profit')
                self.logger.info(f"📈 Entered LONG position for {self.symbol} at {signal.price:.2f}")

            elif signal.signal_type == SignalType.SELL:
                self.current_position = 'short'
                self.entry_price = signal.price
                self.stop_loss = signal.metadata.get('stop_loss')
                self.take_profit = signal.metadata.get('take_profit')
                self.logger.info(f"📉 Entered SHORT position for {self.symbol} at {signal.price:.2f}")

            elif signal.signal_type in [SignalType.EXIT_LONG, SignalType.EXIT_SHORT]:
                old_position = self.current_position
                self.current_position = None
                self.entry_price = None
                self.stop_loss = None
                self.take_profit = None
                self.logger.info(f"🔄 Exited {old_position.upper()} position for {self.symbol} at {signal.price:.2f}")

        except Exception as e:
            self.logger.error(f"❌ Error updating position: {str(e)}")

    def get_position_info(self) -> Dict[str, Any]:
        """Get current position information.

        Returns:
            dict: Position details
        """
        return {
            'symbol': self.symbol,
            'position': self.current_position,
            'entry_price': self.entry_price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'swing_levels': self.swing_levels
        }


class StrategyManager:
    """Manages multiple trading strategies."""

    def __init__(self):
        """Initialize strategy manager."""
        self.strategies = {}  # symbol -> strategy
        self.logger = logger
        self.data_manager = get_data_manager()

        # Set up data callbacks
        self.data_manager.add_data_callback(self._on_data_update)

    def add_strategy(self, symbol: str, strategy_class=SwingStrategy, **kwargs):
        """Add a strategy for a symbol.

        Args:
            symbol: Trading symbol
            strategy_class: Strategy class to instantiate
            **kwargs: Strategy parameters
        """
        try:
            if symbol in self.strategies:
                self.logger.warning(f"⚠️  Strategy for {symbol} already exists, replacing")

            strategy = strategy_class(symbol, **kwargs)
            self.strategies[symbol] = strategy

            # Subscribe to data for this symbol
            self.data_manager.subscribe_symbol(symbol)

            self.logger.info(f"✅ Added {strategy_class.__name__} strategy for {symbol}")

        except Exception as e:
            self.logger.error(f"❌ Error adding strategy for {symbol}: {str(e)}")

    def remove_strategy(self, symbol: str):
        """Remove strategy for a symbol.

        Args:
            symbol: Trading symbol
        """
        if symbol in self.strategies:
            del self.strategies[symbol]
            self.data_manager.unsubscribe_symbol(symbol)
            self.logger.info(f"✅ Removed strategy for {symbol}")

    def generate_signals(self, symbol: str = None) -> Dict[str, List[Signal]]:
        """Generate signals for strategies.

        Args:
            symbol: Specific symbol or None for all

        Returns:
            dict: Symbol to signals mapping
        """
        signals = {}

        try:
            symbols = [symbol] if symbol else list(self.strategies.keys())

            for sym in symbols:
                if sym not in self.strategies:
                    continue

                strategy = self.strategies[sym]

                # Get historical data for signal generation
                end_date = datetime.now().strftime('%Y-%m-%d')
                start_date = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')

                data = self.data_manager.get_historical_data(sym, start_date, end_date)
                if data is not None:
                    symbol_signals = strategy.generate_signals(data)
                    if symbol_signals:
                        signals[sym] = symbol_signals

        except Exception as e:
            self.logger.error(f"❌ Error generating signals: {str(e)}")

        return signals

    def _on_data_update(self, symbol: str, data: Dict[str, Any]):
        """Handle live data updates.

        Args:
            symbol: Trading symbol
            data: Updated data
        """
        try:
            if symbol in self.strategies:
                strategy = self.strategies[symbol]

                # Create a minimal DataFrame for live data
                live_df = pd.DataFrame([{
                    'close': data.get('ltp', 0),
                    'high': data.get('ltp', 0),
                    'low': data.get('ltp', 0),
                    'open': data.get('ltp', 0),
                    'volume': data.get('volume', 0)
                }])

                # Generate signals from live data
                signals = strategy.generate_signals(live_df)

                # Process signals
                for signal in signals:
                    strategy.update_position(signal)
                    self.logger.info(f"📊 Live signal: {signal}")

        except Exception as e:
            self.logger.debug(f"⚠️  Error processing live data update for {symbol}: {str(e)}")

    def get_strategy_info(self, symbol: str = None) -> Dict[str, Any]:
        """Get strategy information.

        Args:
            symbol: Specific symbol or None for all

        Returns:
            dict: Strategy information
        """
        if symbol:
            strategy = self.strategies.get(symbol)
            return strategy.get_position_info() if strategy else {}
        else:
            return {sym: strategy.get_position_info() for sym, strategy in self.strategies.items()}


# Global strategy manager instance
strategy_manager = StrategyManager()


def get_strategy_manager() -> StrategyManager:
    """Get the global strategy manager instance.

    Returns:
        StrategyManager: The global strategy manager
    """
    return strategy_manager


def add_swing_strategy(symbol: str, **kwargs):
    """Add a swing strategy for a symbol.

    Args:
        symbol: Trading symbol
        **kwargs: Strategy parameters
    """
    strategy_manager.add_strategy(symbol, SwingStrategy, **kwargs)


def generate_signals(symbol: str = None) -> Dict[str, List[Signal]]:
    """Generate trading signals.

    Args:
        symbol: Specific symbol or None for all

    Returns:
        dict: Symbol to signals mapping
    """
    return strategy_manager.generate_signals(symbol)