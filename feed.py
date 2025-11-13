import config
# Note: Removed circular import of strategy_modified 
import logging
import os
import sys
import traceback
import json
import time
from datetime import datetime
from SmartApi.smartWebSocketV2 import SmartWebSocketV2

def setup_logging():
    """
    Setup logging configuration for the trading system.
    
    Creates a logs directory and configures logging to both file and console.
    Log files are stored in the 'logs' directory with the name 'trading_bot.log'.
    
    Returns:
        logging.Logger: Configured logger instance
    """
    # Create logs directory if it doesn't exist
    current_dir = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(current_dir, 'logs')
    
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
        print(f"Created logs directory: {logs_dir}")
    
    log_file = os.path.join(logs_dir, 'trading_bot.log')
    
    # Simple logging configuration to avoid encoding issues
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)

def setup_websocket(api_key, client_code, feed_token, logger, jwt_token):
    """
    Setup and connect the Angel One SmartAPI WebSocket for real-time data streaming.
    
    Args:
        api_key (str): Angel One API key
        client_code (str): Angel One client code (username)
        feed_token (str): Feed token from login response
        logger (logging.Logger): Logger instance for logging
        jwt_token (str): JWT token from login response
        
    Returns:
        SmartWebSocketV2: Connected WebSocket instance
    """
    logger.info("Initializing WebSocket connection...")
    
    # Initialize WebSocket with JWT token as first parameter
    smart_socket = SmartWebSocketV2(jwt_token, api_key, client_code, feed_token)
    
    def on_open(ws):
        """Callback function triggered when WebSocket connection opens"""
        logger.info("WebSocket connection opened successfully")
        print("WebSocket connection opened successfully", flush=True)
        
        # Read tokens from configuration file created by strategy
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            tickers_file = os.path.join(current_dir, 'tickers_config.json')
            
            if os.path.exists(tickers_file):
                with open(tickers_file, 'r') as f:
                    feed_config = json.load(f)
                
                # Use the pre-formatted tokens_for_subscription for WebSocket subscription
                subscription_tokens = feed_config.get('tokens_for_subscription', [])
                all_tickers_info = feed_config.get('all_tickers', {})
                tickers_info = feed_config.get('tickers', {})
                
                logger.info("Loaded tickers configuration:")
                logger.info(f"All tickers (for subscription): {len(all_tickers_info)} tokens")
                for token, name in all_tickers_info.items():
                    logger.info(f"  Token {token}: {name}")
                
                logger.info(f"Trading tickers (current month futures only): {len(tickers_info)} tokens")
                for token, name in tickers_info.items():
                    logger.info(f"  Token {token}: {name}")
                
                logger.info(f"Subscription format: {subscription_tokens}")
                
                # Store the token mappings globally for use in data processing
                config.ALL_TICKERS_MAP = all_tickers_info
                config.TICKERS_MAP = tickers_info
                
            else:
                # Fallback to hardcoded tokens if configuration file doesn't exist
                logger.warning("tickers_config.json not found, using fallback tokens")
                subscription_tokens = [{"exchangeType": 1, "tokens": ["99926009", "99926000"]}]
                config.ALL_TICKERS_MAP = {"99926009": "BANKNIFTY_SPOT", "99926000": "NIFTY_SPOT"}
                config.TICKERS_MAP = {}
                
        except Exception as e:
            logger.error(f"Error reading tickers configuration: {e}")
            logger.warning("Using fallback tokens due to configuration error")
            # Fallback to hardcoded tokens: Bank Nifty and Nifty 50 indices
            subscription_tokens = [{"exchangeType": 1, "tokens": ["99926009", "99926000"]}]
            config.ALL_TICKERS_MAP = {"99926009": "BANKNIFTY_SPOT", "99926000": "NIFTY_SPOT"}
            config.TICKERS_MAP = {}
        
        # Subscribe to real-time data with mode=1 (LTP only)
        logger.info(f"Subscribing to tokens: {subscription_tokens}")
        print(f"Subscribing to tokens: {subscription_tokens}", flush=True)
        
        smart_socket.subscribe(config.CORRELATION_ID, 1, subscription_tokens)
        logger.info(f"Subscription call completed")
        print(f"Subscription call completed", flush=True)
    
    def on_data(ws, message):
        """
        Callback function to process incoming real-time market data
        
        Args:
            ws: WebSocket instance
            message: Market data message (can be single dict or list of dicts)
        """
        try:
            # Handle both single message and list of messages from the API
            if isinstance(message, list):
                data_points = message
            else:
                data_points = [message]
              
            # Process each data point in the message
            for data_point in data_points:
                if isinstance(data_point, dict) and "token" in data_point and "last_traded_price" in data_point:
                    token = str(data_point["token"])
                    # Angel One API returns price in paisa, convert to rupees
                    ltp = float(data_point["last_traded_price"]) / 100
                    
                    # Store the live price data in global config for strategy access
                    config.LIVE_FEED_JSON[token] = {
                        "ltp": ltp,
                        "timestamp": datetime.now().isoformat()
                    }
                    
                    # Also save to a JSON file for inter-process communication (throttled)
                    try:
                        # Only save to file every few updates to reduce I/O
                        if int(time.time()) % 2 == 0:  # Save every 2 seconds
                            live_data_file = os.path.join(os.path.dirname(__file__), 'live_feed_data.json')
                            with open(live_data_file, 'w') as f:
                                json.dump(config.LIVE_FEED_JSON, f)
                    except Exception as file_error:
                        logger.debug(f"Error writing live data file: {file_error}")
                    
                    # Get instrument name for better logging
                    instrument_name = "UNKNOWN"
                    if hasattr(config, 'ALL_TICKERS_MAP') and token in config.ALL_TICKERS_MAP:
                        instrument_name = config.ALL_TICKERS_MAP[token]
                    
                    # Log the updated token price for monitoring (throttled to reduce log spam)
                    if int(time.time()) % 5 == 0:  # Log every 5 seconds for active tokens
                        logger.info(f"Updated {instrument_name} (token {token}): {ltp}")
            
        except Exception as e:
            error_msg = f"Error processing WebSocket data: {e}"
            logger.error(error_msg)
            logger.error(f"Message content: {str(message)[:200]}...")  # Truncate long messages
            print(f"ERROR: {error_msg}", flush=True)
    
    def on_error(ws, error):
        """Callback function to handle WebSocket errors"""
        error_msg = f"WebSocket error: {error}"
        logger.error(error_msg)
        print(f"ERROR: {error_msg}", flush=True)
        
        # Try to reconnect on connection errors
        if "Connection closed" in str(error) or "forcibly closed" in str(error):
            logger.info("Attempting to reconnect WebSocket due to connection error...")
            print("Attempting to reconnect WebSocket...", flush=True)
            try:
                time.sleep(2)  # Wait before reconnecting
                ws.connect()
                logger.info("WebSocket reconnection attempt completed")
            except Exception as reconnect_error:
                logger.error(f"Reconnection failed: {reconnect_error}")
                print(f"Reconnection failed: {reconnect_error}", flush=True)
    
    def on_close(ws, close_status_code=None, close_msg=None):
        """Callback function triggered when WebSocket connection closes"""
        close_message = f"WebSocket connection closed"
        if close_status_code:
            close_message += f" - Status Code: {close_status_code}"
        if close_msg:
            close_message += f" - Message: {close_msg}"
        
        logger.warning(close_message)
        print(f"WARNING: {close_message}", flush=True)
    
    # Register all callback functions with the WebSocket instance
    smart_socket.on_open = on_open
    smart_socket.on_data = on_data
    smart_socket.on_error = on_error
    smart_socket.on_close = on_close
    
    # Establish the WebSocket connection
    logger.info("Attempting to connect WebSocket...")
    print("Connecting to WebSocket...", flush=True)
    try:
        smart_socket.connect()
        logger.info("WebSocket connect() method called successfully")
        print("WebSocket connect() called successfully", flush=True)
    except Exception as e:
        error_msg = f"Error calling WebSocket connect(): {e}"
        logger.error(error_msg)
        print(f"ERROR: {error_msg}", flush=True)
        raise
        raise
    
    return smart_socket

def main():
    """
    Main execution function that orchestrates the entire trading system startup.
    
    This function:
    1. Sets up logging
    2. Creates necessary directories
    3. Initializes Angel One API connection
    4. Establishes WebSocket connection for live data
    5. Starts the trading algorithm
    """
    try:
        print("=" * 60, flush=True)
        print("STARTING FEED.PY - DATA FEED PROCESS", flush=True)
        print("=" * 60, flush=True)
        print(f"Python executable: {os.sys.executable}", flush=True)
        print(f"Working directory: {os.getcwd()}", flush=True)
        print(f"Script location: {os.path.abspath(__file__)}", flush=True)
        print("Starting initialization...", flush=True)
        
        # Initialize logging system
        logger = setup_logging()
        config.logger = logger
        
        logger.info("Feed.py starting up...")
        logger.info(f"Python executable: {os.sys.executable}")
        logger.info(f"Working directory: {os.getcwd()}")
        logger.info(f"Script location: {os.path.abspath(__file__)}")
        logger.info("Checking configuration...")
        print("Configuration check...", flush=True)
        
        # Validate configuration
        logger.info(f"API_KEY configured: {'Yes' if config.API_KEY else 'No'}")
        logger.info(f"USERNAME configured: {'Yes' if config.USERNAME else 'No'}")
        logger.info(f"PIN configured: {'Yes' if config.PIN else 'No'}")
        logger.info(f"TOTP_TOKEN configured: {'Yes' if config.TOTP_TOKEN else 'No'}")
        
        print(f"API_KEY: {'Configured' if config.API_KEY else 'Missing'}", flush=True)
        print(f"USERNAME: {'Configured' if config.USERNAME else 'Missing'}", flush=True)
        print(f"PIN: {'Configured' if config.PIN else 'Missing'}", flush=True)
        print(f"TOTP_TOKEN: {'Configured' if config.TOTP_TOKEN else 'Missing'}", flush=True)
        
        # Check for missing configuration
        if not all([config.API_KEY, config.USERNAME, config.PIN, config.TOTP_TOKEN]):
            error_msg = "Missing required configuration. Please check config.py"
            logger.error(error_msg)
            print(f"ERROR: {error_msg}", flush=True)
            return
        
        # Create Data directory for storing pickle files if it doesn't exist
        current_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(current_dir, 'Data')
        
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            logger.info(f"Created Data directory: {data_dir}")
        
        # Use centralized authentication from config
        logger.info("Initializing SmartAPI connection using centralized authentication...")
        print("Initializing SmartAPI connection using centralized authentication...", flush=True)
        
        # Set the logger in config before authentication
        config.logger = logger
        
        # Authenticate using centralized function
        print("Calling centralized authentication...", flush=True)
        if config.initialize_smart_api():
            logger.info("Centralized authentication successful")
            print("Centralized authentication successful! Extracting tokens...", flush=True)
            
            # Get authentication tokens from config
            feed_token = config.FEED_TOKEN
            jwt_token = config.JWT_TOKEN
            
            logger.info("Tokens extracted successfully from config")
            print("Tokens extracted successfully from config", flush=True)
            
            # Initialize live price data storage
            config.LIVE_FEED_JSON = {}
            logger.info("Initialized LIVE_FEED_JSON dictionary")
            print("Initialized LIVE_FEED_JSON dictionary", flush=True)
            
            # Setup and connect WebSocket for real-time market data
            logger.info("Setting up WebSocket connection...")
            print("Setting up WebSocket connection...", flush=True)
            config.SMART_WEB = setup_websocket(
                config.API_KEY, 
                config.USERNAME, 
                feed_token, 
                logger, 
                jwt_token
            )
            
            # Allow time for WebSocket to establish connection and receive initial data
            logger.info("Waiting for WebSocket connection to establish...")
            print("Waiting for WebSocket to establish connection...", flush=True)
            time.sleep(5)
            
            # Keep the data feed running without starting the strategy
            logger.info("Data feed established successfully. Keeping connection alive...")
            logger.info("🕐 Data feed will automatically stop at Market Close (15:30)")
            logger.info(f"LIVE_FEED_JSON status: {len(config.LIVE_FEED_JSON)} tokens available")
            print(f"Data feed established! {len(config.LIVE_FEED_JSON)} tokens available", flush=True)
            print("🕐 Data feed will automatically stop at Market Close (15:30)", flush=True)
            print("Entering main loop to keep connection alive...", flush=True)
            
            # Keep the WebSocket connection alive with enhanced monitoring
            try:
                loop_count = 0
                consecutive_errors = 0
                max_consecutive_errors = 5
                
                while True:
                    time.sleep(1)  # Keep the process running
                    loop_count += 1
                    
                    # Check for market close time (15:30)
                    current_time = datetime.now().time()
                    if current_time.hour >= 15 and current_time.minute >= 30:
                        logger.info("🔔 Market Close Time (15:30) reached - Shutting down feed...")
                        print("🔔 Market Close Time (15:30) reached - Shutting down feed...")
                        
                        # Disconnect WebSocket gracefully
                        try:
                            if hasattr(config, 'SMART_WEB') and config.SMART_WEB:
                                config.SMART_WEB.disconnect()
                                logger.info("WebSocket disconnected gracefully")
                        except Exception as e:
                            logger.error(f"Error disconnecting WebSocket: {e}")
                        
                        # Exit the feed process
                        logger.info("Feed process shutting down at market close")
                        sys.exit(0)
                    
                    # Check if we have live data - if not, there might be a connection issue
                    if loop_count > 60 and not config.LIVE_FEED_JSON:  # After 1 minute
                        logger.warning("No live data received after 1 minute - possible connection issue")
                        consecutive_errors += 1
                        
                        if consecutive_errors >= max_consecutive_errors:
                            logger.error("Too many consecutive errors - attempting to restart WebSocket")
                            try:
                                config.SMART_WEB.connect()
                                consecutive_errors = 0  # Reset error counter on successful reconnect
                                logger.info("WebSocket restart attempt completed")
                            except Exception as restart_error:
                                logger.error(f"WebSocket restart failed: {restart_error}")
                    else:
                        consecutive_errors = 0  # Reset if we have data
                    
                    # Log status every 30 seconds
                    if loop_count % 30 == 0:
                        logger.info(f"Data feed alive - {len(config.LIVE_FEED_JSON)} tokens active")
                        print(f"Data feed alive - {len(config.LIVE_FEED_JSON)} tokens active", flush=True)
                        
                        # Log current data for debugging (only if we have data)
                        if config.LIVE_FEED_JSON:
                            latest_token = list(config.LIVE_FEED_JSON.keys())[0]
                            latest_data = config.LIVE_FEED_JSON[latest_token]
                            logger.debug(f"Latest data - Token {latest_token}: {latest_data['ltp']} at {latest_data['timestamp']}")
                        
                    # Reset counter to prevent overflow
                    if loop_count > 86400:  # Reset after 24 hours
                        loop_count = 0
                        
            except KeyboardInterrupt:
                logger.info("Data feed stopped by user")
                print("Data feed stopped by user", flush=True)
            
        else:
            error_msg = "Centralized authentication failed"
            logger.error(error_msg)
            print(f"ERROR: {error_msg}", flush=True)
            print("feed.py exiting due to authentication failure", flush=True)
        
    except KeyboardInterrupt:
        logger.info("Trading system stopped by user")
        print("feed.py stopped by user", flush=True)
    except Exception as e:
        error_msg = f"Fatal error in feed.py: {e}"
        logger.error(error_msg)
        logger.error(f"Full traceback: {traceback.format_exc()}")
        print(f"ERROR: {error_msg}", flush=True)
        print("feed.py exiting due to error", flush=True)
        raise  # Re-raise to ensure subprocess sees the error
        
if __name__ == "__main__":
    print("Starting feed.py...", flush=True)
    try:
        main()
    except Exception as e:
        print(f"FATAL ERROR in feed.py: {e}", flush=True)
        import traceback
        traceback.print_exc()
    finally:
        print("feed.py execution completed", flush=True)