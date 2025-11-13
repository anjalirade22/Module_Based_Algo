"""WebSocket feed subprocess for live market data streaming.

This module runs as an independent subprocess and connects to the
SmartAPI WebSocket to stream live market data. It writes tick data
to a JSON file that can be read by the main process.

DO NOT IMPORT THIS MODULE - it is meant to be run as a subprocess.

Usage:
    # Run as subprocess from LiveDataFeed
    python -m modules.data_module.feed_process
    
    # Or directly
    python modules/data_module/feed_process.py

Architecture:
    ┌──────────────────┐
    │ SmartWebSocketV2 │
    └────────┬─────────┘
             │ WebSocket
             ↓
    ┌──────────────────┐
    │ WebSocketFeed    │
    │ (this process)   │
    └────────┬─────────┘
             │ writes JSON
             ↓
    ┌──────────────────┐
    │ live_feed_data   │
    │     .json        │
    └──────────────────┘

Features:
    - Independent subprocess (crash isolation)
    - Automatic reconnection on errors
    - JSON file output every 2 seconds
    - Heartbeat monitoring
    - Error logging
"""

import json
import time
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path to import modules
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from SmartApi.smartWebSocketV2 import SmartWebSocketV2
from modules.logger_module import get_logger
from config.credentials import get_credentials
from config.settings import CORRELATION_ID, API_KEY, CLIENT_CODE, FEED_TOKEN

# Initialize logger for this subprocess
logger = get_logger(__name__)


class WebSocketFeed:
    """WebSocket feed handler for live market data.
    
    This class manages the WebSocket connection to SmartAPI and handles
    incoming tick data. It runs in a separate process from the main
    trading application.
    
    Attributes:
        sws: SmartWebSocketV2 instance
        feed_file: Path to JSON output file
        latest_data: Latest tick data received
        last_write_time: Timestamp of last file write
        
    Example:
        # This runs automatically when feed_process.py is executed
        feed = WebSocketFeed()
        feed.connect()
    """
    
    def __init__(self, feed_file: str = "live_feed_data.json"):
        """Initialize WebSocket feed.
        
        Args:
            feed_file: Name of JSON output file (default: live_feed_data.json)
        """
        self.logger = get_logger(__name__)
        
        # Set feed file path (in data/live directory)
        live_data_dir = project_root / "data" / "live"
        live_data_dir.mkdir(parents=True, exist_ok=True)
        self.feed_file = live_data_dir / feed_file
        
        # Get credentials
        creds = get_credentials()
        
        # Initialize WebSocket
        self.sws = SmartWebSocketV2(
            auth_token=creds['auth_token'],
            api_key=API_KEY,
            client_code=CLIENT_CODE,
            feed_token=FEED_TOKEN
        )
        
        # Data storage
        self.latest_data = []
        self.last_write_time = time.time()
        self.write_interval = 2  # Write to file every 2 seconds
        
        # Connection state
        self.is_connected = False
        
        self.logger.info(f"WebSocketFeed initialized, output: {self.feed_file}")
    
    def on_open(self, wsapp):
        """Handle WebSocket connection opened.
        
        Args:
            wsapp: WebSocket app instance
        """
        self.logger.info("WebSocket connection opened")
        self.is_connected = True
        
        # Subscribe to instruments
        # Note: Modify this list based on your trading needs
        # Format: MODE | EXCHANGE | TOKEN
        subscription_data = {
            "correlationID": CORRELATION_ID,
            "action": 1,  # 1 = Subscribe
            "params": {
                "mode": 3,  # 1=LTP, 2=Quote, 3=Snap Quote
                "tokenList": [
                    {
                        "exchangeType": 1,  # 1=NSE, 2=NFO, 3=BSE, etc.
                        "tokens": ["99926000"]  # NIFTY 50 token (example)
                    }
                ]
            }
        }
        
        self.sws.subscribe(CORRELATION_ID, subscription_data["params"]["mode"], 
                          subscription_data["params"]["tokenList"])
        self.logger.info(f"Subscribed to instruments: {subscription_data}")
    
    def on_data(self, wsapp, message):
        """Handle incoming tick data.
        
        Args:
            wsapp: WebSocket app instance
            message: Tick data message
        """
        try:
            # Store latest tick data
            self.latest_data = message
            
            # Log tick (debug level to avoid spam)
            if isinstance(message, list) and len(message) > 0:
                tick = message[0]
                self.logger.debug(f"Tick: {tick.get('trading_symbol')} @ {tick.get('last_traded_price')}")
            
            # Write to file periodically (every 2 seconds)
            current_time = time.time()
            if current_time - self.last_write_time >= self.write_interval:
                self.write_to_file()
                self.last_write_time = current_time
                
        except Exception as e:
            self.logger.error(f"Error processing tick data: {e}", exc_info=True)
    
    def on_error(self, wsapp, error):
        """Handle WebSocket error.
        
        Args:
            wsapp: WebSocket app instance
            error: Error message
        """
        self.logger.error(f"WebSocket error: {error}")
        self.is_connected = False
    
    def on_close(self, wsapp):
        """Handle WebSocket connection closed.
        
        Args:
            wsapp: WebSocket app instance
        """
        self.logger.warning("WebSocket connection closed")
        self.is_connected = False
    
    def write_to_file(self):
        """Write latest tick data to JSON file.
        
        This method is called periodically (every 2 seconds) to update
        the JSON file with latest market data.
        """
        try:
            if not self.latest_data:
                return
            
            # Add metadata
            output_data = {
                "timestamp": datetime.now().isoformat(),
                "data": self.latest_data
            }
            
            # Write to file atomically (write to temp, then rename)
            temp_file = self.feed_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(output_data, f, indent=2)
            
            # Atomic rename
            temp_file.replace(self.feed_file)
            
            self.logger.debug(f"Wrote {len(self.latest_data)} ticks to {self.feed_file}")
            
        except Exception as e:
            self.logger.error(f"Error writing to file: {e}", exc_info=True)
    
    def connect(self):
        """Connect to WebSocket and start streaming.
        
        This is a blocking call that runs until the process is terminated.
        """
        try:
            # Set callbacks
            self.sws.on_open = self.on_open
            self.sws.on_data = self.on_data
            self.sws.on_error = self.on_error
            self.sws.on_close = self.on_close
            
            # Connect and run (blocking)
            self.logger.info("Connecting to WebSocket...")
            self.sws.connect()
            
        except KeyboardInterrupt:
            self.logger.info("Received interrupt signal, shutting down...")
            self.close()
        except Exception as e:
            self.logger.error(f"Fatal error in WebSocket feed: {e}", exc_info=True)
            self.close()
    
    def close(self):
        """Close WebSocket connection and cleanup."""
        try:
            self.logger.info("Closing WebSocket connection...")
            self.sws.close_connection()
            
            # Write final data
            if self.latest_data:
                self.write_to_file()
            
            self.logger.info("WebSocket feed closed")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}", exc_info=True)


def main():
    """Main entry point for feed subprocess.
    
    This function is called when the script is run as a subprocess.
    It creates a WebSocketFeed instance and starts streaming data.
    """
    logger.info("=" * 80)
    logger.info("Starting WebSocket Feed Subprocess")
    logger.info(f"Python: {sys.version}")
    logger.info(f"PID: {sys.pid if hasattr(sys, 'pid') else 'N/A'}")
    logger.info("=" * 80)
    
    try:
        # Create feed instance
        feed = WebSocketFeed()
        
        # Start streaming (blocking)
        feed.connect()
        
    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
