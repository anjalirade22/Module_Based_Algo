"""Execution module for trade execution and order management.

This module coordinates between:
- Strategy signals
- Risk management
- API order placement
- Position tracking
- Order status monitoring

Provides the execution layer that translates signals into actual trades.
"""
import time
import threading
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum

from config import config
from modules.api_module import get_api_client
from modules.strategy_module import get_strategy_manager, Signal, SignalType
from modules.rms_module import get_risk_manager
from modules.logging_config import logger


class OrderStatus(Enum):
    """Order status enumeration."""
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    PARTIAL_FILL = "partial_fill"


class Order:
    """Represents a trading order."""

    def __init__(self, symbol: str, side: str, quantity: int, price: float,
                 order_type: str = "MARKET", product_type: str = "CARRYFORWARD"):
        """Initialize order.

        Args:
            symbol: Trading symbol
            side: 'BUY' or 'SELL'
            quantity: Order quantity
            price: Order price
            order_type: Order type (MARKET, LIMIT, etc.)
            product_type: Product type (CARRYFORWARD, INTRADAY, etc.)
        """
        self.order_id = None  # Broker order ID
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.price = price
        self.order_type = order_type
        self.product_type = product_type
        self.status = OrderStatus.PENDING
        self.filled_quantity = 0
        self.average_price = 0.0
        self.timestamp = datetime.now()
        self.last_update = datetime.now()

    def update_status(self, status: OrderStatus, filled_qty: int = 0, avg_price: float = 0.0):
        """Update order status.

        Args:
            status: New order status
            filled_qty: Filled quantity
            avg_price: Average fill price
        """
        self.status = status
        self.filled_quantity = filled_qty
        self.average_price = avg_price
        self.last_update = datetime.now()

    def is_complete(self) -> bool:
        """Check if order is complete.

        Returns:
            bool: True if order is filled, cancelled, or rejected
        """
        return self.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]

    def __str__(self) -> str:
        return f"{self.side} {self.symbol} x{self.quantity} @ {self.price} [{self.status.value}]"


class ExecutionEngine:
    """Execution engine for processing signals and managing orders."""

    def __init__(self):
        """Initialize execution engine."""
        self.logger = logger
        self.api_client = get_api_client()
        self.strategy_manager = get_strategy_manager()
        self.risk_manager = get_risk_manager()

        # Order management
        self.pending_orders = {}  # order_id -> Order
        self.completed_orders = {}  # order_id -> Order
        self.active_positions = {}  # symbol -> position info

        # Execution settings
        self.max_order_retry = config.MAX_ORDER_RETRY
        self.order_timeout = config.ORDER_TIMEOUT
        self.order_check_interval = config.ORDER_STATUS_CHECK_INTERVAL

        # Monitoring thread
        self.monitoring_thread = None
        self.is_monitoring = False

        # Callbacks
        self.execution_callbacks = []  # Functions to call on execution events

    def start(self):
        """Start the execution engine."""
        try:
            self.logger.info("🚀 Starting execution engine...")

            # Start order monitoring
            self.is_monitoring = True
            self.monitoring_thread = threading.Thread(target=self._monitor_orders)
            self.monitoring_thread.daemon = True
            self.monitoring_thread.start()

            self.logger.info("✅ Execution engine started")

        except Exception as e:
            self.logger.error(f"❌ Failed to start execution engine: {str(e)}")

    def stop(self):
        """Stop the execution engine."""
        try:
            self.logger.info("🛑 Stopping execution engine...")

            self.is_monitoring = False
            if self.monitoring_thread:
                self.monitoring_thread.join(timeout=5)

            # Cancel all pending orders
            self._cancel_all_pending_orders()

            self.logger.info("✅ Execution engine stopped")

        except Exception as e:
            self.logger.error(f"❌ Error stopping execution engine: {str(e)}")

    def process_signal(self, signal: Signal) -> bool:
        """Process a trading signal.

        Args:
            signal: Trading signal to process

        Returns:
            bool: True if signal processed successfully
        """
        try:
            self.logger.info(f"📡 Processing signal: {signal}")

            # Validate signal
            if not self._validate_signal(signal):
                return False

            # Execute based on signal type
            if signal.signal_type in [SignalType.BUY, SignalType.SELL]:
                return self._execute_entry_signal(signal)
            elif signal.signal_type in [SignalType.EXIT_LONG, SignalType.EXIT_SHORT]:
                return self._execute_exit_signal(signal)
            else:
                self.logger.debug(f"⚠️  Ignoring signal type: {signal.signal_type}")
                return True

        except Exception as e:
            self.logger.error(f"❌ Error processing signal {signal}: {str(e)}")
            return False

    def _validate_signal(self, signal: Signal) -> bool:
        """Validate a trading signal.

        Args:
            signal: Signal to validate

        Returns:
            bool: True if signal is valid
        """
        try:
            # Check if symbol is valid
            if not signal.symbol:
                self.logger.error("❌ Signal missing symbol")
                return False

            # Check confidence threshold
            if signal.confidence < 0.5:  # Minimum confidence
                self.logger.debug(f"⚠️  Signal confidence too low: {signal.confidence}")
                return False

            # Check trading mode
            if config.TRADING_MODE not in ['live', 'paper']:
                self.logger.warning(f"⚠️  Invalid trading mode: {config.TRADING_MODE}")
                return False

            return True

        except Exception as e:
            self.logger.error(f"❌ Error validating signal: {str(e)}")
            return False

    def _execute_entry_signal(self, signal: Signal) -> bool:
        """Execute an entry signal (BUY/SELL).

        Args:
            signal: Entry signal

        Returns:
            bool: True if executed successfully
        """
        try:
            symbol = signal.symbol
            side = 'long' if signal.signal_type == SignalType.BUY else 'short'

            # Get stop loss from signal metadata
            stop_loss = signal.metadata.get('stop_loss', signal.price * 0.95)  # Default 5% stop

            # Calculate position size using RMS
            quantity = self.risk_manager.calculate_position_size(
                symbol, signal.price, stop_loss, side
            )

            if quantity == 0:
                self.logger.warning(f"⚠️  Position size calculation returned 0 for {symbol}")
                return False

            # Adjust quantity for test mode
            if config.TRADING_MODE == 'paper':
                quantity = min(quantity, config.TEST_QUANTITY)

            # Open position in RMS
            success = self.risk_manager.open_position(
                symbol, side, quantity, signal.price, stop_loss
            )

            if not success:
                self.logger.error(f"❌ Failed to open position in RMS for {symbol}")
                return False

            # Place order if in live mode
            if config.TRADING_MODE == 'live':
                order_success = self._place_order(signal, quantity)
                if not order_success:
                    # Close position in RMS if order failed
                    self.risk_manager.close_position(symbol)
                    return False

            # Update strategy position
            self.strategy_manager.strategies[symbol].update_position(signal)

            self.logger.info(f"✅ Executed {side.upper()} entry for {symbol}: {quantity} units @ {signal.price:.2f}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error executing entry signal: {str(e)}")
            return False

    def _execute_exit_signal(self, signal: Signal) -> bool:
        """Execute an exit signal (EXIT_LONG/EXIT_SHORT).

        Args:
            signal: Exit signal

        Returns:
            bool: True if executed successfully
        """
        try:
            symbol = signal.symbol

            # Check if we have a position
            if symbol not in self.risk_manager.positions:
                self.logger.debug(f"⚠️  No position found for {symbol} to exit")
                return True

            position = self.risk_manager.positions[symbol]

            # Validate exit signal matches position
            expected_side = 'long' if signal.signal_type == SignalType.EXIT_LONG else 'short'
            if position.side != expected_side:
                self.logger.warning(f"⚠️  Exit signal side mismatch for {symbol}: expected {expected_side}, got {position.side}")
                return False

            # Place exit order if in live mode
            if config.TRADING_MODE == 'live':
                exit_side = 'SELL' if position.side == 'long' else 'BUY'
                order_success = self._place_order(signal, position.quantity, exit_side)
                if not order_success:
                    self.logger.error(f"❌ Failed to place exit order for {symbol}")
                    return False

            # Close position in RMS
            self.risk_manager.close_position(symbol, signal.price)

            # Update strategy position
            self.strategy_manager.strategies[symbol].update_position(signal)

            self.logger.info(f"✅ Executed exit for {symbol} @ {signal.price:.2f}")
            return True

        except Exception as e:
            self.logger.error(f"❌ Error executing exit signal: {str(e)}")
            return False

    def _place_order(self, signal: Signal, quantity: int, side: str = None) -> bool:
        """Place an order with the broker.

        Args:
            signal: Trading signal
            quantity: Order quantity
            side: Order side (overrides signal side)

        Returns:
            bool: True if order placed successfully
        """
        try:
            if side is None:
                side = 'BUY' if signal.signal_type == SignalType.BUY else 'SELL'

            # Prepare order parameters
            order_params = {
                'tradingsymbol': signal.symbol,
                'symboltoken': 'unknown',  # Would need to be looked up
                'transactiontype': side,
                'ordertype': config.ORDER_TYPE,
                'producttype': config.PRODUCT_TYPE,
                'quantity': quantity,
                'price': signal.price if config.ORDER_TYPE == 'LIMIT' else 0,
                'exchange': 'NSE'
            }

            # Retry logic
            for attempt in range(self.max_order_retry):
                try:
                    order_response = self.api_client.place_order(order_params)

                    if order_response and order_response.get('status'):
                        order_id = order_response.get('orderid')
                        if order_id:
                            # Create order object
                            order = Order(
                                symbol=signal.symbol,
                                side=side,
                                quantity=quantity,
                                price=signal.price,
                                order_type=config.ORDER_TYPE,
                                product_type=config.PRODUCT_TYPE
                            )
                            order.order_id = order_id
                            order.status = OrderStatus.OPEN

                            self.pending_orders[order_id] = order

                            self.logger.info(f"✅ Order placed: {order_id} - {order}")
                            return True

                    # Log failure and retry
                    error_msg = order_response.get('message', 'Unknown error') if order_response else 'No response'
                    self.logger.warning(f"⚠️  Order attempt {attempt + 1} failed: {error_msg}")

                    if attempt < self.max_order_retry - 1:
                        time.sleep(1)  # Wait before retry

                except Exception as e:
                    self.logger.error(f"❌ Order attempt {attempt + 1} error: {str(e)}")
                    if attempt < self.max_order_retry - 1:
                        time.sleep(1)

            self.logger.error(f"❌ Failed to place order after {self.max_order_retry} attempts")
            return False

        except Exception as e:
            self.logger.error(f"❌ Error placing order: {str(e)}")
            return False

    def _monitor_orders(self):
        """Monitor pending orders and update their status."""
        while self.is_monitoring:
            try:
                # Check each pending order
                orders_to_remove = []

                for order_id, order in self.pending_orders.items():
                    try:
                        # Get order book from API
                        order_book = self.api_client.get_order_book()

                        if order_book:
                            # Find our order in the book
                            order_info = None
                            for book_order in order_book:
                                if str(book_order.get('orderid', '')) == str(order_id):
                                    order_info = book_order
                                    break

                            if order_info:
                                status = order_info.get('status', '').upper()

                                # Update order status
                                if status == 'COMPLETE':
                                    order.update_status(
                                        OrderStatus.FILLED,
                                        filled_qty=int(order_info.get('filledshares', order.quantity)),
                                        avg_price=float(order_info.get('averageprice', order.price))
                                    )
                                    orders_to_remove.append(order_id)
                                    self.logger.info(f"✅ Order filled: {order_id}")

                                elif status in ['CANCELLED', 'REJECTED']:
                                    order.update_status(OrderStatus.CANCELLED if status == 'CANCELLED' else OrderStatus.REJECTED)
                                    orders_to_remove.append(order_id)
                                    self.logger.warning(f"❌ Order {status.lower()}: {order_id}")

                                elif status == 'OPEN':
                                    # Still open, check timeout
                                    if (datetime.now() - order.timestamp).seconds > self.order_timeout:
                                        self._cancel_order(order_id)
                                        order.update_status(OrderStatus.CANCELLED)
                                        orders_to_remove.append(order_id)
                                        self.logger.warning(f"⏰ Order timeout: {order_id}")

                    except Exception as e:
                        self.logger.error(f"❌ Error checking order {order_id}: {str(e)}")

                # Remove completed orders
                for order_id in orders_to_remove:
                    if order_id in self.pending_orders:
                        order = self.pending_orders[order_id]
                        self.completed_orders[order_id] = order
                        del self.pending_orders[order_id]

                # Wait before next check
                time.sleep(self.order_check_interval)

            except Exception as e:
                self.logger.error(f"❌ Error in order monitoring: {str(e)}")
                time.sleep(5)  # Wait before retry

    def _cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order.

        Args:
            order_id: Order ID to cancel

        Returns:
            bool: True if cancelled successfully
        """
        try:
            success = self.api_client.cancel_order(order_id)
            if success:
                self.logger.info(f"✅ Order cancelled: {order_id}")
            return success

        except Exception as e:
            self.logger.error(f"❌ Error cancelling order {order_id}: {str(e)}")
            return False

    def _cancel_all_pending_orders(self):
        """Cancel all pending orders."""
        try:
            for order_id in list(self.pending_orders.keys()):
                self._cancel_order(order_id)
            self.logger.info("✅ Cancelled all pending orders")

        except Exception as e:
            self.logger.error(f"❌ Error cancelling all orders: {str(e)}")

    def get_pending_orders(self) -> Dict[str, Order]:
        """Get all pending orders.

        Returns:
            dict: Order ID to Order mapping
        """
        return self.pending_orders.copy()

    def get_completed_orders(self) -> Dict[str, Order]:
        """Get all completed orders.

        Returns:
            dict: Order ID to Order mapping
        """
        return self.completed_orders.copy()

    def get_order_status(self, order_id: str) -> Optional[OrderStatus]:
        """Get status of a specific order.

        Args:
            order_id: Order ID

        Returns:
            OrderStatus: Order status or None if not found
        """
        if order_id in self.pending_orders:
            return self.pending_orders[order_id].status
        elif order_id in self.completed_orders:
            return self.completed_orders[order_id].status
        return None

    def add_execution_callback(self, callback: Callable[[str, Any], None]):
        """Add a callback for execution events.

        Args:
            callback: Function to call on execution events (event_type, data)
        """
        self.execution_callbacks.append(callback)

    def _notify_callbacks(self, event_type: str, data: Any):
        """Notify all execution callbacks.

        Args:
            event_type: Type of execution event
            data: Event data
        """
        for callback in self.execution_callbacks:
            try:
                callback(event_type, data)
            except Exception as e:
                self.logger.error(f"❌ Execution callback error: {str(e)}")


# Global execution engine instance
execution_engine = ExecutionEngine()


def get_execution_engine() -> ExecutionEngine:
    """Get the global execution engine instance.

    Returns:
        ExecutionEngine: The global execution engine
    """
    return execution_engine


def process_signal(signal: Signal) -> bool:
    """Process a trading signal.

    Args:
        signal: Trading signal to process

    Returns:
        bool: True if signal processed successfully
    """
    return execution_engine.process_signal(signal)


def start_execution():
    """Start the execution engine."""
    execution_engine.start()


def stop_execution():
    """Stop the execution engine."""
    execution_engine.stop()