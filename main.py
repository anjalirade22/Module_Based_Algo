"""Main entry point for the modular automated trading system.

This script initializes and orchestrates all trading system components:
- Configuration and credentials
- Logging system
- API connections
- Data management
- Strategy execution
- Risk management
- Order execution

Usage:
    python main.py                    # Run in live mode
    python main.py --mode paper       # Run in paper trading mode
    python main.py --mode test        # Run tests
    python main.py --help             # Show help
"""
import argparse
import signal
import sys
import time
from typing import Optional

from config import config
from modules.logging_config import logger
from modules.api_module import get_api_client, authenticate
from modules.data_module import get_data_manager, subscribe_symbol
from modules.strategy_module import get_strategy_manager, add_swing_strategy
from modules.rms_module import get_risk_manager
from modules.execution_module import get_execution_engine, start_execution, stop_execution


class TradingSystem:
    """Main trading system orchestrator."""

    def __init__(self, mode: str = 'live'):
        """Initialize the trading system.

        Args:
            mode: Trading mode ('live', 'paper', 'test')
        """
        self.mode = mode
        self.running = False

        # Initialize all managers
        self.api_client = get_api_client()
        self.data_manager = get_data_manager()
        self.strategy_manager = get_strategy_manager()
        self.risk_manager = get_risk_manager()
        self.execution_engine = get_execution_engine()

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info(f"Trading system initialized in {mode.upper()} mode")

    def initialize(self) -> bool:
        """Initialize all system components.

        Returns:
            bool: True if initialization successful
        """
        try:
            logger.info("Initializing trading system components...")

            # Set trading mode in config
            config.TRADING_MODE = self.mode

            # Initialize API client
            if self.mode == 'live':
                logger.info("Authenticating with broker API...")
                if not authenticate():
                    logger.error("Failed to authenticate with broker API")
                    return False
            else:
                logger.info(f"Running in {self.mode.upper()} mode - skipping API authentication")

            # Start execution engine
            start_execution()

            # Setup sample strategies (customize as needed)
            self._setup_strategies()

            logger.info("✅ Trading system initialization completed")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to initialize trading system: {str(e)}")
            return False

    def _setup_strategies(self):
        """Setup trading strategies."""
        try:
            # Example: Add swing strategy for NIFTY
            # In production, load strategies from config or database
            symbols = ['NIFTY']  # Add more symbols as needed

            for symbol in symbols:
                # Subscribe to data
                subscribe_symbol(symbol, 'NSE')

                # Add swing strategy
                add_swing_strategy(symbol, lookback_period=20)

                logger.info(f"Setup strategy for {symbol}")

        except Exception as e:
            logger.error(f"Error setting up strategies: {str(e)}")

    def start(self):
        """Start the trading system."""
        try:
            if not self.initialize():
                logger.error("Initialization failed, cannot start trading system")
                return

            self.running = True
            logger.info("🚀 Starting trading system...")

            # Start live data streaming if in live mode
            if self.mode == 'live':
                self.data_manager.start_live_stream()

            # Main trading loop
            self._trading_loop()

        except Exception as e:
            logger.error(f"❌ Error in trading system: {str(e)}")
        finally:
            self.stop()

    def _trading_loop(self):
        """Main trading loop."""
        try:
            while self.running:
                try:
                    # Generate signals
                    signals = self.strategy_manager.generate_signals()

                    # Process signals through execution engine
                    for symbol, symbol_signals in signals.items():
                        for signal in symbol_signals:
                            self.execution_engine.process_signal(signal)

                    # Log system status periodically
                    self._log_system_status()

                    # Sleep before next iteration
                    time.sleep(60)  # Check every minute

                except Exception as e:
                    logger.error(f"Error in trading loop: {str(e)}")
                    time.sleep(10)  # Wait before retry

        except KeyboardInterrupt:
            logger.info("Trading loop interrupted by user")

    def _log_system_status(self):
        """Log current system status."""
        try:
            # Log status every 5 minutes
            if int(time.time()) % 300 == 0:
                risk_metrics = self.risk_manager.get_risk_metrics()
                positions = len(self.risk_manager.get_positions())
                pending_orders = len(self.execution_engine.get_pending_orders())

                logger.info(f"System Status - Portfolio: ₹{risk_metrics.total_portfolio_value:,.0f}, "
                           f"Positions: {positions}, Pending Orders: {pending_orders}, "
                           f"Daily P&L: ₹{risk_metrics.daily_pnl:.2f}")

        except Exception as e:
            logger.debug(f"Error logging system status: {str(e)}")

    def stop(self):
        """Stop the trading system gracefully."""
        try:
            logger.info("🛑 Stopping trading system...")

            self.running = False

            # Stop execution engine
            stop_execution()

            # Stop data streaming
            self.data_manager.stop_live_stream()

            # Close all positions if in live mode
            if self.mode == 'live':
                self._close_all_positions()

            logger.info("✅ Trading system stopped")

        except Exception as e:
            logger.error(f"❌ Error stopping trading system: {str(e)}")

    def _close_all_positions(self):
        """Close all open positions."""
        try:
            positions = self.risk_manager.get_positions()
            for symbol in positions.keys():
                self.risk_manager.close_position(symbol)
            logger.info("Closed all positions during shutdown")

        except Exception as e:
            logger.error(f"Error closing positions during shutdown: {str(e)}")

    def _signal_handler(self, signum, frame):
        """Handle system signals for graceful shutdown."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.running = False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Modular Automated Trading System')
    parser.add_argument('--mode', choices=['live', 'paper', 'test'],
                       default='paper', help='Trading mode (default: paper)')
    parser.add_argument('--symbols', nargs='+', help='Symbols to trade (default: NIFTY)')
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       default='INFO', help='Logging level (default: INFO)')

    args = parser.parse_args()

    # Set log level
    import logging
    logging.getLogger().setLevel(getattr(logging, args.log_level))

    try:
        # Create and start trading system
        system = TradingSystem(mode=args.mode)

        if args.symbols:
            # Override default symbols if provided
            system.symbols = args.symbols

        # Start the system
        system.start()

    except KeyboardInterrupt:
        logger.info("System interrupted by user")
    except Exception as e:
        logger.error(f"Unhandled error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()