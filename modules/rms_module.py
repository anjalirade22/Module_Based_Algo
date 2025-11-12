"""Risk Management System (RMS) module.

This module implements:
- Position sizing calculations
- Stop loss management
- Risk allocation and limits
- Portfolio risk monitoring
- Drawdown controls
- Risk-adjusted position sizing

Provides comprehensive risk management for trading strategies.
"""
import math
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass

from config import config
from modules.logging_config import logger


@dataclass
class Position:
    """Represents a trading position."""
    symbol: str
    side: str  # 'long' or 'short'
    quantity: int
    entry_price: float
    current_price: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    @property
    def unrealized_pnl(self) -> float:
        """Calculate unrealized P&L."""
        if self.side == 'long':
            return (self.current_price - self.entry_price) * self.quantity
        else:  # short
            return (self.entry_price - self.current_price) * self.quantity

    @property
    def unrealized_pnl_percent(self) -> float:
        """Calculate unrealized P&L percentage."""
        if self.entry_price == 0:
            return 0.0
        return (self.unrealized_pnl / (self.entry_price * self.quantity)) * 100

    @property
    def risk_amount(self) -> float:
        """Calculate risk amount (entry to stop loss)."""
        if not self.stop_loss:
            return 0.0
        if self.side == 'long':
            return (self.entry_price - self.stop_loss) * self.quantity
        else:  # short
            return (self.stop_loss - self.entry_price) * self.quantity


@dataclass
class RiskMetrics:
    """Portfolio risk metrics."""
    total_portfolio_value: float
    total_risk_amount: float
    max_drawdown: float
    daily_pnl: float
    daily_pnl_percent: float
    sharpe_ratio: Optional[float] = None
    win_rate: Optional[float] = None
    total_trades: int = 0
    winning_trades: int = 0


class RiskManager:
    """Risk management system for portfolio and position control."""

    def __init__(self):
        """Initialize risk manager."""
        self.logger = logger

        # Portfolio state
        self.positions = {}  # symbol -> Position
        self.portfolio_value = config.MAX_POSITION_SIZE  # Starting portfolio value
        self.daily_start_value = self.portfolio_value

        # Risk limits from config
        self.max_positions = config.MAX_POSITIONS
        self.max_daily_loss = config.MAX_DAILY_LOSS
        self.max_position_size = config.MAX_POSITION_SIZE
        self.position_size_percent = config.POSITION_SIZE_PERCENT
        self.stop_loss_percent = config.STOP_LOSS_PERCENT
        self.target_profit_percent = config.TARGET_PROFIT_PERCENT

        # Risk tracking
        self.daily_pnl = 0.0
        self.peak_portfolio_value = self.portfolio_value
        self.max_drawdown = 0.0
        self.trade_history = []

        # Risk controls
        self.daily_loss_limit_hit = False
        self.portfolio_stop_active = False

    def calculate_position_size(self, symbol: str, entry_price: float,
                              stop_loss: float, side: str = 'long') -> int:
        """Calculate position size based on risk management rules.

        Args:
            symbol: Trading symbol
            entry_price: Entry price
            stop_loss: Stop loss price
            side: 'long' or 'short'

        Returns:
            int: Position quantity
        """
        try:
            # Check if we can open new positions
            if len(self.positions) >= self.max_positions:
                self.logger.warning(f"⚠️  Maximum positions ({self.max_positions}) reached")
                return 0

            if self.daily_loss_limit_hit:
                self.logger.warning("⚠️  Daily loss limit hit, no new positions")
                return 0

            # Calculate risk per trade
            risk_per_trade = self.portfolio_value * self.position_size_percent

            # Calculate risk amount for this position
            if side == 'long':
                risk_amount_per_unit = entry_price - stop_loss
            else:  # short
                risk_amount_per_unit = stop_loss - entry_price

            if risk_amount_per_unit <= 0:
                self.logger.error(f"❌ Invalid stop loss for {symbol}: entry={entry_price}, stop={stop_loss}")
                return 0

            # Calculate quantity based on risk
            quantity = int(risk_per_trade / risk_amount_per_unit)

            # Apply position size limits
            max_quantity_by_value = int(self.max_position_size / entry_price)
            quantity = min(quantity, max_quantity_by_value)

            # Apply lot size constraints (for futures/options)
            if hasattr(config, 'LOT_SIZE') and symbol.upper() in config.LOT_SIZE:
                lot_size = config.LOT_SIZE[symbol.upper()]
                quantity = (quantity // lot_size) * lot_size

            # Ensure minimum quantity
            quantity = max(quantity, 1)

            # Final check against portfolio limits
            position_value = quantity * entry_price
            if position_value > self.max_position_size:
                quantity = int(self.max_position_size / entry_price)
                quantity = max(quantity, 1)

            self.logger.info(f"📊 Calculated position size for {symbol}: {quantity} units "
                           f"(risk: ₹{risk_per_trade:.2f}, position value: ₹{position_value:.2f})")

            return quantity

        except Exception as e:
            self.logger.error(f"❌ Error calculating position size for {symbol}: {str(e)}")
            return 0

    def open_position(self, symbol: str, side: str, quantity: int,
                     entry_price: float, stop_loss: Optional[float] = None) -> bool:
        """Open a new position.

        Args:
            symbol: Trading symbol
            side: 'long' or 'short'
            quantity: Position quantity
            entry_price: Entry price
            stop_loss: Stop loss price (optional)

        Returns:
            bool: True if position opened successfully
        """
        try:
            # Validate inputs
            if quantity <= 0:
                self.logger.error(f"❌ Invalid quantity for {symbol}: {quantity}")
                return False

            if symbol in self.positions:
                self.logger.warning(f"⚠️  Position already exists for {symbol}, closing first")
                self.close_position(symbol)

            # Set stop loss if not provided
            if stop_loss is None:
                if side == 'long':
                    stop_loss = entry_price * (1 - self.stop_loss_percent)
                else:  # short
                    stop_loss = entry_price * (1 + self.stop_loss_percent)

            # Set take profit
            risk_amount = abs(entry_price - stop_loss)
            if side == 'long':
                take_profit = entry_price + (risk_amount * config.TARGET_PROFIT_PERCENT / self.stop_loss_percent)
            else:  # short
                take_profit = entry_price - (risk_amount * config.TARGET_PROFIT_PERCENT / self.stop_loss_percent)

            # Create position
            position = Position(
                symbol=symbol,
                side=side,
                quantity=quantity,
                entry_price=entry_price,
                current_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit
            )

            self.positions[symbol] = position

            # Update portfolio value
            position_value = quantity * entry_price
            self.portfolio_value -= position_value  # Assume margin/cash used

            self.logger.info(f"✅ Opened {side.upper()} position: {symbol} x{quantity} @ {entry_price:.2f} "
                           f"SL: {stop_loss:.2f}, TP: {take_profit:.2f}")

            return True

        except Exception as e:
            self.logger.error(f"❌ Error opening position for {symbol}: {str(e)}")
            return False

    def close_position(self, symbol: str, exit_price: Optional[float] = None) -> bool:
        """Close an existing position.

        Args:
            symbol: Trading symbol
            exit_price: Exit price (optional, uses current price if not provided)

        Returns:
            bool: True if position closed successfully
        """
        try:
            if symbol not in self.positions:
                self.logger.warning(f"⚠️  No position found for {symbol}")
                return False

            position = self.positions[symbol]

            # Use current price if exit price not provided
            if exit_price is None:
                exit_price = position.current_price

            # Calculate P&L
            pnl = position.unrealized_pnl if exit_price == position.current_price else \
                  (exit_price - position.entry_price) * position.quantity if position.side == 'long' else \
                  (position.entry_price - exit_price) * position.quantity

            # Update portfolio value
            self.portfolio_value += (position.quantity * exit_price) + pnl

            # Record trade
            trade_record = {
                'symbol': symbol,
                'side': position.side,
                'quantity': position.quantity,
                'entry_price': position.entry_price,
                'exit_price': exit_price,
                'pnl': pnl,
                'timestamp': datetime.now()
            }
            self.trade_history.append(trade_record)

            # Update daily P&L
            self.daily_pnl += pnl

            # Remove position
            del self.positions[symbol]

            self.logger.info(f"✅ Closed {position.side.upper()} position: {symbol} "
                           f"Entry: {position.entry_price:.2f}, Exit: {exit_price:.2f}, "
                           f"P&L: ₹{pnl:.2f} ({pnl/(position.entry_price * position.quantity)*100:.2f}%)")

            return True

        except Exception as e:
            self.logger.error(f"❌ Error closing position for {symbol}: {str(e)}")
            return False

    def update_positions(self, price_updates: Dict[str, float]):
        """Update position prices and check risk limits.

        Args:
            price_updates: Symbol to price mapping
        """
        try:
            for symbol, price in price_updates.items():
                if symbol in self.positions:
                    position = self.positions[symbol]
                    position.current_price = price

                    # Check stop loss
                    if self._check_stop_loss(position):
                        continue  # Position was closed

                    # Check take profit
                    if self._check_take_profit(position):
                        continue  # Position was closed

            # Update portfolio risk metrics
            self._update_risk_metrics()

            # Check portfolio-level risk limits
            self._check_portfolio_limits()

        except Exception as e:
            self.logger.error(f"❌ Error updating positions: {str(e)}")

    def _check_stop_loss(self, position: Position) -> bool:
        """Check if stop loss is hit.

        Args:
            position: Position to check

        Returns:
            bool: True if position was closed
        """
        try:
            if not position.stop_loss:
                return False

            stop_hit = False
            if position.side == 'long' and position.current_price <= position.stop_loss:
                stop_hit = True
            elif position.side == 'short' and position.current_price >= position.stop_loss:
                stop_hit = True

            if stop_hit:
                self.logger.warning(f"🛑 Stop loss hit for {position.symbol} at {position.current_price:.2f}")
                self.close_position(position.symbol, position.stop_loss)
                return True

            return False

        except Exception as e:
            self.logger.error(f"❌ Error checking stop loss for {position.symbol}: {str(e)}")
            return False

    def _check_take_profit(self, position: Position) -> bool:
        """Check if take profit is hit.

        Args:
            position: Position to check

        Returns:
            bool: True if position was closed
        """
        try:
            if not position.take_profit:
                return False

            profit_hit = False
            if position.side == 'long' and position.current_price >= position.take_profit:
                profit_hit = True
            elif position.side == 'short' and position.current_price <= position.take_profit:
                profit_hit = True

            if profit_hit:
                self.logger.info(f"💰 Take profit hit for {position.symbol} at {position.current_price:.2f}")
                self.close_position(position.symbol, position.take_profit)
                return True

            return False

        except Exception as e:
            self.logger.error(f"❌ Error checking take profit for {position.symbol}: {str(e)}")
            return False

    def _update_risk_metrics(self):
        """Update portfolio risk metrics."""
        try:
            # Calculate current portfolio value
            current_value = self.portfolio_value
            for position in self.positions.values():
                current_value += position.quantity * position.current_price

            # Update drawdown
            if current_value > self.peak_portfolio_value:
                self.peak_portfolio_value = current_value
            else:
                drawdown = (self.peak_portfolio_value - current_value) / self.peak_portfolio_value
                self.max_drawdown = max(self.max_drawdown, drawdown)

            # Calculate total risk amount
            total_risk = sum(pos.risk_amount for pos in self.positions.values())

        except Exception as e:
            self.logger.error(f"❌ Error updating risk metrics: {str(e)}")

    def _check_portfolio_limits(self):
        """Check portfolio-level risk limits."""
        try:
            # Check daily loss limit
            if not self.daily_loss_limit_hit and self.daily_pnl <= -self.max_daily_loss:
                self.daily_loss_limit_hit = True
                self.logger.critical(f"🚨 Daily loss limit hit: ₹{self.daily_pnl:.2f} (limit: ₹{self.max_daily_loss:.2f})")
                self._close_all_positions("daily_loss_limit")

            # Check maximum drawdown
            if self.max_drawdown >= 0.20:  # 20% drawdown
                if not self.portfolio_stop_active:
                    self.portfolio_stop_active = True
                    self.logger.critical(f"🚨 Portfolio stop activated - Max drawdown: {self.max_drawdown:.2%}")
                    self._close_all_positions("portfolio_stop")

        except Exception as e:
            self.logger.error(f"❌ Error checking portfolio limits: {str(e)}")

    def _close_all_positions(self, reason: str):
        """Close all open positions.

        Args:
            reason: Reason for closing positions
        """
        try:
            symbols_to_close = list(self.positions.keys())
            for symbol in symbols_to_close:
                self.close_position(symbol)
            self.logger.warning(f"🔒 Closed all positions due to: {reason}")

        except Exception as e:
            self.logger.error(f"❌ Error closing all positions: {str(e)}")

    def get_risk_metrics(self) -> RiskMetrics:
        """Get current risk metrics.

        Returns:
            RiskMetrics: Current risk metrics
        """
        try:
            current_value = self.portfolio_value
            for position in self.positions.values():
                current_value += position.quantity * position.current_price

            daily_pnl_percent = (self.daily_pnl / self.daily_start_value) * 100 if self.daily_start_value > 0 else 0

            # Calculate win rate
            if self.trade_history:
                winning_trades = sum(1 for trade in self.trade_history if trade['pnl'] > 0)
                win_rate = winning_trades / len(self.trade_history)
            else:
                win_rate = None

            total_risk = sum(pos.risk_amount for pos in self.positions.values())

            return RiskMetrics(
                total_portfolio_value=current_value,
                total_risk_amount=total_risk,
                max_drawdown=self.max_drawdown,
                daily_pnl=self.daily_pnl,
                daily_pnl_percent=daily_pnl_percent,
                win_rate=win_rate,
                total_trades=len(self.trade_history),
                winning_trades=sum(1 for trade in self.trade_history if trade['pnl'] > 0)
            )

        except Exception as e:
            self.logger.error(f"❌ Error calculating risk metrics: {str(e)}")
            return RiskMetrics(0, 0, 0, 0, 0)

    def get_positions(self) -> Dict[str, Position]:
        """Get all open positions.

        Returns:
            dict: Symbol to Position mapping
        """
        return self.positions.copy()

    def reset_daily_stats(self):
        """Reset daily statistics (call at start of new trading day)."""
        self.daily_pnl = 0.0
        self.daily_loss_limit_hit = False
        self.daily_start_value = self.portfolio_value
        self.logger.info("🌅 Daily statistics reset")


# Global risk manager instance
risk_manager = RiskManager()


def get_risk_manager() -> RiskManager:
    """Get the global risk manager instance.

    Returns:
        RiskManager: The global risk manager
    """
    return risk_manager


def calculate_position_size(symbol: str, entry_price: float, stop_loss: float, side: str = 'long') -> int:
    """Calculate position size for a trade.

    Args:
        symbol: Trading symbol
        entry_price: Entry price
        stop_loss: Stop loss price
        side: 'long' or 'short'

    Returns:
        int: Position quantity
    """
    return risk_manager.calculate_position_size(symbol, entry_price, stop_loss, side)


def open_position(symbol: str, side: str, quantity: int, entry_price: float,
                 stop_loss: Optional[float] = None) -> bool:
    """Open a new position.

    Args:
        symbol: Trading symbol
        side: 'long' or 'short'
        quantity: Position quantity
        entry_price: Entry price
        stop_loss: Stop loss price

    Returns:
        bool: True if position opened successfully
    """
    return risk_manager.open_position(symbol, side, quantity, entry_price, stop_loss)


def close_position(symbol: str, exit_price: Optional[float] = None) -> bool:
    """Close an existing position.

    Args:
        symbol: Trading symbol
        exit_price: Exit price

    Returns:
        bool: True if position closed successfully
    """
    return risk_manager.close_position(symbol, exit_price)