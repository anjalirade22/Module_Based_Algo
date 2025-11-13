"""Data processing and caching utilities.

This module provides utilities for processing and caching market data.
It includes functionality for data validation, transformation, and
caching to improve performance.

Key Features:
    - Data validation and cleaning
    - Caching frequently accessed data
    - Data format conversions
    - Data resampling
    - Data quality checks

Usage:
    from modules.data_module import get_data_processor
    
    processor = get_data_processor()
    
    # Validate data
    is_valid = processor.validate_candle_data(df)
    
    # Clean and process data
    df_clean = processor.clean_candle_data(df)
"""

import pandas as pd
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from modules.logger_module import get_logger

# Global instance
_data_processor_instance = None

def get_data_processor():
    """Get singleton instance of DataProcessor.
    
    Returns:
        DataProcessor: The singleton processor instance
    """
    global _data_processor_instance
    if _data_processor_instance is None:
        _data_processor_instance = DataProcessor()
    return _data_processor_instance


class DataProcessor:
    """Utilities for processing and caching market data.
    
    This class provides various data processing utilities including
    validation, caching, transformations, and resampling.
    
    Attributes:
        cache_dir (Path): Directory for cached data
        cache (dict): In-memory cache
        logger: Logger instance
        MARKET_OPEN (str): Market opening time (09:15)
        MARKET_CLOSE (str): Market closing time (15:30)
        
    Example:
        >>> processor = DataProcessor()
        >>> 
        >>> # Validate data
        >>> if processor.validate_candle_data(df):
        ...     print("Data is valid")
        >>> 
        >>> # Clean and resample data
        >>> df_clean = processor.clean_candle_data(df)
        >>> df_5min = processor.resample_data(df, target_interval='5min')
    """
    
    # Market hours configuration (IST)
    MARKET_OPEN = "09:15"
    MARKET_CLOSE = "15:30"
    
    def __init__(self, cache_dir: str = "data/cache"):
        """Initialize DataProcessor.
        
        Args:
            cache_dir: Directory for cached data (default: data/cache)
        """
        self.logger = get_logger(__name__)
        
        # Setup cache directory
        project_root = Path(__file__).parent.parent.parent
        self.cache_dir = project_root / cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory cache
        self.cache: Dict[str, Any] = {}
        
        self.logger.info(f"DataProcessor initialized, cache dir: {self.cache_dir}")
    
    def validate_candle_data(self, df: pd.DataFrame) -> bool:
        """Validate candle data DataFrame.
        
        Checks if DataFrame has required columns and valid data.
        
        Args:
            df: DataFrame to validate
            
        Returns:
            bool: True if valid, False otherwise
            
        Example:
            >>> processor = DataProcessor()
            >>> if processor.validate_candle_data(df):
            ...     print("Data is valid")
            ... else:
            ...     print("Data validation failed")
        """
        try:
            if df is None or len(df) == 0:
                self.logger.error("DataFrame is None or empty")
                return False
            
            # Check required columns
            required_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                self.logger.error(f"Missing required columns: {missing_cols}")
                return False
            
            # Check for NaN values
            if df[required_cols].isnull().any().any():
                self.logger.warning("DataFrame contains NaN values")
                return False
            
            # Validate OHLC relationships
            invalid_rows = df[
                (df['high'] < df['low']) |
                (df['high'] < df['open']) |
                (df['high'] < df['close']) |
                (df['low'] > df['open']) |
                (df['low'] > df['close'])
            ]
            
            if len(invalid_rows) > 0:
                self.logger.error(f"Found {len(invalid_rows)} rows with invalid OHLC relationships")
                return False
            
            self.logger.debug("DataFrame validation passed")
            return True
            
        except Exception as e:
            self.logger.error(f"Error validating DataFrame: {e}", exc_info=True)
            return False
    
    def clean_candle_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean candle data by removing duplicates and sorting.
        
        Args:
            df: DataFrame to clean
            
        Returns:
            pd.DataFrame: Cleaned DataFrame
            
        Example:
            >>> processor = DataProcessor()
            >>> df_clean = processor.clean_candle_data(df)
        """
        try:
            # Remove duplicates based on timestamp
            df = df.drop_duplicates(subset=['timestamp'], keep='last')
            
            # Sort by timestamp
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # Remove any rows with NaN
            df = df.dropna()
            
            self.logger.debug(f"Cleaned data: {len(df)} rows")
            return df
            
        except Exception as e:
            self.logger.error(f"Error cleaning data: {e}", exc_info=True)
            return df
    
    def filter_market_hours(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter candle data to only include candles within market hours.
        
        Removes any candles with timestamps after market close (15:30).
        This ensures that resampling operations only work with valid
        market data.
        
        Args:
            df: DataFrame with timestamp column
            
        Returns:
            pd.DataFrame: Filtered DataFrame with only market hours data
            
        Example:
            >>> processor = DataProcessor()
            >>> df_filtered = processor.filter_market_hours(df)
            >>> # All candles after 15:30 are removed
        """
        try:
            # Make a copy to avoid modifying original
            df = df.copy()
            
            # Ensure timestamp is datetime
            if df['timestamp'].dtype != 'datetime64[ns]':
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Extract time component
            df_time = df['timestamp'].dt.time
            
            # Parse market close time
            close_time = pd.to_datetime(self.MARKET_CLOSE, format='%H:%M').time()
            
            # Filter: keep only candles at or before market close
            df_filtered = df[df_time <= close_time].copy()
            
            removed_count = len(df) - len(df_filtered)
            if removed_count > 0:
                self.logger.info(f"Filtered out {removed_count} candles after market close ({self.MARKET_CLOSE})")
            
            return df_filtered
            
        except Exception as e:
            self.logger.error(f"Error filtering market hours: {e}", exc_info=True)
            return df
    
    def cache_data(self, key: str, data: Any, ttl_seconds: int = 300) -> bool:
        """Cache data with time-to-live.
        
        Args:
            key: Cache key
            data: Data to cache
            ttl_seconds: Time to live in seconds (default: 300 = 5 minutes)
            
        Returns:
            bool: True if cached successfully, False otherwise
            
        Example:
            >>> processor = DataProcessor()
            >>> processor.cache_data("nifty_data", df, ttl_seconds=300)
        """
        try:
            expiry = datetime.now() + timedelta(seconds=ttl_seconds)
            
            self.cache[key] = {
                'data': data,
                'expiry': expiry
            }
            
            self.logger.debug(f"Cached data with key: {key}, TTL: {ttl_seconds}s")
            return True
            
        except Exception as e:
            self.logger.error(f"Error caching data: {e}", exc_info=True)
            return False
    
    def get_cached_data(self, key: str) -> Optional[Any]:
        """Get cached data if not expired.
        
        Args:
            key: Cache key
            
        Returns:
            Any: Cached data, or None if not found or expired
            
        Example:
            >>> processor = DataProcessor()
            >>> df = processor.get_cached_data("nifty_data")
            >>> if df is not None:
            ...     print("Using cached data")
        """
        try:
            if key not in self.cache:
                return None
            
            cached = self.cache[key]
            
            # Check expiry
            if datetime.now() > cached['expiry']:
                self.logger.debug(f"Cache expired for key: {key}")
                del self.cache[key]
                return None
            
            self.logger.debug(f"Cache hit for key: {key}")
            return cached['data']
            
        except Exception as e:
            self.logger.error(f"Error getting cached data: {e}", exc_info=True)
            return None
    
    def clear_cache(self, key: Optional[str] = None):
        """Clear cache.
        
        Args:
            key: Specific key to clear, or None to clear all (default: None)
            
        Example:
            >>> processor = DataProcessor()
            >>> # Clear specific key
            >>> processor.clear_cache("nifty_data")
            >>> # Clear all cache
            >>> processor.clear_cache()
        """
        try:
            if key is None:
                self.cache.clear()
                self.logger.info("Cleared all cache")
            elif key in self.cache:
                del self.cache[key]
                self.logger.info(f"Cleared cache for key: {key}")
            
        except Exception as e:
            self.logger.error(f"Error clearing cache: {e}", exc_info=True)
    
    def save_cache_to_disk(self, filename: str = "cache.json") -> bool:
        """Save in-memory cache to disk.
        
        Args:
            filename: Cache file name (default: cache.json)
            
        Returns:
            bool: True if saved successfully, False otherwise
        """
        try:
            filepath = self.cache_dir / filename
            
            # Convert cache to serializable format
            cache_data = {}
            for key, value in self.cache.items():
                cache_data[key] = {
                    'data': value['data'],
                    'expiry': value['expiry'].isoformat()
                }
            
            with open(filepath, 'w') as f:
                json.dump(cache_data, f, indent=2, default=str)
            
            self.logger.info(f"Saved cache to {filepath}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving cache to disk: {e}", exc_info=True)
            return False
    
    def load_cache_from_disk(self, filename: str = "cache.json") -> bool:
        """Load cache from disk.
        
        Args:
            filename: Cache file name (default: cache.json)
            
        Returns:
            bool: True if loaded successfully, False otherwise
        """
        try:
            filepath = self.cache_dir / filename
            
            if not filepath.exists():
                self.logger.warning(f"Cache file not found: {filepath}")
                return False
            
            with open(filepath, 'r') as f:
                cache_data = json.load(f)
            
            # Convert to cache format
            for key, value in cache_data.items():
                expiry = datetime.fromisoformat(value['expiry'])
                
                # Only load non-expired entries
                if datetime.now() <= expiry:
                    self.cache[key] = {
                        'data': value['data'],
                        'expiry': expiry
                    }
            
            self.logger.info(f"Loaded {len(self.cache)} cache entries from {filepath}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading cache from disk: {e}", exc_info=True)
            return False
    
    def resample_data(self, df: pd.DataFrame, target_interval: str = '5min') -> pd.DataFrame:
        """Resample candle data to different timeframe.
        
        Uses pandas resample with label='left' to ensure timestamp represents
        the start of the candle period. Filters out candles after market close
        but retains all candles including partial ones for complete data coverage.
        
        Args:
            df: DataFrame with OHLC data (must have timestamp column)
            target_interval: Target interval (e.g., '5min', '15min', '30min', '1H')
            
        Returns:
            pd.DataFrame: Resampled DataFrame with timestamp as start of candle
            
        Example:
            >>> processor = DataProcessor()
            >>> # Resample 1-minute data to 5-minute
            >>> df_5min = processor.resample_data(df, target_interval='5min')
            >>> # Timestamp will be start of candle (e.g., 9:15 for 9:15-9:20 candle)
            >>> # All candles are retained including partial ones at end of day
        """
        try:
            # Make a copy to avoid modifying original
            df = df.copy()
            
            # Ensure timestamp is datetime
            if df['timestamp'].dtype != 'datetime64[ns]':
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Filter out any candles after market close
            df = self.filter_market_hours(df)
            
            if len(df) == 0:
                self.logger.warning("No data left after filtering market hours")
                return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Set timestamp as index
            df = df.set_index('timestamp')
            
            # Resample with label='left' to use start of period as timestamp
            resampled = df.resample(target_interval, label='left').agg({
                'open': 'first',
                'high': 'max',
                'low': 'min',
                'close': 'last',
                'volume': 'sum'
            })
            
            # Remove any NaN rows (incomplete candles)
            resampled = resampled.dropna()
            
            # Reset index to make timestamp a column again
            resampled = resampled.reset_index()
            
            self.logger.debug(f"Resampled to {target_interval}: {len(resampled)} candles")
            return resampled
            
        except Exception as e:
            self.logger.error(f"Error resampling data: {e}", exc_info=True)
            return df
    
    def update_resampled_data(
        self,
        symbol: str,
        df_1min: pd.DataFrame,
        timeframes: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """Automatically resample 1-minute data into multiple timeframes and save to CSV.
        
        This method takes 1-minute candle data and creates resampled versions
        for all supported timeframes. Each resampled DataFrame is saved in its 
        own directory structure.
        
        Directory structure created:
            data/historical/{SYMBOL}_THREE_MINUTE/{SYMBOL}_THREE_MINUTE.csv
            data/historical/{SYMBOL}_FIVE_MINUTE/{SYMBOL}_FIVE_MINUTE.csv
            data/historical/{SYMBOL}_TEN_MINUTE/{SYMBOL}_TEN_MINUTE.csv
            data/historical/{SYMBOL}_FIFTEEN_MINUTE/{SYMBOL}_FIFTEEN_MINUTE.csv
            data/historical/{SYMBOL}_THIRTY_MINUTE/{SYMBOL}_THIRTY_MINUTE.csv
            data/historical/{SYMBOL}_ONE_HOUR/{SYMBOL}_ONE_HOUR.csv
        
        Timestamp rules (label='left'):
            - 1-hour candle from 9:15–10:15 → timestamp = 9:15
            - 30-min candle from 9:15–9:45 → timestamp = 9:15
            - 15-min candle from 9:15–9:30 → timestamp = 9:15
            - 10-min candle from 9:15–9:25 → timestamp = 9:15
            - 5-min candle from 9:15–9:20 → timestamp = 9:15
            - 3-min candle from 9:15–9:18 → timestamp = 9:15
        
        Args:
            symbol: Trading symbol (e.g., "NIFTY", "BANKNIFTY")
            df_1min: DataFrame with 1-minute OHLC data
            timeframes: List of timeframes to generate (default: all supported timeframes)
            
        Returns:
            dict: Dictionary with timeframe as key and success status (bool) as value
            
        Example:
            >>> processor = DataProcessor()
            >>> 
            >>> # Load 1-minute data
            >>> df_1min = hist_mgr.load_historical_data("NIFTY", "ONE_MINUTE")
            >>> 
            >>> # Automatically create all resampled timeframes
            >>> results = processor.update_resampled_data("NIFTY", df_1min)
            >>> 
            >>> for timeframe, success in results.items():
            ...     if success:
            ...         print(f"✓ {timeframe}: Successfully created")
            ...     else:
            ...         print(f"✗ {timeframe}: Failed")
            >>> 
            >>> # Custom timeframes
            >>> results = processor.update_resampled_data(
            ...     symbol="BANKNIFTY",
            ...     df_1min=df_1min,
            ...     timeframes=['5min', '15min', '1H']
            ... )
        """
        try:
            # Complete timeframes mapping for all supported intervals
            timeframe_map = {
                '3min': 'THREE_MINUTE',
                '5min': 'FIVE_MINUTE',
                '10min': 'TEN_MINUTE',
                '15min': 'FIFTEEN_MINUTE',
                '30min': 'THIRTY_MINUTE',
                '1H': 'ONE_HOUR'
            }
            
            # Use all timeframes if not specified
            if timeframes is None:
                timeframes = ['3min', '5min', '10min', '15min', '30min', '1H']
            
            results = {}
            
            # Validate input data
            if df_1min is None or len(df_1min) == 0:
                self.logger.error("Input 1-minute DataFrame is None or empty")
                return {tf: False for tf in timeframes}
            
            if not self.validate_candle_data(df_1min):
                self.logger.error("Input 1-minute data validation failed")
                return {tf: False for tf in timeframes}
            
            self.logger.info(f"Starting automated resampling for {symbol}")
            self.logger.info(f"Input: {len(df_1min)} 1-minute candles")
            self.logger.info(f"Timeframes to generate: {timeframes}")
            
            # Get project root for data directory
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / "data" / "historical"
            
            # Resample and save each timeframe
            for timeframe in timeframes:
                try:
                    # Get interval name for directory/filename
                    interval_name = timeframe_map.get(timeframe)
                    
                    if interval_name is None:
                        self.logger.warning(f"Unknown timeframe: {timeframe}, skipping")
                        results[timeframe] = False
                        continue
                    
                    self.logger.info(f"⬇ Resampling to {timeframe} ({interval_name})...")
                    
                    # Resample data
                    df_resampled = self.resample_data(df_1min.copy(), target_interval=timeframe)
                    
                    if df_resampled is None or len(df_resampled) == 0:
                        self.logger.error(f"Resampling to {timeframe} produced empty result")
                        results[timeframe] = False
                        continue
                    
                    # Create subdirectory
                    subdir_name = f"{symbol}_{interval_name}"
                    subdir = data_dir / subdir_name
                    subdir.mkdir(parents=True, exist_ok=True)
                    
                    # Create filename
                    filename = f"{symbol}_{interval_name}.csv"
                    filepath = subdir / filename
                    
                    # Save to CSV
                    df_resampled.to_csv(filepath, index=False)
                    
                    self.logger.info(f"✓ {timeframe}: Saved {len(df_resampled)} candles to {filepath}")
                    results[timeframe] = True
                    
                except Exception as e:
                    self.logger.error(f"Error resampling {timeframe}: {e}", exc_info=True)
                    results[timeframe] = False
            
            # Summary
            success_count = sum(1 for v in results.values() if v)
            total_count = len(results)
            self.logger.info(f"Resampling complete: {success_count}/{total_count} timeframes successful")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error in automated resampling pipeline: {e}", exc_info=True)
            return {tf: False for tf in (timeframes or ['3min', '5min', '10min', '15min', '30min', '1H'])}
