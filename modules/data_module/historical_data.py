"""Historical data management with CSV storage.

This module handles fetching historical candle data from SmartAPI
and storing it in CSV format for Strategy module consumption.

Key Features:
    - Fetch historical candles via SmartAPI
    - Store data in organized CSV structure (data/historical/{SYMBOL}_{INTERVAL}/*.csv)
    - Support for multiple timeframes (1min, 5min, 15min, etc.)
    - Automatic max lookback on first fetch
    - Initialize all intervals for an instrument
    - Automatic data caching and validation
    - CSV format optimized for pandas

Architecture:
    API Module → HistoricalDataManager → CSV Files → Strategy Module
    
    Directory structure:
        data/historical/
            NIFTY_FIVE_MINUTE/
                NIFTY_FIVE_MINUTE.csv
            NIFTY_ONE_DAY/
                NIFTY_ONE_DAY.csv
            BANKNIFTY_FIVE_MINUTE/
                BANKNIFTY_FIVE_MINUTE.csv
    
    CSV format:
        timestamp,open,high,low,close,volume
        2024-01-01 09:15:00,19500.00,19520.00,19495.00,19510.00,1250000
        ...

Usage:
    from modules.data_module import get_historical_manager
    
    # Initialize all intervals for an instrument (first-time setup)
    hist_mgr = get_historical_manager()
    results = hist_mgr.initialize_instrument_data(
        symbol="NIFTY",
        token="99926000"
    )
    
    # Fetch and save specific interval
    df = hist_mgr.fetch_and_save_historical_data(
        symbol="NIFTY",
        token="99926000",
        interval="FIVE_MINUTE",
        max_lookback=True  # Fetch max data on first run
    )
    
    # Load existing data
    df = hist_mgr.load_historical_data("NIFTY", "FIVE_MINUTE")
"""

import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List
from modules.logger_module import get_logger
from modules.api_module import get_api_instance

# Global instance
_historical_manager_instance = None

def get_historical_manager():
    """Get singleton instance of HistoricalDataManager.
    
    Returns:
        HistoricalDataManager: The singleton manager instance
    """
    global _historical_manager_instance
    if _historical_manager_instance is None:
        _historical_manager_instance = HistoricalDataManager()
    return _historical_manager_instance


class HistoricalDataManager:
    """Manages historical market data fetching and CSV storage.
    
    This class provides methods to fetch historical candle data from
    SmartAPI and store it in organized CSV format. Supports automatic
    maximum lookback on first fetch and initialization of all intervals.
    
    Attributes:
        data_dir (Path): Directory for storing CSV files
        api: SmartAPI instance for data fetching
        logger: Logger instance
        
    Directory Structure:
        data/historical/{SYMBOL}_{INTERVAL}/{SYMBOL}_{INTERVAL}.csv
        
        Example:
            data/historical/NIFTY_FIVE_MINUTE/NIFTY_FIVE_MINUTE.csv
            data/historical/NIFTY_ONE_DAY/NIFTY_ONE_DAY.csv
        
    CSV Format:
        timestamp,open,high,low,close,volume
        2024-01-01 09:15:00,19500.00,19520.00,19495.00,19510.00,1250000
        
    Example:
        >>> hist_mgr = HistoricalDataManager()
        >>> 
        >>> # Initialize all intervals for an instrument (first-time setup)
        >>> results = hist_mgr.initialize_instrument_data(
        ...     symbol="NIFTY",
        ...     token="99926000"
        ... )
        >>> 
        >>> # Fetch specific interval with max lookback
        >>> df = hist_mgr.fetch_and_save_historical_data(
        ...     symbol="NIFTY",
        ...     token="99926000",
        ...     interval="FIVE_MINUTE",
        ...     max_lookback=True
        ... )
        >>> 
        >>> # Load existing data
        >>> df = hist_mgr.load_historical_data("NIFTY", "FIVE_MINUTE")
        >>> print(df.head())
    """
    
    # Supported intervals
    INTERVALS = {
        "ONE_MINUTE": "1min",
        "THREE_MINUTE": "3min",
        "FIVE_MINUTE": "5min",
        "TEN_MINUTE": "10min",
        "FIFTEEN_MINUTE": "15min",
        "THIRTY_MINUTE": "30min",
        "ONE_HOUR": "1hour",
        "ONE_DAY": "1day"
    }
    
    # Maximum lookback days for each interval (SmartAPI limits)
    # These are conservative estimates based on Angel One SmartAPI documentation
    MAX_LOOKBACK_DAYS = {
        "ONE_MINUTE": 30,        # 1-minute candles: ~30 days
        "THREE_MINUTE": 60,      # 3-minute candles: ~60 days
        "FIVE_MINUTE": 100,      # 5-minute candles: ~100 days
        "TEN_MINUTE": 100,       # 10-minute candles: ~100 days
        "FIFTEEN_MINUTE": 100,   # 15-minute candles: ~100 days
        "THIRTY_MINUTE": 100,    # 30-minute candles: ~100 days
        "ONE_HOUR": 365,         # 1-hour candles: ~365 days
        "ONE_DAY": 2000          # 1-day candles: ~2000 days
    }
    
    def __init__(self, data_dir: str = "data/historical"):
        """Initialize HistoricalDataManager.
        
        Args:
            data_dir: Directory path for CSV files (default: data/historical)
        """
        self.logger = get_logger(__name__)
        
        # Get project root and create historical data directory
        project_root = Path(__file__).parent.parent.parent
        self.data_dir = project_root / data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Get API instance
        self.api = get_api_instance()
        
        self.logger.info(f"HistoricalDataManager initialized, data dir: {self.data_dir}")
    
    def fetch_historical_data(
        self,
        symbol: str,
        token: str,
        exchange: str = "NSE",
        interval: str = "FIVE_MINUTE",
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        days: int = 5
    ) -> Optional[pd.DataFrame]:
        """Fetch historical candle data from SmartAPI.
        
        Args:
            symbol: Trading symbol (e.g., "NIFTY", "BANKNIFTY")
            token: Instrument token
            exchange: Exchange name (default: NSE)
            interval: Candle interval (default: FIVE_MINUTE)
            from_date: Start date (optional, defaults to 'days' ago)
            to_date: End date (optional, defaults to today)
            days: Number of days to fetch if from_date not specified (default: 5)
            
        Returns:
            pd.DataFrame: Historical data with columns [timestamp, open, high, low, close, volume]
            None if fetch fails
            
        Example:
            >>> hist_mgr = HistoricalDataManager()
            >>> 
            >>> # Fetch last 5 days
            >>> df = hist_mgr.fetch_historical_data("NIFTY", "99926000")
            >>> 
            >>> # Fetch specific date range
            >>> from datetime import datetime
            >>> df = hist_mgr.fetch_historical_data(
            ...     symbol="NIFTY",
            ...     token="99926000",
            ...     from_date=datetime(2024, 1, 1),
            ...     to_date=datetime(2024, 1, 31)
            ... )
        """
        try:
            # Validate interval
            if interval not in self.INTERVALS:
                self.logger.error(f"Invalid interval: {interval}. Must be one of {list(self.INTERVALS.keys())}")
                return None
            
            # Set date range
            if to_date is None:
                to_date = datetime.now()
            if from_date is None:
                from_date = to_date - timedelta(days=days)
            
            # Format dates for API
            from_date_str = from_date.strftime("%Y-%m-%d %H:%M")
            to_date_str = to_date.strftime("%Y-%m-%d %H:%M")
            
            self.logger.info(f"Fetching historical data for {symbol}")
            self.logger.info(f"  Token: {token}")
            self.logger.info(f"  Exchange: {exchange}")
            self.logger.info(f"  Interval: {interval}")
            self.logger.info(f"  From: {from_date_str}")
            self.logger.info(f"  To: {to_date_str}")
            
            # Prepare params
            params = {
                "exchange": exchange,
                "symboltoken": token,
                "interval": interval,
                "fromdate": from_date_str,
                "todate": to_date_str
            }
            
            # Fetch data from API
            response = self.api.getCandleData(params)
            
            if not response or response.get('status') is False:
                error_msg = response.get('message', 'Unknown error') if response else 'No response'
                self.logger.error(f"Failed to fetch historical data: {error_msg}")
                return None
            
            # Extract candle data
            candles = response.get('data', [])
            if not candles:
                self.logger.warning("No historical data returned from API")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Convert price columns to float
            for col in ['open', 'high', 'low', 'close']:
                df[col] = df[col].astype(float)
            
            # Convert volume to int
            df['volume'] = df['volume'].astype(int)
            
            # Sort by timestamp
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            self.logger.info(f"Fetched {len(df)} candles for {symbol}")
            self.logger.debug(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
            
            return df
            
        except Exception as e:
            self.logger.error(f"Error fetching historical data: {e}", exc_info=True)
            return None
    
    def save_to_csv(self, df: pd.DataFrame, symbol: str, interval: str) -> bool:
        """Save DataFrame to CSV file.
        
        File is saved in: data/historical/{SYMBOL}_{INTERVAL}/{SYMBOL}_{INTERVAL}.csv
        
        Args:
            df: DataFrame with historical data
            symbol: Trading symbol
            interval: Candle interval
            
        Returns:
            bool: True if save successful, False otherwise
            
        Example:
            >>> hist_mgr = HistoricalDataManager()
            >>> df = hist_mgr.fetch_historical_data("NIFTY", "99926000")
            >>> hist_mgr.save_to_csv(df, "NIFTY", "FIVE_MINUTE")
        """
        try:
            # Create subdirectory for this symbol-interval combination
            subdir_name = f"{symbol}_{interval}"
            subdir = self.data_dir / subdir_name
            subdir.mkdir(parents=True, exist_ok=True)
            
            # Generate filename
            filename = f"{symbol}_{interval}.csv"
            filepath = subdir / filename
            
            # Save to CSV
            df.to_csv(filepath, index=False)
            
            self.logger.info(f"Saved {len(df)} candles to {filepath}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving to CSV: {e}", exc_info=True)
            return False
    
    def load_historical_data(self, symbol: str, interval: str) -> Optional[pd.DataFrame]:
        """Load historical data from CSV file.
        
        File is loaded from: data/historical/{SYMBOL}_{INTERVAL}/{SYMBOL}_{INTERVAL}.csv
        
        Args:
            symbol: Trading symbol
            interval: Candle interval
            
        Returns:
            pd.DataFrame: Historical data, or None if file doesn't exist
            
        Example:
            >>> hist_mgr = HistoricalDataManager()
            >>> df = hist_mgr.load_historical_data("NIFTY", "FIVE_MINUTE")
            >>> if df is not None:
            ...     print(f"Loaded {len(df)} candles")
        """
        try:
            # Build filepath with subdirectory
            subdir_name = f"{symbol}_{interval}"
            filename = f"{symbol}_{interval}.csv"
            filepath = self.data_dir / subdir_name / filename
            
            if not filepath.exists():
                self.logger.warning(f"CSV file not found: {filepath}")
                return None
            
            # Load CSV
            df = pd.read_csv(filepath)
            
            # Convert timestamp to datetime
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            self.logger.info(f"Loaded {len(df)} candles from {filepath}")
            return df
            
        except Exception as e:
            self.logger.error(f"Error loading CSV: {e}", exc_info=True)
            return None
    
    def fetch_and_save_historical_data(
        self,
        symbol: str,
        token: str,
        exchange: str = "NSE",
        interval: str = "FIVE_MINUTE",
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        days: int = 5,
        max_lookback: bool = False
    ) -> Optional[pd.DataFrame]:
        """Fetch historical data and save to CSV in one step.
        
        Convenience method that combines fetch and save operations.
        If the CSV doesn't exist and max_lookback=True, fetches maximum
        available data based on interval limits.
        
        Args:
            symbol: Trading symbol
            token: Instrument token
            exchange: Exchange name (default: NSE)
            interval: Candle interval (default: FIVE_MINUTE)
            from_date: Start date (optional)
            to_date: End date (optional)
            days: Number of days if from_date not specified (default: 5)
            max_lookback: If True and CSV doesn't exist, fetch max data for interval
            
        Returns:
            pd.DataFrame: Historical data, or None if operation fails
            
        Example:
            >>> hist_mgr = HistoricalDataManager()
            >>> # Fetch last 5 days
            >>> df = hist_mgr.fetch_and_save_historical_data(
            ...     symbol="NIFTY",
            ...     token="99926000",
            ...     interval="FIVE_MINUTE",
            ...     days=5
            ... )
            >>> 
            >>> # Fetch maximum available data for first time
            >>> df = hist_mgr.fetch_and_save_historical_data(
            ...     symbol="NIFTY",
            ...     token="99926000",
            ...     interval="FIVE_MINUTE",
            ...     max_lookback=True
            ... )
        """
        # Check if this is first-time fetch
        existing_df = self.load_historical_data(symbol, interval)
        
        if existing_df is None and max_lookback:
            # First time fetch - use maximum lookback for this interval
            max_days = self.MAX_LOOKBACK_DAYS.get(interval, days)
            self.logger.info(f"First-time fetch for {symbol} {interval}, using max lookback: {max_days} days")
            days = max_days
        
        # Fetch data
        df = self.fetch_historical_data(
            symbol=symbol,
            token=token,
            exchange=exchange,
            interval=interval,
            from_date=from_date,
            to_date=to_date,
            days=days
        )
        
        if df is None:
            return None
        
        # Save to CSV
        if self.save_to_csv(df, symbol, interval):
            return df
        else:
            return None
    
    def _is_market_hours(self) -> bool:
        """Check if current time is within Indian market hours (9:15 AM - 3:30 PM IST).
        
        Returns:
            bool: True if within market hours, False otherwise
        """
        from datetime import time
        
        now = datetime.now()
        current_time = now.time()
        
        # Market hours: 9:15 AM to 3:30 PM
        market_open = time(9, 15)
        market_close = time(15, 30)
        
        # Check if weekday (Monday=0, Sunday=6)
        is_weekday = now.weekday() < 5
        
        # Check if within time range
        is_within_hours = market_open <= current_time <= market_close
        
        return is_weekday and is_within_hours
    
    def _merge_and_deduplicate(
        self,
        existing_df: pd.DataFrame,
        new_df: pd.DataFrame
    ) -> pd.DataFrame:
        """Merge new data with existing data and remove duplicates.
        
        Args:
            existing_df: Existing DataFrame
            new_df: New DataFrame to merge
            
        Returns:
            pd.DataFrame: Merged and deduplicated DataFrame
        """
        try:
            # Combine dataframes
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
            
            # Remove duplicates based on timestamp, keeping last occurrence
            combined_df = combined_df.drop_duplicates(subset=['timestamp'], keep='last')
            
            # Sort by timestamp
            combined_df = combined_df.sort_values('timestamp').reset_index(drop=True)
            
            self.logger.debug(f"Merged data: {len(existing_df)} + {len(new_df)} = {len(combined_df)} (after deduplication)")
            
            return combined_df
            
        except Exception as e:
            self.logger.error(f"Error merging dataframes: {e}", exc_info=True)
            return existing_df
    
    def _get_last_complete_hour_window(self) -> datetime:
        """Calculate the last complete hour window based on current time.
        
        Market hours start at 9:15, so hour windows are:
        9:15-10:15, 10:15-11:15, 11:15-12:15, 12:15-13:15, 13:15-14:15, 14:15-15:15
        
        Examples:
            Current time 13:45 → Last complete window: 13:15
            Current time 10:10 → Last complete window: 9:15
            Current time 15:20 → Last complete window: 15:15 (end of day)
        
        Returns:
            datetime: Start time of the last complete hour window
        """
        from datetime import time
        
        now = datetime.now()
        current_time = now.time()
        
        # Define hour windows (start times)
        hour_windows = [
            time(9, 15),   # 9:15-10:15
            time(10, 15),  # 10:15-11:15
            time(11, 15),  # 11:15-12:15
            time(12, 15),  # 12:15-13:15
            time(13, 15),  # 13:15-14:15
            time(14, 15),  # 14:15-15:15
            time(15, 15),  # Last possible window
        ]
        
        # Find the last complete window
        last_complete = None
        for window_start in hour_windows:
            if current_time >= window_start:
                last_complete = datetime.combine(now.date(), window_start)
            else:
                break
        
        # If current time is before 9:15, use previous day's last window
        if last_complete is None:
            yesterday = now - timedelta(days=1)
            last_complete = datetime.combine(yesterday.date(), time(15, 15))
        
        return last_complete
    
    def _detect_late_start(self, symbol: str) -> tuple[bool, Optional[datetime], Optional[datetime]]:
        """Detect if script started late and calculate missing data window.
        
        Checks if existing 1-minute data is from a previous trading day and
        calculates the window of missing data that needs to be backfilled.
        
        Args:
            symbol: Trading symbol to check
            
        Returns:
            tuple: (needs_backfill, start_time, end_time)
                - needs_backfill: True if backfill is needed
                - start_time: Start of missing data window (market open 9:15)
                - end_time: End of missing data window (last complete hour or 15:30)
        """
        try:
            from datetime import time
            
            # Load existing 1-minute data
            existing_df = self.load_historical_data(symbol, "ONE_MINUTE")
            
            now = datetime.now()
            current_date = now.date()
            current_time = now.time()
            
            # If no existing data, no need for backfill (will be handled by initial fetch)
            if existing_df is None or len(existing_df) == 0:
                self.logger.info("No existing 1-minute data found, no backfill needed")
                return False, None, None
            
            # Get latest timestamp from existing data
            latest_timestamp = existing_df['timestamp'].max()
            latest_date = latest_timestamp.date()
            
            self.logger.info(f"Latest 1-minute data: {latest_timestamp}")
            self.logger.info(f"Current date/time: {now}")
            
            # Check if latest data is from a previous day
            if latest_date < current_date:
                self.logger.info(f"Late start detected! Latest data from {latest_date}, current date {current_date}")
                
                # Determine end time for backfill
                market_close = time(15, 30)
                
                if current_time > market_close:
                    # Script started after market close - backfill full day
                    start_time = datetime.combine(current_date, time(9, 15))
                    end_time = datetime.combine(current_date, market_close)
                    self.logger.info("Post-market start detected - will backfill full day")
                else:
                    # Script started during market hours - backfill to last complete hour
                    start_time = datetime.combine(current_date, time(9, 15))
                    end_time = self._get_last_complete_hour_window()
                    self.logger.info(f"Intraday start detected - will backfill to last complete hour window: {end_time}")
                
                return True, start_time, end_time
            else:
                # Latest data is from today, check if there's a gap
                time_since_last = now - latest_timestamp
                
                # If gap is more than 2 hours during market hours, might need backfill
                if time_since_last.total_seconds() > 7200 and self._is_market_hours():
                    self.logger.warning(f"Large gap detected ({time_since_last}) in today's data")
                    # Could implement gap-filling logic here if needed
                
                return False, None, None
                
        except Exception as e:
            self.logger.error(f"Error detecting late start: {e}", exc_info=True)
            return False, None, None
    
    def backfill_intraday_data(
        self,
        symbol: str,
        token: str,
        start_time: datetime,
        end_time: datetime,
        exchange: str = "NSE"
    ) -> Optional[pd.DataFrame]:
        """Fetch missing 1-minute data between start_time and end_time, then resample.
        
        This method handles late start scenarios where the script begins after market
        open and needs to backfill missing morning data. It fetches 1-minute data,
        merges with existing data, and automatically resamples to all higher timeframes.
        
        Features:
        - Fetches 1-minute data for specified time window
        - Merges with existing CSV data
        - Removes duplicates and sorts
        - Automatically resamples to 3min, 5min, 10min, 15min, 30min, 1H
        - Saves all resampled data to appropriate directories
        
        Args:
            symbol: Trading symbol (e.g., "NIFTY", "BANKNIFTY")
            token: Instrument token
            start_time: Start of backfill window (typically market open 9:15)
            end_time: End of backfill window (last complete hour or 15:30)
            exchange: Exchange name (default: NSE)
            
        Returns:
            pd.DataFrame: Updated 1-minute data with backfilled candles, or None if fails
            
        Example:
            >>> hist_mgr = HistoricalDataManager()
            >>> 
            >>> # Backfill from 9:15 to 13:15
            >>> from datetime import datetime
            >>> start = datetime(2024, 1, 15, 9, 15)
            >>> end = datetime(2024, 1, 15, 13, 15)
            >>> 
            >>> df = hist_mgr.backfill_intraday_data(
            ...     symbol="NIFTY",
            ...     token="99926000",
            ...     start_time=start,
            ...     end_time=end
            ... )
        """
        try:
            self.logger.info("="*60)
            self.logger.info("BACKFILLING MISSING INTRADAY DATA")
            self.logger.info("="*60)
            self.logger.info(f"Symbol: {symbol}")
            self.logger.info(f"Window: {start_time} → {end_time}")
            
            # Fetch 1-minute data for the missing window
            self.logger.info("Step 1: Fetching 1-minute data for missing window...")
            new_df = self.fetch_historical_data(
                symbol=symbol,
                token=token,
                exchange=exchange,
                interval="ONE_MINUTE",
                from_date=start_time,
                to_date=end_time
            )
            
            if new_df is None or len(new_df) == 0:
                self.logger.error("Failed to fetch backfill data from API")
                return None
            
            self.logger.info(f"✓ Fetched {len(new_df)} 1-minute candles")
            
            # Load existing 1-minute data
            existing_df = self.load_historical_data(symbol, "ONE_MINUTE")
            
            # Merge with existing data
            if existing_df is not None and len(existing_df) > 0:
                self.logger.info("Step 2: Merging with existing 1-minute data...")
                combined_df = self._merge_and_deduplicate(existing_df, new_df)
                new_candles = len(combined_df) - len(existing_df)
                self.logger.info(f"✓ Merged: added {new_candles} new candles, total: {len(combined_df)}")
            else:
                self.logger.info("No existing 1-minute data, using backfilled data as base")
                combined_df = new_df
            
            # Save updated 1-minute data
            self.logger.info("Step 3: Saving updated 1-minute data...")
            if not self.save_to_csv(combined_df, symbol, "ONE_MINUTE"):
                self.logger.error("Failed to save backfilled 1-minute data")
                return None
            
            self.logger.info(f"✓ Saved {len(combined_df)} 1-minute candles to CSV")
            
            # Resample to all higher timeframes
            self.logger.info("Step 4: Resampling to higher timeframes...")
            
            from modules.data_module import get_data_processor
            processor = get_data_processor()
            
            results = processor.update_resampled_data(symbol, combined_df)
            
            # Log results
            success_count = sum(1 for v in results.values() if v)
            total_count = len(results)
            
            self.logger.info(f"✓ Resampling complete: {success_count}/{total_count} timeframes successful")
            
            for timeframe, success in results.items():
                status = "✓" if success else "✗"
                self.logger.info(f"  {status} {timeframe}")
            
            self.logger.info("="*60)
            self.logger.info("BACKFILL COMPLETE")
            self.logger.info("="*60)
            
            return combined_df
            
        except Exception as e:
            self.logger.error(f"Error backfilling intraday data: {e}", exc_info=True)
            return None
    
    def update_historical_data(
        self,
        symbol: str,
        token: str,
        exchange: str = "NSE",
        interval: str = "FIVE_MINUTE"
    ) -> Optional[pd.DataFrame]:
        """Update existing historical data with latest candles (incremental update).
        
        Enhanced incremental update logic:
        - Detects latest timestamp from existing CSV
        - Fetches only missing candles from last timestamp to current time
        - Merges new data with existing data
        - Removes duplicates and sorts by timestamp
        - Saves updated data back to CSV
        
        Args:
            symbol: Trading symbol
            token: Instrument token
            exchange: Exchange name (default: NSE)
            interval: Candle interval (default: FIVE_MINUTE)
            
        Returns:
            pd.DataFrame: Updated historical data, or None if operation fails
            
        Example:
            >>> hist_mgr = HistoricalDataManager()
            >>> # Update with latest data (incremental)
            >>> df = hist_mgr.update_historical_data("NIFTY", "99926000")
            >>> print(f"Total candles: {len(df)}")
        """
        try:
            # Load existing data
            existing_df = self.load_historical_data(symbol, interval)
            
            if existing_df is None or len(existing_df) == 0:
                # No existing data, fetch fresh with max lookback
                self.logger.info("No existing data found, fetching fresh data with max lookback")
                return self.fetch_and_save_historical_data(
                    symbol=symbol,
                    token=token,
                    exchange=exchange,
                    interval=interval,
                    max_lookback=True
                )
            
            # Get last timestamp from existing data
            last_timestamp = existing_df['timestamp'].max()
            current_time = datetime.now()
            
            self.logger.info(f"Last timestamp in CSV: {last_timestamp}")
            self.logger.info(f"Current time: {current_time}")
            
            # Check if update is needed
            time_diff = current_time - last_timestamp
            self.logger.info(f"Time difference: {time_diff}")
            
            # If last timestamp is today and very recent (less than interval), skip update
            if time_diff.total_seconds() < 60:  # Less than 1 minute
                self.logger.info("Data is already up-to-date (less than 1 minute old)")
                return existing_df
            
            # Fetch new data from last timestamp to now
            self.logger.info(f"Fetching incremental data from {last_timestamp} to {current_time}")
            
            new_df = self.fetch_historical_data(
                symbol=symbol,
                token=token,
                exchange=exchange,
                interval=interval,
                from_date=last_timestamp,
                to_date=current_time
            )
            
            if new_df is None or len(new_df) == 0:
                self.logger.info("No new data available from API")
                return existing_df
            
            # Filter out overlapping candles (keep only newer than last timestamp)
            new_df = new_df[new_df['timestamp'] > last_timestamp]
            
            if len(new_df) == 0:
                self.logger.info("No new candles after filtering overlaps")
                return existing_df
            
            self.logger.info(f"Fetched {len(new_df)} new candles")
            
            # Merge and deduplicate
            combined_df = self._merge_and_deduplicate(existing_df, new_df)
            
            # Save updated data
            if self.save_to_csv(combined_df, symbol, interval):
                self.logger.info(f"Successfully updated: added {len(new_df)} new candles, total: {len(combined_df)}")
                return combined_df
            else:
                self.logger.error("Failed to save updated data")
                return None
                
        except Exception as e:
            self.logger.error(f"Error updating historical data: {e}", exc_info=True)
            return None
    
    def update_intraday_data(
        self,
        symbol: str,
        token: str,
        exchange: str = "NSE",
        lookback_minutes: int = 60,
        auto_backfill: bool = True
    ) -> Optional[pd.DataFrame]:
        """Update 1-minute intraday data during market hours with automatic late-start backfill.
        
        This method is designed to be called hourly during market hours (9:15 AM - 3:30 PM).
        It fetches the last N minutes of 1-minute candle data and merges with existing data.
        
        Enhanced Features:
        - Detects late start (script started after market open)
        - Automatically backfills missing morning data if needed
        - Fetches last 60 minutes of 1-minute data by default
        - Merges with existing CSV data
        - Removes duplicates automatically
        - Saves updated data back to CSV
        - Resamples to all higher timeframes when backfilling
        
        Late Start Handling:
        - If existing data is from previous day and current time is < 15:30:
          Backfills from 9:15 to last complete hour window
        - If existing data is from previous day and current time is > 15:30:
          Backfills full day from 9:15 to 15:30
        - After backfill, continues with normal hourly update
        
        Args:
            symbol: Trading symbol
            token: Instrument token
            exchange: Exchange name (default: NSE)
            lookback_minutes: Minutes to look back for normal updates (default: 60)
            auto_backfill: Enable automatic late-start backfilling (default: True)
            
        Returns:
            pd.DataFrame: Updated 1-minute data, or None if operation fails
            
        Example:
            >>> hist_mgr = HistoricalDataManager()
            >>> 
            >>> # Update 1-minute data (call this hourly during market hours)
            >>> # Automatically handles late start if script began after 9:15
            >>> df = hist_mgr.update_intraday_data("NIFTY", "99926000")
            >>> 
            >>> # Custom lookback period
            >>> df = hist_mgr.update_intraday_data("NIFTY", "99926000", lookback_minutes=120)
            >>> 
            >>> # Disable auto-backfill if needed
            >>> df = hist_mgr.update_intraday_data("NIFTY", "99926000", auto_backfill=False)
        """
        try:
            interval = "ONE_MINUTE"
            
            # STEP 1: Check for late start and backfill if needed
            if auto_backfill:
                needs_backfill, start_time, end_time = self._detect_late_start(symbol)
                
                if needs_backfill:
                    self.logger.warning("⚠ Late start detected! Initiating automatic backfill...")
                    
                    # Perform backfill
                    backfill_result = self.backfill_intraday_data(
                        symbol=symbol,
                        token=token,
                        start_time=start_time,
                        end_time=end_time,
                        exchange=exchange
                    )
                    
                    if backfill_result is None:
                        self.logger.error("Backfill failed, continuing with normal update")
                    else:
                        self.logger.info("✓ Backfill successful, data is now up to date")
                        
                        # If we backfilled to current time or past market close, we're done
                        if end_time >= datetime.now() or end_time.time() >= datetime.strptime("15:30", "%H:%M").time():
                            self.logger.info("Backfill covered current time, no additional update needed")
                            return backfill_result
            
            # STEP 2: Normal intraday update logic
            # Check if within market hours
            if not self._is_market_hours():
                self.logger.warning("Not within market hours (9:15 AM - 3:30 PM IST), skipping intraday update")
                # Still return existing data if available
                return self.load_historical_data(symbol, interval)
            
            self.logger.info(f"Updating intraday 1-minute data for {symbol}")
            self.logger.info(f"Lookback period: {lookback_minutes} minutes")
            
            # Load existing data
            existing_df = self.load_historical_data(symbol, interval)
            
            # Calculate from_date (lookback_minutes ago)
            current_time = datetime.now()
            from_date = current_time - timedelta(minutes=lookback_minutes)
            
            self.logger.info(f"Fetching 1-minute data from {from_date} to {current_time}")
            
            # Fetch recent 1-minute data
            new_df = self.fetch_historical_data(
                symbol=symbol,
                token=token,
                exchange=exchange,
                interval=interval,
                from_date=from_date,
                to_date=current_time
            )
            
            if new_df is None or len(new_df) == 0:
                self.logger.warning("No new intraday data fetched from API")
                return existing_df
            
            self.logger.info(f"Fetched {len(new_df)} recent 1-minute candles")
            
            # If no existing data, save and return new data
            if existing_df is None or len(existing_df) == 0:
                self.logger.info("No existing 1-minute data, saving fresh data")
                if self.save_to_csv(new_df, symbol, interval):
                    return new_df
                else:
                    return None
            
            # Merge and deduplicate
            combined_df = self._merge_and_deduplicate(existing_df, new_df)
            
            # Save updated data
            if self.save_to_csv(combined_df, symbol, interval):
                new_candles = len(combined_df) - len(existing_df)
                self.logger.info(f"Intraday update successful: added {new_candles} new candles, total: {len(combined_df)}")
                return combined_df
            else:
                self.logger.error("Failed to save updated intraday data")
                return None
                
        except Exception as e:
            self.logger.error(f"Error updating intraday data: {e}", exc_info=True)
            return None
    
    def get_available_data_files(self) -> List[Dict[str, str]]:
        """Get list of available historical data CSV files.
        
        Returns:
            list: List of dicts with 'symbol', 'interval', 'filepath' keys
            
        Example:
            >>> hist_mgr = HistoricalDataManager()
            >>> files = hist_mgr.get_available_data_files()
            >>> for f in files:
            ...     print(f"{f['symbol']} - {f['interval']}: {f['filepath']}")
        """
        try:
            csv_files = []
            
            # Iterate through subdirectories
            for subdir in self.data_dir.iterdir():
                if subdir.is_dir():
                    # Look for CSV files in subdirectory
                    for filepath in subdir.glob("*.csv"):
                        # Parse filename: SYMBOL_INTERVAL.csv
                        parts = filepath.stem.split('_', 1)
                        if len(parts) == 2:
                            csv_files.append({
                                'symbol': parts[0],
                                'interval': parts[1],
                                'filepath': str(filepath)
                            })
            
            return csv_files
            
        except Exception as e:
            self.logger.error(f"Error listing data files: {e}", exc_info=True)
            return []
    
    def initialize_instrument_data(
        self,
        symbol: str,
        token: str,
        exchange: str = "NSE",
        intervals: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """Initialize historical data for an instrument across all intervals.
        
        This method checks if data exists for each interval. If not, it fetches
        the maximum available lookback period for that interval and saves it.
        
        Args:
            symbol: Trading symbol (e.g., "NIFTY", "BANKNIFTY")
            token: Instrument token
            exchange: Exchange name (default: NSE)
            intervals: List of intervals to initialize (default: all supported intervals)
            
        Returns:
            dict: Dictionary with interval as key and success status (bool) as value
            
        Example:
            >>> hist_mgr = HistoricalDataManager()
            >>> 
            >>> # Initialize all intervals for NIFTY
            >>> results = hist_mgr.initialize_instrument_data(
            ...     symbol="NIFTY",
            ...     token="99926000",
            ...     exchange="NSE"
            ... )
            >>> 
            >>> for interval, success in results.items():
            ...     if success:
            ...         print(f"✓ {interval}: Data initialized")
            ...     else:
            ...         print(f"✗ {interval}: Initialization failed")
            >>> 
            >>> # Initialize only specific intervals
            >>> results = hist_mgr.initialize_instrument_data(
            ...     symbol="NIFTY",
            ...     token="99926000",
            ...     intervals=["FIVE_MINUTE", "FIFTEEN_MINUTE", "ONE_DAY"]
            ... )
        """
        try:
            # Use all intervals if not specified
            if intervals is None:
                intervals = list(self.INTERVALS.keys())
            
            results = {}
            
            self.logger.info(f"Initializing instrument data for {symbol}")
            self.logger.info(f"Exchange: {exchange}, Token: {token}")
            self.logger.info(f"Intervals to initialize: {intervals}")
            
            for interval in intervals:
                # Validate interval
                if interval not in self.INTERVALS:
                    self.logger.warning(f"Invalid interval: {interval}, skipping")
                    results[interval] = False
                    continue
                
                # Check if data already exists
                existing_df = self.load_historical_data(symbol, interval)
                
                if existing_df is not None:
                    self.logger.info(f"✓ {interval}: Data already exists ({len(existing_df)} candles)")
                    results[interval] = True
                    continue
                
                # Data doesn't exist, fetch maximum lookback
                max_days = self.MAX_LOOKBACK_DAYS.get(interval, 5)
                self.logger.info(f"⬇ {interval}: Fetching {max_days} days of data...")
                
                df = self.fetch_and_save_historical_data(
                    symbol=symbol,
                    token=token,
                    exchange=exchange,
                    interval=interval,
                    days=max_days,
                    max_lookback=True
                )
                
                if df is not None:
                    self.logger.info(f"✓ {interval}: Successfully fetched and saved {len(df)} candles")
                    results[interval] = True
                else:
                    self.logger.error(f"✗ {interval}: Failed to fetch data")
                    results[interval] = False
            
            # Summary
            success_count = sum(1 for v in results.values() if v)
            total_count = len(results)
            self.logger.info(f"Initialization complete: {success_count}/{total_count} intervals successful")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error initializing instrument data: {e}", exc_info=True)
            return {interval: False for interval in (intervals or list(self.INTERVALS.keys()))}
