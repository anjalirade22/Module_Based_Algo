"""API module for broker integration.

This module provides a unified interface for broker API operations including:
- Authentication and session management
- Order placement and management
- Market data fetching
- Position and portfolio management
- WebSocket connections for live data

Currently implemented for Angel One SmartAPI.
"""
import time
import json
from typing import Dict, List, Optional, Any, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from SmartApi import SmartConnect
from datetime import datetime, timedelta

from config import config
from modules.logging_config import logger


class BrokerAPI:
    """Unified broker API interface for Angel One SmartAPI."""

    def __init__(self):
        """Initialize the broker API client."""
        self.client: Optional['SmartConnect'] = None
        self.feed_token: Optional[str] = None
        self.jwt_token: Optional[str] = None
        self.websocket = None
        self.is_connected = False
        self.last_auth_time: Optional[datetime] = None
        self.session_expiry: Optional[datetime] = None

        # Initialize logger
        self.logger = logger

    def authenticate(self) -> bool:
        """Authenticate with the broker API.

        Returns:
            bool: True if authentication successful, False otherwise
        """
        try:
            self.logger.info("Attempting broker authentication...")

            # Check if we have required credentials
            if not all([config.API_KEY, config.USERNAME, config.PIN, config.TOTP_TOKEN]):
                self.logger.error("Missing required credentials for authentication")
                return False

            # Import SmartAPI (this would need to be installed)
            try:
                from SmartApi import SmartConnect
            except ImportError:
                self.logger.error("SmartApi package not installed. Install with: pip install smartapi-python")
                return False

            # Initialize SmartConnect client
            self.client = SmartConnect(api_key=config.API_KEY)

            # Generate TOTP for 2FA
            totp_token = self._generate_totp()

            # Login
            login_data = self.client.generateSession(
                config.USERNAME,
                config.PIN,
                totp_token
            )

            # Validate response is a dictionary
            if not isinstance(login_data, dict):
                self.logger.error("Invalid response format from authentication API")
                return False

            if login_data.get('status') and login_data.get('data'):
                self.jwt_token = login_data['data'].get('jwtToken')
                self.feed_token = login_data['data'].get('feedToken')
                self.last_auth_time = datetime.now()
                self.session_expiry = self.last_auth_time + timedelta(hours=24)  # Sessions typically last 24 hours

                self.logger.info("Broker authentication successful")
                config.SMART_API_OBJ = self.client  # type: ignore
                config.JWT_TOKEN = self.jwt_token
                config.FEED_TOKEN = self.feed_token

                return True
            else:
                error_msg = login_data.get('message', 'Unknown authentication error')
                self.logger.error(f"Authentication failed: {error_msg}")
                return False

        except Exception as e:
            self.logger.error(f"Authentication error: {str(e)}")
            return False

    def _generate_totp(self) -> str:
        """Generate TOTP token for 2FA.

        Returns:
            str: TOTP token
        """
        try:
            import pyotp
            totp = pyotp.TOTP(config.TOTP_TOKEN)
            return totp.now()
        except ImportError:
            self.logger.warning("pyotp not installed, using TOTP_TOKEN directly")
            return config.TOTP_TOKEN

    def is_authenticated(self) -> bool:
        """Check if the session is still valid.

        Returns:
            bool: True if authenticated and session valid
        """
        if not self.client or not self.jwt_token:
            return False

        # Check if session has expired
        if self.session_expiry and datetime.now() > self.session_expiry:
            self.logger.warning("Session expired, need re-authentication")
            return False

        return True

    def renew_session(self) -> bool:
        """Renew the authentication session if needed.

        Returns:
            bool: True if session renewed successfully
        """
        if self.is_authenticated():
            return True

        self.logger.info("🔄 Renewing authentication session...")
        return self.authenticate()

    def place_order(self, order_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Place an order with the broker.

        Args:
            order_params: Order parameters including symbol, quantity, price, etc.

        Returns:
            dict: Order response or None if failed
        """
        try:
            if not self.renew_session():
                return None

            # Ensure client is authenticated
            if self.client is None:
                self.logger.error("API client not initialized")
                return None

            # Type assertion for type checker
            assert self.client is not None

            # Validate required parameters
            required_params = ['tradingsymbol', 'symboltoken', 'transactiontype', 'ordertype', 'producttype', 'quantity']
            missing_params = [param for param in required_params if param not in order_params]

            if missing_params:
                self.logger.error(f"Missing required order parameters: {missing_params}")
                return None

            # Set default values if not provided
            order_params.setdefault('exchange', 'NSE')
            order_params.setdefault('duration', 'DAY')
            order_params.setdefault('price', 0)
            order_params.setdefault('triggerprice', 0)

            self.logger.info(f"Placing order: {order_params}")

            # Place the order
            order_response = self.client.placeOrder(order_params)

            # Ensure response is a dict before accessing keys
            if not isinstance(order_response, dict):
                self.logger.error(f"Unexpected response type for order placement: expected dict, got {type(order_response)}")
                return None

            if order_response.get('status') and order_response.get('data'):
                order_id = order_response['data'].get('orderid')
                self.logger.info(f"Order placed successfully. Order ID: {order_id}")
                return order_response['data']
            else:
                error_msg = order_response.get('message', 'Unknown order placement error')
                self.logger.error(f"Order placement failed: {error_msg}")
                return None

        except Exception as e:
            self.logger.error(f"Order placement error: {str(e)}")
            return None

    def modify_order(self, order_id: str, modify_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Modify an existing order.

        Args:
            order_id: Order ID to modify
            modify_params: Parameters to modify

        Returns:
            dict: Modified order response or None if failed
        """
        try:
            if not self.renew_session():
                return None

            modify_params['orderid'] = order_id

            self.logger.info(f"Modifying order {order_id}: {modify_params}")

            response = self.client.modifyOrder(modify_params)  # type: ignore

            # Ensure response is a dict before accessing keys
            if not isinstance(response, dict):
                self.logger.error(f"Unexpected response type for order modification: expected dict, got {type(response)}")
                return None

            if response.get('status') and response.get('data'):
                self.logger.info(f"Order {order_id} modified successfully")
                return response['data']
            else:
                error_msg = response.get('message', 'Unknown order modification error')
                self.logger.error(f"Order modification failed: {error_msg}")
                return None

        except Exception as e:
            self.logger.error(f"Order modification error: {str(e)}")
            return None

    def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order.

        Args:
            order_id: Order ID to cancel

        Returns:
            bool: True if cancelled successfully
        """
        try:
            if not self.renew_session():
                return False

            self.logger.info(f"Cancelling order {order_id}")

            response = self.client.cancelOrder(order_id=order_id, variety="NORMAL")  # type: ignore

            # Ensure response is a dict before accessing keys
            if not isinstance(response, dict):
                self.logger.error(f"Unexpected response type for order cancellation: expected dict, got {type(response)}")
                return False

            if response.get('status') and response.get('data'):
                self.logger.info(f"Order {order_id} cancelled successfully")
                return True
            else:
                error_msg = response.get('message', 'Unknown order cancellation error')
                self.logger.error(f"Order cancellation failed: {error_msg}")
                return False

        except Exception as e:
            self.logger.error(f"Order cancellation error: {str(e)}")
            return False

    def get_order_book(self) -> Optional[List[Dict[str, Any]]]:
        """Get the current order book.

        Returns:
            list: List of orders or None if failed
        """
        try:
            if not self.renew_session():
                return None

            response = self.client.orderBook()  # type: ignore

            # Ensure response is a dict before accessing keys
            if not isinstance(response, dict):
                self.logger.error(f"Unexpected response type for order book: expected dict, got {type(response)}")
                return None

            if response.get('status') and response.get('data'):
                return response['data']
            else:
                error_msg = response.get('message', 'Unknown error fetching order book')
                self.logger.error(f"Failed to fetch order book: {error_msg}")
                return None

        except Exception as e:
            self.logger.error(f"Error fetching order book: {str(e)}")
            return None

    def get_positions(self) -> Optional[Dict[str, Any]]:
        """Get current positions.

        Returns:
            dict: Positions data or None if failed
        """
        try:
            if not self.renew_session():
                return None

            # Ensure client is authenticated
            if self.client is None:
                self.logger.error("API client not initialized")
                return None

            response = self.client.position()

            # Ensure response is a dict before accessing keys
            if not isinstance(response, dict):
                self.logger.error(f"Unexpected response type for positions: expected dict, got {type(response)}")
                return None

            if response.get('status') and response.get('data'):
                return response['data']
            else:
                error_msg = response.get('message', 'Unknown error fetching positions')
                self.logger.error(f"Failed to fetch positions: {error_msg}")
                return None

        except Exception as e:
            self.logger.error(f"Error fetching positions: {str(e)}")
            return None

    def get_holdings(self) -> Optional[List[Dict[str, Any]]]:
        """Get current holdings.

        Returns:
            list: List of holdings or None if failed
        """
        try:
            if not self.renew_session():
                return None

            # Ensure client is authenticated
            if self.client is None:
                self.logger.error("API client not initialized")
                return None

            response = self.client.holding()

            # Ensure response is a dict before accessing keys
            if not isinstance(response, dict):
                self.logger.error(f"Unexpected response type for holdings: expected dict, got {type(response)}")
                return None

            if response.get('status') and response.get('data'):
                return response['data']
            else:
                error_msg = response.get('message', 'Unknown error fetching holdings')
                self.logger.error(f"Failed to fetch holdings: {error_msg}")
                return None

        except Exception as e:
            self.logger.error(f"Error fetching holdings: {str(e)}")
            return None

    def get_market_data(self, instruments: List[Dict[str, str]], mode: str = "LTP") -> Optional[Dict[str, Any]]:
        """Get market data for instruments.

        Args:
            instruments: List of instrument dicts with 'exchange' and 'token'
            mode: Data mode - "LTP", "QUOTE", "SNAPQUOTE"

        Returns:
            dict: Market data or None if failed
        """
        try:
            if not self.renew_session():
                return None

            # Ensure client is authenticated
            if self.client is None:
                self.logger.error("API client not initialized")
                return None

            # Map mode to feed mode
            mode_map = {"LTP": 1, "QUOTE": 2, "SNAPQUOTE": 3}
            feed_mode = mode_map.get(mode.upper(), 1)

            response = self.client.getMarketData(
                mode=feed_mode,
                exchangeTokens=instruments
            )

            # Ensure response is a dict before accessing keys
            if not isinstance(response, dict):
                self.logger.error(f"Unexpected response type for market data: expected dict, got {type(response)}")
                return None

            if response.get('status') and response.get('data'):
                return response['data']
            else:
                error_msg = response.get('message', 'Unknown error fetching market data')
                self.logger.error(f"Failed to fetch market data: {error_msg}")
                return None

        except Exception as e:
            self.logger.error(f"Error fetching market data: {str(e)}")
            return None

    def get_historical_data(self, instrument: Dict[str, str], from_date: str, to_date: str,
                          interval: str = "ONE_MINUTE") -> Optional[List[Dict[str, Any]]]:
        """Get historical candle data.

        Args:
            instrument: Instrument dict with 'exchange' and 'token'
            from_date: Start date in YYYY-MM-DD format
            to_date: End date in YYYY-MM-DD format
            interval: Candle interval

        Returns:
            list: Historical data or None if failed
        """
        try:
            if not self.renew_session():
                return None

            # Ensure client is authenticated
            if self.client is None:
                self.logger.error("API client not initialized")
                return None

            response = self.client.getCandleData({
                "exchange": instrument["exchange"],
                "symboltoken": instrument["token"],
                "interval": interval,
                "fromdate": from_date,
                "todate": to_date
            })

            # Ensure response is a dict before accessing keys
            if not isinstance(response, dict):
                self.logger.error(f"Unexpected response type for historical data: expected dict, got {type(response)}")
                return None

            if response.get('status') and response.get('data'):
                return response['data']
            else:
                error_msg = response.get('message', 'Unknown error fetching historical data')
                self.logger.error(f"Failed to fetch historical data: {error_msg}")
                return None

        except Exception as e:
            self.logger.error(f"Error fetching historical data: {str(e)}")
            return None

    def get_instrument_details(self, exchange: str, symbol: str) -> Optional[Dict[str, Any]]:
        """Get instrument details by symbol.

        Args:
            exchange: Exchange name (NSE, BSE, etc.)
            symbol: Trading symbol

        Returns:
            dict: Instrument details or None if not found
        """
        try:
            if not self.renew_session():
                return None

            # This would typically require a symbol lookup API
            # For now, return a basic structure
            # In production, you'd implement proper symbol lookup
            self.logger.warning("get_instrument_details is a stub - implement proper symbol lookup")
            return {
                "exchange": exchange,
                "symbol": symbol,
                "token": "unknown",  # Would need to be looked up
                "name": symbol
            }

        except Exception as e:
            self.logger.error(f"Error getting instrument details: {str(e)}")
            return None


# Global API instance
api_client = BrokerAPI()


def get_api_client() -> BrokerAPI:
    """Get the global API client instance.

    Returns:
        BrokerAPI: The global API client
    """
    return api_client


def authenticate() -> bool:
    """Convenience function to authenticate the API client.

    Returns:
        bool: True if authentication successful
    """
    return api_client.authenticate()


def is_authenticated() -> bool:
    """Check if API client is authenticated.

    Returns:
        bool: True if authenticated
    """
    return api_client.is_authenticated()
