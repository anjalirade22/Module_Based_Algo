"""Entry point for data module.

This module can be run directly to perform various data operations:
    - Start live feed
    - Fetch historical data
    - Update existing data
    - Test data module functionality

Usage:
    # Start live feed
    python -m modules.data_module --live
    
    # Fetch historical data
    python -m modules.data_module --historical NIFTY 99926000
    
    # Update historical data
    python -m modules.data_module --update NIFTY 99926000
    
    # Run tests
    python -m modules.data_module --test
"""

import argparse
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from modules.logger_module import get_logger
from modules.data_module import (
    get_live_feed,
    get_historical_manager,
    get_data_processor
)

logger = get_logger(__name__)


def start_live_feed():
    """Start live data feed subprocess."""
    logger.info("=" * 80)
    logger.info("Starting Live Data Feed")
    logger.info("=" * 80)
    
    try:
        feed = get_live_feed()
        
        # Start feed
        if not feed.start_feed():
            logger.error("Failed to start feed")
            return False
        
        # Wait for data
        logger.info("Waiting for feed data...")
        if not feed.wait_for_data(timeout=30):
            logger.error("Timeout waiting for feed data")
            feed.stop_feed()
            return False
        
        logger.info("Feed is running and data is available")
        logger.info("Press Ctrl+C to stop the feed")
        
        # Monitor feed
        try:
            while True:
                if feed.is_data_fresh():
                    price = feed.get_live_price()
                    logger.info(f"Live price: {price}")
                else:
                    logger.warning("Data is stale")
                
                time.sleep(5)
                
        except KeyboardInterrupt:
            logger.info("Stopping feed...")
            feed.stop_feed()
            logger.info("Feed stopped")
        
        return True
        
    except Exception as e:
        logger.error(f"Error in live feed: {e}", exc_info=True)
        return False


def fetch_historical_data(symbol: str, token: str, interval: str = "FIVE_MINUTE", days: int = 5):
    """Fetch historical data and save to CSV."""
    logger.info("=" * 80)
    logger.info(f"Fetching Historical Data: {symbol}")
    logger.info("=" * 80)
    
    try:
        hist_mgr = get_historical_manager()
        
        # Fetch and save
        df = hist_mgr.fetch_and_save_historical_data(
            symbol=symbol,
            token=token,
            interval=interval,
            days=days
        )
        
        if df is None:
            logger.error("Failed to fetch historical data")
            return False
        
        logger.info(f"Successfully fetched {len(df)} candles")
        logger.info(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        logger.info(f"Latest close: {df['close'].iloc[-1]}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error fetching historical data: {e}", exc_info=True)
        return False


def update_historical_data(symbol: str, token: str, interval: str = "FIVE_MINUTE"):
    """Update existing historical data with latest candles."""
    logger.info("=" * 80)
    logger.info(f"Updating Historical Data: {symbol}")
    logger.info("=" * 80)
    
    try:
        hist_mgr = get_historical_manager()
        
        # Update
        df = hist_mgr.update_historical_data(
            symbol=symbol,
            token=token,
            interval=interval
        )
        
        if df is None:
            logger.error("Failed to update historical data")
            return False
        
        logger.info(f"Successfully updated data, total: {len(df)} candles")
        logger.info(f"Latest timestamp: {df['timestamp'].max()}")
        logger.info(f"Latest close: {df['close'].iloc[-1]}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error updating historical data: {e}", exc_info=True)
        return False


def run_tests():
    """Run data module tests."""
    logger.info("=" * 80)
    logger.info("Running Data Module Tests")
    logger.info("=" * 80)
    
    all_passed = True
    
    # Test 1: LiveDataFeed initialization
    logger.info("\nTest 1: LiveDataFeed initialization")
    try:
        feed = get_live_feed()
        logger.info("✓ LiveDataFeed initialized successfully")
    except Exception as e:
        logger.error(f"✗ Failed to initialize LiveDataFeed: {e}")
        all_passed = False
    
    # Test 2: HistoricalDataManager initialization
    logger.info("\nTest 2: HistoricalDataManager initialization")
    try:
        hist_mgr = get_historical_manager()
        logger.info("✓ HistoricalDataManager initialized successfully")
    except Exception as e:
        logger.error(f"✗ Failed to initialize HistoricalDataManager: {e}")
        all_passed = False
    
    # Test 3: DataProcessor initialization
    logger.info("\nTest 3: DataProcessor initialization")
    try:
        processor = get_data_processor()
        logger.info("✓ DataProcessor initialized successfully")
    except Exception as e:
        logger.error(f"✗ Failed to initialize DataProcessor: {e}")
        all_passed = False
    
    # Test 4: List available data files
    logger.info("\nTest 4: List available data files")
    try:
        hist_mgr = get_historical_manager()
        files = hist_mgr.get_available_data_files()
        logger.info(f"✓ Found {len(files)} data files:")
        for f in files:
            logger.info(f"  - {f['symbol']} ({f['interval']})")
    except Exception as e:
        logger.error(f"✗ Failed to list data files: {e}")
        all_passed = False
    
    # Test 5: Data validation
    logger.info("\nTest 5: Data validation")
    try:
        import pandas as pd
        from datetime import datetime
        
        # Create sample data
        sample_data = pd.DataFrame({
            'timestamp': [datetime.now()],
            'open': [19500.0],
            'high': [19550.0],
            'low': [19480.0],
            'close': [19520.0],
            'volume': [1000000]
        })
        
        processor = get_data_processor()
        if processor.validate_candle_data(sample_data):
            logger.info("✓ Data validation passed")
        else:
            logger.error("✗ Data validation failed")
            all_passed = False
    except Exception as e:
        logger.error(f"✗ Data validation test failed: {e}")
        all_passed = False
    
    # Summary
    logger.info("\n" + "=" * 80)
    if all_passed:
        logger.info("All tests passed ✓")
    else:
        logger.error("Some tests failed ✗")
    logger.info("=" * 80)
    
    return all_passed


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Data Module CLI')
    parser.add_argument('--live', action='store_true', help='Start live feed')
    parser.add_argument('--historical', nargs='+', metavar=('SYMBOL', 'TOKEN'),
                       help='Fetch historical data (symbol token [interval] [days])')
    parser.add_argument('--update', nargs='+', metavar=('SYMBOL', 'TOKEN'),
                       help='Update historical data (symbol token [interval])')
    parser.add_argument('--test', action='store_true', help='Run tests')
    
    args = parser.parse_args()
    
    try:
        if args.live:
            # Start live feed
            start_live_feed()
            
        elif args.historical:
            # Fetch historical data
            if len(args.historical) < 2:
                logger.error("Usage: --historical SYMBOL TOKEN [INTERVAL] [DAYS]")
                sys.exit(1)
            
            symbol = args.historical[0]
            token = args.historical[1]
            interval = args.historical[2] if len(args.historical) > 2 else "FIVE_MINUTE"
            days = int(args.historical[3]) if len(args.historical) > 3 else 5
            
            fetch_historical_data(symbol, token, interval, days)
            
        elif args.update:
            # Update historical data
            if len(args.update) < 2:
                logger.error("Usage: --update SYMBOL TOKEN [INTERVAL]")
                sys.exit(1)
            
            symbol = args.update[0]
            token = args.update[1]
            interval = args.update[2] if len(args.update) > 2 else "FIVE_MINUTE"
            
            update_historical_data(symbol, token, interval)
            
        elif args.test:
            # Run tests
            if run_tests():
                sys.exit(0)
            else:
                sys.exit(1)
        else:
            # No arguments, show help
            parser.print_help()
            
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
