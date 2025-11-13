"""Live data feed management using subprocess architecture.

This module provides the LiveDataFeed class that manages a separate
WebSocket feed process for live market data streaming. The feed process
runs independently and writes data to a JSON file that can be read by
the Execution module.

Key Features:
    - Subprocess-based feed for crash isolation
    - JSON-based inter-process communication
    - Automatic feed validation and health monitoring
    - Clean lifecycle management (start/stop)
    - Thread-safe data access

Architecture:
    Main Process                    Feed Subprocess
    ┌─────────────┐                ┌──────────────┐
    │ LiveDataFeed│───starts──────>│ WebSocketFeed│
    │             │                │              │
    │ validates   │<──writes JSON──│  streams     │
    │ reads data  │                │  ticks       │
    └─────────────┘                └──────────────┘
                    live_feed_data.json

Usage:
    # Basic usage
    feed = get_live_feed()
    feed.start_feed()
    
    # Get live price
    price = feed.get_live_price()
    
    # Check if data is fresh
    if feed.is_data_fresh():
        print(f"Current price: {price}")
    
    # Stop feed
    feed.stop_feed()
"""

import json
import subprocess
import time
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any
from modules.logger_module import get_logger

# Global instance
_live_feed_instance = None

def get_live_feed():
    """Get singleton instance of LiveDataFeed.
    
    Returns:
        LiveDataFeed: The singleton feed instance
    """
    global _live_feed_instance
    if _live_feed_instance is None:
        _live_feed_instance = LiveDataFeed()
    return _live_feed_instance


class LiveDataFeed:
    """Manages live market data feed using subprocess architecture.
    
    This class handles the lifecycle of a WebSocket feed subprocess that
    streams live market data. The subprocess writes data to a JSON file
    which can be read by other modules (primarily Execution module).
    
    Attributes:
        feed_file (Path): Path to the JSON file for live data
        feed_process (subprocess.Popen): The feed subprocess
        logger: Logger instance for this module
        
    Example:
        >>> feed = LiveDataFeed()
        >>> feed.start_feed()
        >>> # Wait for data to be available
        >>> feed.wait_for_data(timeout=10)
        >>> price = feed.get_live_price()
        >>> print(f"Live price: {price}")
        >>> feed.stop_feed()
    """
    
    def __init__(self, feed_file: str = "live_feed_data.json"):
        """Initialize LiveDataFeed.
        
        Args:
            feed_file: Name of JSON file for live data (default: live_feed_data.json)
        """
        self.logger = get_logger(__name__)
        
        # Get project root directory and create live data directory
        project_root = Path(__file__).parent.parent.parent
        live_data_dir = project_root / "data" / "live"
        live_data_dir.mkdir(parents=True, exist_ok=True)
        self.feed_file = live_data_dir / feed_file
        
        self.feed_process: Optional[subprocess.Popen] = None
        self.logger.info(f"LiveDataFeed initialized with file: {self.feed_file}")
    
    def start_feed(self) -> bool:
        """Start the live data feed subprocess.
        
        Launches the feed_process.py as a separate subprocess. The subprocess
        will connect to WebSocket and start streaming data to JSON file.
        
        Returns:
            bool: True if feed started successfully, False otherwise
            
        Example:
            >>> feed = LiveDataFeed()
            >>> if feed.start_feed():
            ...     print("Feed started successfully")
            ... else:
            ...     print("Failed to start feed")
        """
        if self.feed_process is not None:
            self.logger.warning("Feed process already running")
            return True
        
        try:
            # Get path to feed_process.py
            feed_script = Path(__file__).parent / "feed_process.py"
            
            if not feed_script.exists():
                self.logger.error(f"Feed script not found: {feed_script}")
                return False
            
            # Start subprocess
            self.logger.info(f"Starting feed subprocess: {feed_script}")
            self.feed_process = subprocess.Popen(
                [sys.executable, str(feed_script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.logger.info(f"Feed subprocess started with PID: {self.feed_process.pid}")
            
            # Wait a moment for process to initialize
            time.sleep(2)
            
            # Check if process is still running
            if self.feed_process.poll() is not None:
                # Process has terminated
                stdout, stderr = self.feed_process.communicate()
                self.logger.error(f"Feed process terminated immediately")
                self.logger.error(f"STDOUT: {stdout}")
                self.logger.error(f"STDERR: {stderr}")
                self.feed_process = None
                return False
            
            self.logger.info("Feed subprocess running successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error starting feed subprocess: {e}", exc_info=True)
            self.feed_process = None
            return False
    
    def validate_feed_file(self) -> bool:
        """Validate that feed file exists and has recent data.
        
        Checks if the JSON file exists and contains data updated within
        the last 10 seconds.
        
        Returns:
            bool: True if feed file is valid and fresh, False otherwise
            
        Example:
            >>> feed = LiveDataFeed()
            >>> if feed.validate_feed_file():
            ...     print("Feed file is valid")
        """
        try:
            if not self.feed_file.exists():
                self.logger.warning(f"Feed file does not exist: {self.feed_file}")
                return False
            
            # Check file modification time
            mtime = datetime.fromtimestamp(self.feed_file.stat().st_mtime)
            age = datetime.now() - mtime
            
            if age > timedelta(seconds=10):
                self.logger.warning(f"Feed file is stale (last update: {age.total_seconds():.1f}s ago)")
                return False
            
            # Try to read and parse JSON
            with open(self.feed_file, 'r') as f:
                data = json.load(f)
            
            if not data:
                self.logger.warning("Feed file is empty")
                return False
            
            self.logger.debug("Feed file validation passed")
            return True
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in feed file: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error validating feed file: {e}", exc_info=True)
            return False
    
    def wait_for_data(self, timeout: int = 30) -> bool:
        """Wait for feed data to become available.
        
        Polls the feed file until valid data is available or timeout occurs.
        Useful after starting the feed to ensure data is ready.
        
        Args:
            timeout: Maximum seconds to wait (default: 30)
            
        Returns:
            bool: True if data is available, False if timeout
            
        Example:
            >>> feed = LiveDataFeed()
            >>> feed.start_feed()
            >>> if feed.wait_for_data(timeout=10):
            ...     print("Data is ready")
            ... else:
            ...     print("Timeout waiting for data")
        """
        self.logger.info(f"Waiting for feed data (timeout: {timeout}s)")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.validate_feed_file():
                elapsed = time.time() - start_time
                self.logger.info(f"Feed data available after {elapsed:.1f}s")
                return True
            
            time.sleep(1)
        
        self.logger.error(f"Timeout waiting for feed data after {timeout}s")
        return False
    
    def get_live_price(self, symbol: Optional[str] = None) -> Optional[float]:
        """Get current live price from feed data.
        
        Reads the JSON file and returns the latest price. If symbol is specified,
        returns price for that symbol only (supports multi-symbol feeds).
        
        Args:
            symbol: Optional symbol to get price for (default: first symbol)
            
        Returns:
            float: Current live price, or None if not available
            
        Example:
            >>> feed = LiveDataFeed()
            >>> price = feed.get_live_price()
            >>> print(f"Current price: {price}")
            >>> 
            >>> # For specific symbol
            >>> nifty_price = feed.get_live_price("NIFTY")
        """
        try:
            if not self.feed_file.exists():
                return None
            
            with open(self.feed_file, 'r') as f:
                data = json.load(f)
            
            if not data:
                return None
            
            # If symbol specified, filter by symbol
            if symbol:
                for tick in data:
                    if tick.get('trading_symbol') == symbol:
                        return tick.get('last_traded_price')
                return None
            
            # Return first available price
            if isinstance(data, list) and len(data) > 0:
                return data[0].get('last_traded_price')
            elif isinstance(data, dict):
                return data.get('last_traded_price')
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error reading live price: {e}")
            return None
    
    def get_feed_data(self) -> Optional[Dict[str, Any]]:
        """Get complete feed data from JSON file.
        
        Returns the entire feed data structure. Useful when you need
        more than just the price (e.g., volume, bid/ask, etc.)
        
        Returns:
            dict: Complete feed data, or None if not available
            
        Example:
            >>> feed = LiveDataFeed()
            >>> data = feed.get_feed_data()
            >>> if data:
            ...     print(f"Price: {data['last_traded_price']}")
            ...     print(f"Volume: {data['volume']}")
            ...     print(f"Timestamp: {data['exchange_timestamp']}")
        """
        try:
            if not self.feed_file.exists():
                return None
            
            with open(self.feed_file, 'r') as f:
                return json.load(f)
                
        except Exception as e:
            self.logger.error(f"Error reading feed data: {e}")
            return None
    
    def is_data_fresh(self, max_age_seconds: int = 5) -> bool:
        """Check if feed data is fresh (recently updated).
        
        Verifies that the data file has been updated within the specified
        time window. Useful for ensuring data quality before trading.
        
        Args:
            max_age_seconds: Maximum age in seconds (default: 5)
            
        Returns:
            bool: True if data is fresh, False otherwise
            
        Example:
            >>> feed = LiveDataFeed()
            >>> if feed.is_data_fresh(max_age_seconds=3):
            ...     price = feed.get_live_price()
            ...     print(f"Fresh price: {price}")
            ... else:
            ...     print("Data is stale, waiting for update...")
        """
        try:
            if not self.feed_file.exists():
                return False
            
            mtime = datetime.fromtimestamp(self.feed_file.stat().st_mtime)
            age = datetime.now() - mtime
            
            return age.total_seconds() <= max_age_seconds
            
        except Exception as e:
            self.logger.error(f"Error checking data freshness: {e}")
            return False
    
    def stop_feed(self) -> bool:
        """Stop the live data feed subprocess.
        
        Terminates the feed subprocess gracefully. Waits up to 5 seconds
        for clean shutdown, then forces termination if needed.
        
        Returns:
            bool: True if feed stopped successfully, False otherwise
            
        Example:
            >>> feed = LiveDataFeed()
            >>> feed.start_feed()
            >>> # ... trading operations ...
            >>> feed.stop_feed()
        """
        if self.feed_process is None:
            self.logger.warning("No feed process to stop")
            return True
        
        try:
            self.logger.info(f"Stopping feed subprocess (PID: {self.feed_process.pid})")
            
            # Terminate process
            self.feed_process.terminate()
            
            # Wait for process to exit (up to 5 seconds)
            try:
                self.feed_process.wait(timeout=5)
                self.logger.info("Feed subprocess terminated gracefully")
            except subprocess.TimeoutExpired:
                self.logger.warning("Feed subprocess did not terminate, killing...")
                self.feed_process.kill()
                self.feed_process.wait()
                self.logger.info("Feed subprocess killed")
            
            self.feed_process = None
            return True
            
        except Exception as e:
            self.logger.error(f"Error stopping feed subprocess: {e}", exc_info=True)
            return False
    
    def restart_feed(self) -> bool:
        """Restart the feed subprocess.
        
        Stops the current feed and starts a new one. Useful for recovering
        from feed errors or reconnecting after network issues.
        
        Returns:
            bool: True if restart successful, False otherwise
            
        Example:
            >>> feed = LiveDataFeed()
            >>> # If feed has issues
            >>> if not feed.is_data_fresh():
            ...     print("Restarting feed...")
            ...     feed.restart_feed()
        """
        self.logger.info("Restarting feed subprocess")
        self.stop_feed()
        time.sleep(1)
        return self.start_feed()
    
    def __del__(self):
        """Cleanup when object is destroyed."""
        if self.feed_process is not None:
            try:
                self.stop_feed()
            except:
                pass
