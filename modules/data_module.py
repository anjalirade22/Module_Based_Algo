"""Data module for market data management.

This module handles:
- Fetching live market data via WebSocket/API
- Retrieving historical data
- Data storage and caching
- Data preprocessing and formatting
- Real-time data streaming

Data is stored in structured formats for easy access by strategies.
"""
import os
import json
import time
import threading
from typing import Dict, List, Optional, Any, Union, Callable
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

from config import config
from modules.api_module import get_api_client
from modules.logging_config import logger


class MarketData:
    """Container for market data with metadata."""

    def __init__(self, symbol: str, data_type: str = "live"):
        """Initialize market data container.

        Args:
            symbol: Trading symbol
            data_type: Type of data (live/historical)
        """
        self.symbol = symbol
        self.data_type = data_type
        self.last_update = None
        self.data = {}
        self.metadata = {}

    def update(self, data: Dict[str, Any]):
        """Update market data.

        Args:
            data: New market data
        """
        self.data.update(data)
        self.last_update = datetime.now()

    def get_ltp(self) -> Optional[float]:
        """Get last traded price.

        Returns:
            float: LTP or None if not available
        """
        return self.data.get('ltp')

    def get_ohlc(self) -> Optional[Dict[str, float]]:
        """Get OHLC data.

        Returns:
            dict: OHLC data or None if not available
        """
        ohlc_keys = ['open', 'high', 'low', 'close']
        if all(key in self.data for key in ohlc_keys):
            return {key: self.data[key] for key in ohlc_keys}
        return None

    def is_stale(self, max_age_seconds: int = 300) -> bool:
        """Check if data is stale.

        Args:
            max_age_seconds: Maximum age in seconds

        Returns:
            bool: True if data is stale
        """
        if not self.last_update:
            return True
        return (datetime.now() - self.last_update).seconds > max_age_seconds


class DataManager:
    """Manages market data fetching, storage, and streaming."""

    def __init__(self):
        """Initialize the data manager."""
        self.api_client = get_api_client()
        self.logger = logger

        # Data storage
        self.live_data = {}  # symbol -> MarketData
        self.historical_data = {}  # symbol -> DataFrame
        self.subscriptions = set()  # Active symbol subscriptions

        # WebSocket and threading
        self.websocket_thread = None
        self.is_streaming = False
        self.data_callbacks = []  # List of callback functions

        # Cache settings
        self.cache_dir = Path("data/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Data settings
        self.max_cache_age = timedelta(hours=24)  # Cache historical data for 24 hours

    def subscribe_symbol(self, symbol: str, exchange: str = "NSE") -> bool:
        """Subscribe to live data for a symbol.

        Args:
            symbol: Trading symbol
            exchange: Exchange name

        Returns:
            bool: True if subscription successful
        """
        try:
            if symbol in self.subscriptions:
                self.logger.debug(f"📡 Symbol {symbol} already subscribed")
                return True

            # Get instrument token
            instrument = self._get_instrument_token(symbol, exchange)
            if not instrument:
                return False

            # Initialize market data container
            self.live_data[symbol] = MarketData(symbol, "live")

            # Add to subscriptions
            self.subscriptions.add(symbol)

            self.logger.info(f"✅ Subscribed to {symbol} ({exchange})")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to subscribe to {symbol}: {str(e)}")
            return False

    def unsubscribe_symbol(self, symbol: str) -> bool:
        """Unsubscribe from live data for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            bool: True if unsubscription successful
        """
        try:
            if symbol not in self.subscriptions:
                return True

            self.subscriptions.remove(symbol)
            if symbol in self.live_data:
                del self.live_data[symbol]

            self.logger.info(f"✅ Unsubscribed from {symbol}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to unsubscribe from {symbol}: {str(e)}")
            return False

    def get_live_data(self, symbol: str) -> Optional[MarketData]:
        """Get live market data for a symbol.

        Args:
            symbol: Trading symbol

        Returns:
            MarketData: Live data or None if not available
        """
        return self.live_data.get(symbol)

    def get_historical_data(self, symbol: str, from_date: str, to_date: str,
                          interval: str = "ONE_MINUTE", force_refresh: bool = False) -> Optional[pd.DataFrame]:
        """Get historical data for a symbol.

        Args:
            symbol: Trading symbol
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            interval: Data interval
            force_refresh: Force fresh download

        Returns:
            DataFrame: Historical data or None if failed
        """
        try:
            cache_key = f"{symbol}_{from_date}_{to_date}_{interval}"
            cache_file = self.cache_dir / f"{cache_key}.csv"

            # Check cache first
            if not force_refresh and cache_file.exists():
                cache_age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
                if cache_age < self.max_cache_age:
                    self.logger.debug(f"📂 Loading {symbol} data from cache")
                    df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
                    self.historical_data[symbol] = df
                    return df

            # Fetch from API
            self.logger.info(f"📥 Fetching historical data for {symbol} ({from_date} to {to_date})")

            instrument = self._get_instrument_token(symbol)
            if not instrument:
                return None

            data = self.api_client.get_historical_data(
                instrument=instrument,
                from_date=from_date,
                to_date=to_date,
                interval=interval
            )

            if not data:
                self.logger.error(f"❌ No historical data received for {symbol}")
                return None

            # Convert to DataFrame
            df = self._process_historical_data(data)
            if df is None or df.empty:
                return None

            # Cache the data
            df.to_csv(cache_file)
            self.historical_data[symbol] = df

            self.logger.info(f"✅ Retrieved {len(df)} records for {symbol}")
            return df

        except Exception as e:
            self.logger.error(f"❌ Error fetching historical data for {symbol}: {str(e)}")
            return None

    def _process_historical_data(self, raw_data: List[List[Any]]) -> Optional[pd.DataFrame]:
        """Process raw historical data into DataFrame.

        Args:
            raw_data: Raw data from API

        Returns:
            DataFrame: Processed data
        """
        try:
            if not raw_data:
                return None

            # Angel One historical data format: [timestamp, open, high, low, close, volume]
            columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']

            df = pd.DataFrame(raw_data, columns=columns)

            # Convert timestamp
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)

            # Convert numeric columns
            numeric_cols = ['open', 'high', 'low', 'close', 'volume']
            df[numeric_cols] = df[numeric_cols].astype(float)

            return df

        except Exception as e:
            self.logger.error(f"❌ Error processing historical data: {str(e)}")
            return None

    def _get_instrument_token(self, symbol: str, exchange: str = "NSE") -> Optional[Dict[str, str]]:
        """Get instrument token for a symbol.

        Args:
            symbol: Trading symbol
            exchange: Exchange name

        Returns:
            dict: Instrument info or None
        """
        # This is a simplified version. In production, you'd have a proper
        # instrument master database or API lookup
        try:
            # For common indices, use known tokens
            known_tokens = {
                "NSE:NIFTY": {"exchange": "NSE", "token": "26000"},
                "NSE:BANKNIFTY": {"exchange": "NSE", "token": "26009"},
                "NSE:FINNIFTY": {"exchange": "NSE", "token": "26037"},
            }

            key = f"{exchange}:{symbol.upper()}"
            if key in known_tokens:
                return known_tokens[key]

            # For other symbols, try to get from API
            instrument = self.api_client.get_instrument_details(exchange, symbol)
            return instrument

        except Exception as e:
            self.logger.error(f"❌ Error getting instrument token for {symbol}: {str(e)}")
            return None

    def start_live_stream(self) -> bool:
        """Start live data streaming.

        Returns:
            bool: True if streaming started successfully
        """
        try:
            if self.is_streaming:
                self.logger.warning("⚠️  Live streaming already running")
                return True

            if not self.api_client.is_authenticated():
                self.logger.error("❌ Cannot start streaming: API not authenticated")
                return False

            self.logger.info("🚀 Starting live data stream...")

            # Start WebSocket thread
            self.websocket_thread = threading.Thread(target=self._websocket_handler)
            self.websocket_thread.daemon = True
            self.websocket_thread.start()

            self.is_streaming = True
            self.logger.info("✅ Live data streaming started")
            return True

        except Exception as e:
            self.logger.error(f"❌ Failed to start live streaming: {str(e)}")
            return False

    def stop_live_stream(self):
        """Stop live data streaming."""
        try:
            self.is_streaming = False
            if self.websocket_thread:
                self.websocket_thread.join(timeout=5)

            self.logger.info("✅ Live data streaming stopped")

        except Exception as e:
            self.logger.error(f"❌ Error stopping live stream: {str(e)}")

    def _websocket_handler(self):
        """Handle WebSocket connection for live data."""
        try:
            # This is a simplified WebSocket handler
            # In production, you'd implement proper WebSocket connection
            # using the broker's WebSocket API

            while self.is_streaming:
                try:
                    # Simulate fetching live data for subscribed symbols
                    for symbol in list(self.subscriptions):
                        if symbol in self.live_data:
                            # In real implementation, this would come from WebSocket
                            # For now, we'll use the API to fetch LTP
                            self._update_live_data(symbol)

                    # Sleep before next update
                    time.sleep(1)  # 1 second intervals

                except Exception as e:
                    self.logger.error(f"❌ WebSocket handler error: {str(e)}")
                    time.sleep(5)  # Wait before retry

        except Exception as e:
            self.logger.error(f"❌ WebSocket thread error: {str(e)}")

    def _update_live_data(self, symbol: str):
        """Update live data for a symbol.

        Args:
            symbol: Trading symbol
        """
        try:
            instrument = self._get_instrument_token(symbol)
            if not instrument:
                return

            # Fetch LTP data
            instruments = [{"exchange": instrument["exchange"], "token": instrument["token"]}]
            data = self.api_client.get_market_data(instruments, "LTP")

            if data and data.get('fetched'):
                for item in data['fetched']:
                    market_data = {
                        'ltp': float(item.get('ltp', 0)),
                        'volume': int(item.get('volume', 0)),
                        'oi': int(item.get('oi', 0)),
                        'timestamp': datetime.now()
                    }

                    if symbol in self.live_data:
                        self.live_data[symbol].update(market_data)

                        # Notify callbacks
                        self._notify_callbacks(symbol, market_data)

        except Exception as e:
            self.logger.debug(f"⚠️  Failed to update live data for {symbol}: {str(e)}")

    def add_data_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """Add a callback function for data updates.

        Args:
            callback: Function to call when data updates (symbol, data)
        """
        self.data_callbacks.append(callback)

    def remove_data_callback(self, callback: Callable):
        """Remove a data callback function.

        Args:
            callback: Callback function to remove
        """
        if callback in self.data_callbacks:
            self.data_callbacks.remove(callback)

    def _notify_callbacks(self, symbol: str, data: Dict[str, Any]):
        """Notify all callbacks about data updates.

        Args:
            symbol: Trading symbol
            data: Updated data
        """
        for callback in self.data_callbacks:
            try:
                callback(symbol, data)
            except Exception as e:
                self.logger.error(f"❌ Data callback error: {str(e)}")

    def get_symbols_data(self) -> Dict[str, MarketData]:
        """Get all live data for subscribed symbols.

        Returns:
            dict: Symbol to MarketData mapping
        """
        return self.live_data.copy()

    def clear_cache(self, older_than_days: int = 7):
        """Clear old cached data.

        Args:
            older_than_days: Delete cache older than this many days
        """
        try:
            cutoff_time = datetime.now() - timedelta(days=older_than_days)

            for cache_file in self.cache_dir.glob("*.csv"):
                if datetime.fromtimestamp(cache_file.stat().st_mtime) < cutoff_time:
                    cache_file.unlink()
                    self.logger.debug(f"🗑️  Deleted old cache file: {cache_file.name}")

            self.logger.info("✅ Cache cleanup completed")

        except Exception as e:
            self.logger.error(f"❌ Error during cache cleanup: {str(e)}")


# Global data manager instance
data_manager = DataManager()


def get_data_manager() -> DataManager:
    """Get the global data manager instance.

    Returns:
        DataManager: The global data manager
    """
    return data_manager


def subscribe_symbol(symbol: str, exchange: str = "NSE") -> bool:
    """Subscribe to live data for a symbol.

    Args:
        symbol: Trading symbol
        exchange: Exchange name

    Returns:
        bool: True if subscription successful
    """
    return data_manager.subscribe_symbol(symbol, exchange)


def get_live_data(symbol: str) -> Optional[MarketData]:
    """Get live market data for a symbol.

    Args:
        symbol: Trading symbol

    Returns:
        MarketData: Live data or None
    """
    return data_manager.get_live_data(symbol)


def get_historical_data(symbol: str, from_date: str, to_date: str,
                      interval: str = "ONE_MINUTE") -> Optional[pd.DataFrame]:
    """Get historical data for a symbol.

    Args:
        symbol: Trading symbol
        from_date: Start date
        to_date: End date
        interval: Data interval

    Returns:
        DataFrame: Historical data or None
    """
    return data_manager.get_historical_data(symbol, from_date, to_date, interval)