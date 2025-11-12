"""Global settings and parameters for the trading system.

This module loads non-sensitive configuration and provides the Config class.
Sensitive credentials are imported from credentials.py (gitignored).

All settings are stored directly in this file for easy modification.

Import the config singleton: from config import config
"""
from __future__ import annotations

import os
import logging
from datetime import time
from typing import Any, Dict, Optional

import pytz

# Import logger for proper logging
from modules.logging_config import logger

# Import sensitive credentials
from .credentials import (
    API_KEY, USERNAME, PIN, TOTP_TOKEN,
    BOT_TOKEN, CHAT_ID,
    SHEET_ID
)

# --------------------------
# Time & timezone variables
# --------------------------
TIME_ZONE = pytz.timezone('Asia/Kolkata')
TZ_INFO = TIME_ZONE
HOUR = time.fromisoformat('09:14:55')

# --------------------------
# Runtime API & WebSocket objects (initialized at runtime)
# --------------------------
SMART_API_OBJ: Optional[Any] = None
FEED_TOKEN: Optional[str] = None
JWT_TOKEN: Optional[str] = None
SMART_WEB: Optional[Any] = None
LIVE_FEED_JSON: Dict[str, Any] = {}

# --------------------------
# WebSocket configuration
# --------------------------
CORRELATION_ID = 'sdbfihbw49rtgw873gr192'
FEED_MODE = 1  # 1=LTP, 2=Quote, 3=Snap Quote

# --------------------------
# Trading parameters
# --------------------------
PRODUCT_TYPE = 'CARRYFORWARD'
ORDER_TYPE = 'MARKET'
LOT = 1
QUANTITY = 15
LOT_SIZE = {
    'nifty': 75,
    'banknifty': 35
}
LOOKBACK = 400

# --------------------------
# Trading mode configuration
# --------------------------
TRADING_MODE = 'live'  # paper/test/live
TEST_QUANTITY = 1

# --------------------------
# Google Sheets configuration
# --------------------------
CREDENTIALS_PATH = r'D:\Algo\swing-logs-62812324e54a.json'

# --------------------------
# Risk management parameters
# --------------------------
MAX_POSITIONS = 10
MAX_DAILY_LOSS = 50000.0
MAX_POSITION_SIZE = 100000.0
POSITION_SIZE_PERCENT = 0.02
STOP_LOSS_PERCENT = 0.05
TARGET_PROFIT_PERCENT = 0.10

# --------------------------
# Order management
# --------------------------
ORDER_TIMEOUT = 60
MAX_ORDER_RETRY = 3
ORDER_STATUS_CHECK_INTERVAL = 5

# --------------------------
# Session management
# --------------------------
SESSION_CHECK_INTERVAL = 300
SESSION_RENEWAL_THRESHOLD = 3600


# --------------------------
# Config class with helper methods
# --------------------------
class Config:
    """Container class for config values and runtime helpers.

    Example usage:
        from config import config
        if config.is_authenticated():
            api = config.get_smart_api()

    The initialize_smart_api method is a stub - replace with real broker
    client initialization.
    """

    def __init__(self):
        # time & timezone
        self.TIME_ZONE = TIME_ZONE
        self.TZ_INFO = TZ_INFO
        self.HOUR = HOUR

        # credentials (imported from credentials.py)
        self.API_KEY = API_KEY
        self.USERNAME = USERNAME
        self.PIN = PIN
        self.TOTP_TOKEN = TOTP_TOKEN
        self.BOT_TOKEN = BOT_TOKEN
        self.CHAT_ID = CHAT_ID
        self.SHEET_ID = SHEET_ID
        self.CREDENTIALS_PATH = CREDENTIALS_PATH

        # runtime objects
        self.SMART_API_OBJ = None
        self.FEED_TOKEN: Optional[str] = None
        self.JWT_TOKEN: Optional[str] = None
        self.SMART_WEB = None
        self.LIVE_FEED_JSON: Dict[str, Any] = {}

        # websocket & trading params
        self.CORRELATION_ID = CORRELATION_ID
        self.FEED_MODE = FEED_MODE
        self.PRODUCT_TYPE = PRODUCT_TYPE
        self.ORDER_TYPE = ORDER_TYPE
        self.LOT = LOT
        self.QUANTITY = QUANTITY
        self.LOT_SIZE = LOT_SIZE
        self.LOOKBACK = LOOKBACK
        self.TRADING_MODE = TRADING_MODE
        self.TEST_QUANTITY = TEST_QUANTITY

        # risk management
        self.MAX_POSITIONS = MAX_POSITIONS
        self.MAX_DAILY_LOSS = MAX_DAILY_LOSS
        self.MAX_POSITION_SIZE = MAX_POSITION_SIZE
        self.POSITION_SIZE_PERCENT = POSITION_SIZE_PERCENT
        self.STOP_LOSS_PERCENT = STOP_LOSS_PERCENT
        self.TARGET_PROFIT_PERCENT = TARGET_PROFIT_PERCENT

        # order & session management
        self.ORDER_TIMEOUT = ORDER_TIMEOUT
        self.MAX_ORDER_RETRY = MAX_ORDER_RETRY
        self.ORDER_STATUS_CHECK_INTERVAL = ORDER_STATUS_CHECK_INTERVAL
        self.SESSION_CHECK_INTERVAL = SESSION_CHECK_INTERVAL
        self.SESSION_RENEWAL_THRESHOLD = SESSION_RENEWAL_THRESHOLD

    # ---- Helper methods (stubs) ----
    def initialize_smart_api(self, *args, **kwargs) -> bool:
        """Initialize and authenticate the broker API client.

        This is a stub. Replace the body with the real broker SDK login.
        On success, set self.SMART_API_OBJ and return True. On failure,
        return False.
        """
        try:
            # Example pseudo-code - replace with actual broker client calls
            # from some_broker_sdk import SmartConnect
            # client = SmartConnect(api_key=self.API_KEY, username=self.USERNAME)
            # client.login(pin=self.PIN, totp=self.TOTP_TOKEN)
            # self.SMART_API_OBJ = client
            self.SMART_API_OBJ = None  # No-op for now
            return False
        except Exception as e:
            logger.error(f'Failed to initialize smart api: {e}')
            self.SMART_API_OBJ = None
            return False

    def get_smart_api(self) -> Optional[Any]:
        """Return the SMART_API_OBJ (may be None).

        If not initialized, attempt to initialize once.
        """
        if self.SMART_API_OBJ is None:
            self.initialize_smart_api()
        return self.SMART_API_OBJ

    def is_authenticated(self) -> bool:
        """Return True if SMART_API_OBJ appears to be authenticated.

        This method uses a heuristic: if SMART_API_OBJ is not None and has a
        truthy attribute/method that indicates authentication, return True.
        Brokers differ in APIs; augment this check when integrating a real SDK.
        """
        if self.SMART_API_OBJ is None:
            return False
        if hasattr(self.SMART_API_OBJ, 'is_authenticated'):
            try:
                return bool(getattr(self.SMART_API_OBJ, 'is_authenticated'))
            except Exception:
                return False
        return False


# Singleton instance
config = Config()

# Backwards-compatible module-level exports
__all__ = [
    'config', 'Config',
    'TIME_ZONE', 'TZ_INFO', 'HOUR',
    'API_KEY', 'USERNAME', 'PIN', 'TOTP_TOKEN',
    'BOT_TOKEN', 'CHAT_ID',
    'SMART_API_OBJ', 'FEED_TOKEN', 'JWT_TOKEN', 'SMART_WEB', 'LIVE_FEED_JSON',
]