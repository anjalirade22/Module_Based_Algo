"""
Strategy Deploy 1 - Live Trading Implementation
Comprehensive swing levels breakout strategy with live data feed
Rewritten from scratch with clean architecture
"""

import json
import pandas as pd
from datetime import datetime, time, timedelta
import time as t
import pickle
import os
import subprocess
import sys
import warnings
import atexit
import signal
import threading
import traceback
from SmartApi.smartConnect import SmartConnect
import pyotp

warnings.filterwarnings("ignore")

# Import configuration
try:
    import config
except ImportError:
    print("❌ Error: config.py not found. Please ensure config.py exists in the same directory.")
    sys.exit(1)


class SwingLevelsDetector:
    """
    Pure swing level detection using 3-bar pattern
    """
    
    def __init__(self, min_diff=0.0):
        self.buy_level = []
        self.sell_level = []
        self.diff = min_diff
    
    def get_buy_level(self, df):
        """Get swing high levels (resistance) for long entries"""
        if df is None or df.empty:
            return []
        
        self.buy_level = []
        
        try:
            c = float(df.iloc[-1]["close"])
        except (IndexError, KeyError, TypeError):
            return []
        
        # Find swing highs using 3-bar pattern
        for i in range(3, len(df) + 1):
            middle_close = df.iloc[i-2]["close"]
            left_close = df.iloc[i-3]["close"]
            right_close = df.iloc[i-1]["close"]
            
            # Swing high conditions
            if (middle_close > right_close and (middle_close - right_close) > self.diff and
                middle_close > left_close and (middle_close - left_close) > self.diff and
                middle_close > c):
                
                self.buy_level.append({
                    "date": df.index[i-2], 
                    "high": middle_close
                })
        
        # Remove non-virgin levels
        delete = []
        for i in range(len(self.buy_level) - 1):
            for j in range(i + 1, len(self.buy_level)):
                if (self.buy_level[i]["high"] < self.buy_level[j]["high"] and 
                    self.buy_level[i]["date"] < self.buy_level[j]["date"]):
                    delete.append(self.buy_level[i])
                    break
        
        for item in delete:
            if item in self.buy_level:
                self.buy_level.remove(item)
        
        # Keep only the lowest (closest to current price) swing high
        if self.buy_level:
            high_values = [level["high"] for level in self.buy_level]
            high_values.sort()
            self.buy_level = [level for level in self.buy_level 
                            if level["high"] == high_values[0]]
        
        return self.buy_level
    
    def get_sell_level(self, df):
        """Get swing low levels (support) for short entries"""
        if df is None or df.empty:
            return []
        
        self.sell_level = []
        
        try:
            c = float(df.iloc[-1]["close"])
        except (IndexError, KeyError, TypeError):
            return []
        
        # Find swing lows using 3-bar pattern
        for i in range(3, len(df) + 1):
            middle_close = df.iloc[i-2]["close"]
            left_close = df.iloc[i-3]["close"]
            right_close = df.iloc[i-1]["close"]
            
            # Swing low conditions
            if (middle_close < right_close and (right_close - middle_close) > self.diff and
                middle_close < left_close and (left_close - middle_close) > self.diff and
                middle_close < c):
                
                self.sell_level.append({
                    "date": df.index[i-2], 
                    "low": middle_close
                })
        
        # Remove non-virgin levels
        delete = []
        for i in range(len(self.sell_level) - 1):
            for j in range(i + 1, len(self.sell_level)):
                if (self.sell_level[i]["low"] > self.sell_level[j]["low"] and 
                    self.sell_level[i]["date"] < self.sell_level[j]["date"]):
                    delete.append(self.sell_level[i])
                    break
        
        for item in delete:
            if item in self.sell_level:
                self.sell_level.remove(item)
        
        # Keep only the highest (closest to current price) swing low
        if self.sell_level:
            low_values = [level["low"] for level in self.sell_level]
            low_values.sort(reverse=True)
            self.sell_level = [level for level in self.sell_level 
                             if level["low"] == low_values[0]]
        
        return self.sell_level


class LiveDataFeed:
    """
    Live data feed manager
    Handles feed.py process and live data reading
    """
    
    def __init__(self, logger):
        self.logger = logger
        self.feed_process = None
        self.live_data_file = os.path.join(os.path.dirname(__file__), 'live_feed_data.json')
        self.live_data = {}
        self._shutdown_flag = False
        
    def start_feed(self):
        """Start the live data feed process"""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            feed_script = os.path.join(current_dir, 'feed.py')
            
            if not os.path.exists(feed_script):
                self.logger.error(f"[ERROR] feed.py not found at: {feed_script}")
                raise FileNotFoundError(f"feed.py not found at: {feed_script}")
            
            self.logger.info(f"[FEED] Starting data feed process...")
            
            # Check if feed process is already running
            if self.feed_process and self.feed_process.poll() is None:
                self.logger.info("[FEED] Process already running")
                return True
            
            # Start feed.py as separate process with proper error handling
            # Note: Not capturing stdout/stderr to allow real-time output visibility
            self.feed_process = subprocess.Popen(
                [sys.executable, feed_script],
                stdout=None,  # Let output go to console
                stderr=None,  # Let errors go to console  
                text=True,
                cwd=current_dir,
                creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
            )
            
            self.logger.info(f"[FEED] Process started with PID: {self.feed_process.pid}")
            
            # Wait and verify process started
            self.logger.info("Waiting 5 seconds to see if feed process starts successfully...")
            t.sleep(5)  # Give time for startup
            if self.feed_process.poll() is not None:
                error_msg = f"Feed process exited early (within 5 seconds). Exit code: {self.feed_process.returncode}"
                self.logger.error(f"[ERROR] {error_msg}")
                raise RuntimeError(error_msg)
            else:
                self.logger.info("[FEED] Process running successfully")
                
                # Validate and prepare feed file
                self.validate_feed_file()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start data feed: {e}")
            return False
    
    def validate_feed_file(self):
        """Validate and repair feed file if needed"""
        try:
            if not os.path.exists(self.live_data_file):
                # Create empty valid JSON file
                with open(self.live_data_file, 'w') as f:
                    json.dump({}, f)
                self.logger.info("[FEED] Created new live_feed_data.json file")
                return True
                
            # Check if file is empty or corrupted
            if os.path.getsize(self.live_data_file) == 0:
                # File is empty, write empty JSON
                with open(self.live_data_file, 'w') as f:
                    json.dump({}, f)
                self.logger.info("[FEED] Repaired empty live_feed_data.json file")
                return True
                
            # Try to read and validate JSON
            with open(self.live_data_file, 'r') as f:
                content = f.read().strip()
                if not content:
                    # File has whitespace but no content
                    with open(self.live_data_file, 'w') as f:
                        json.dump({}, f)
                    self.logger.info("[FEED] Repaired blank live_feed_data.json file")
                    return True
                
                # Try to parse JSON
                try:
                    json.loads(content)
                    return True  # File is valid
                except json.JSONDecodeError:
                    # File is corrupted, reset it
                    with open(self.live_data_file, 'w') as f:
                        json.dump({}, f)
                    self.logger.info("[FEED] Repaired corrupted live_feed_data.json file")
                    return True
                    
        except Exception as e:
            self.logger.error(f"[ERROR] Error validating feed file: {e}")
            return False
            self.logger.error(f"Failed to start data feed: {e}")
            return False
    
    def wait_for_data(self, timeout=60):
        """Wait for live data to become available"""
        self.logger.info("[FEED] Waiting for data connection...")
        start_time = t.time()
        
        while t.time() - start_time < timeout:
            try:
                if os.path.exists(self.live_data_file):
                    with open(self.live_data_file, 'r') as f:
                        live_data = json.load(f)
                    
                    if live_data and len(live_data) > 0:
                        self.live_data = live_data
                        self.logger.info("[FEED] Data connection established")
                        self.logger.info(f"[FEED] Available tokens: {list(live_data.keys())}")
                        return True
            except (json.JSONDecodeError, FileNotFoundError):
                pass
            
            # Check if feed process is still running
            if self.feed_process and self.feed_process.poll() is not None:
                self.logger.error(f"[ERROR] Feed process died. Exit code: {self.feed_process.returncode}")
                return False
            
            elapsed = t.time() - start_time
            if int(elapsed) % 10 == 0 and elapsed > 0:
                self.logger.info(f"[FEED] Still waiting for data... ({int(elapsed)}s)")
            
            t.sleep(1)
        
        self.logger.error(f"[ERROR] Timeout waiting for live data after {timeout}s")
        return False
    
    def get_live_price(self, token):
        """Get live price for token"""
        try:
            # Try to read fresh data from file
            if os.path.exists(self.live_data_file):
                with open(self.live_data_file, 'r') as f:
                    content = f.read().strip()
                    if content:
                        self.live_data = json.loads(content)
            
            token_str = str(token)
            if token_str in self.live_data and 'ltp' in self.live_data[token_str]:
                return float(self.live_data[token_str]['ltp'])
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Error getting live price for {token}: {e}")
            return None
    
    def is_data_fresh(self, max_age_seconds=60):
        """Check if live data is fresh"""
        try:
            if not os.path.exists(self.live_data_file):
                return False
            
            file_age = t.time() - os.path.getmtime(self.live_data_file)
            return file_age <= max_age_seconds
            
        except Exception:
            return False
            return False
    
    def stop_feed(self):
        """Stop the live data feed process"""
        self._shutdown_flag = True
        if self.feed_process:
            try:
                self.feed_process.terminate()
                self.feed_process.wait(timeout=10)
                self.logger.info("Data feed process stopped")
            except Exception as e:
                self.logger.error(f"Error stopping feed process: {e}")
                try:
                    self.feed_process.kill()
                except:
                    pass
                    pass


class TradingStrategy:
    """
    Main trading strategy class
    Implements swing levels breakout strategy with live data
    """
    
    def __init__(self):
        self.config = config
        self.logger = config.logger
        
        # Strategy parameters
        self.entry_buffer = 0.001  # 0.1% buffer
        self.lookback = getattr(config, 'LOOKBACK', 400)
        
        # Initialize components
        self.swing_detector = SwingLevelsDetector(min_diff=0.0)
        self.live_feed = LiveDataFeed(self.logger)
        
        # Trading state
        self.positions = {}  # {symbol: position_info}
        self.swing_levels = {}  # {symbol: swing_level_info}
        self.tokens = {}  # {symbol: token}
        
        # Timing
        self.last_swing_update = datetime.now() - timedelta(hours=1)
        self.shutdown_flag = False
        
        # Load persistent data
        self.load_data()
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        atexit.register(self.cleanup)
        
        # Initialize API connection
        self.logger.info("[API] Attempting to initialize SmartAPI...")
        if not self.initialize_api():
            self.logger.error("[ERROR] Failed to initialize API - Running in simulation mode")
            self.config.SMART_API_OBJ = None
        else:
            self.logger.info("[SUCCESS] SmartAPI connected successfully")
        
        self.logger.info("[SUCCESS] Trading Strategy initialized")
    
    def initialize_api(self):
        """Initialize and login to SmartAPI"""
        try:
            # Check if already logged in
            if hasattr(self.config, 'SMART_API_OBJ') and self.config.SMART_API_OBJ:
                self.logger.info("✅ SmartAPI already connected")
                return True
            
            self.logger.info("[API] Initializing SmartAPI connection...")
            
            # Check credentials
            if not hasattr(self.config, 'API_KEY') or not self.config.API_KEY:
                self.logger.error("[ERROR] API_KEY not found in config")
                return False
            
            if not hasattr(self.config, 'USERNAME') or not self.config.USERNAME:
                self.logger.error("[ERROR] USERNAME not found in config")
                return False
            
            if not hasattr(self.config, 'PIN') or not self.config.PIN:
                self.logger.error("[ERROR] PIN not found in config")
                return False
            
            if not hasattr(self.config, 'TOTP_TOKEN') or not self.config.TOTP_TOKEN:
                self.logger.error("[ERROR] TOTP_TOKEN not found in config")
                return False
            
            self.logger.info(f"[CONFIG] Using API_KEY: {self.config.API_KEY[:5]}...")
            self.logger.info(f"[CONFIG] Using USERNAME: {self.config.USERNAME}")
            
            # Initialize SmartConnect
            smart_api = SmartConnect(api_key=self.config.API_KEY.strip())
            
            # Generate TOTP
            totp = pyotp.TOTP(self.config.TOTP_TOKEN.strip()).now()
            self.logger.info(f"[TOTP] Generated TOTP: {totp}")
            
            # Login
            data = smart_api.generateSession(
                clientCode=self.config.USERNAME.strip(),
                password=self.config.PIN.strip(),
                totp=totp
            )
            
            if data and data.get('status'):
                self.config.SMART_API_OBJ = smart_api
                self.logger.info("[SUCCESS] SmartAPI login successful")
                
                # Get user profile
                try:
                    # Note: getProfile needs refresh token - skipping for now
                    self.logger.info(f"[USER] Logged in as client: {self.config.USERNAME}")
                except Exception as e:
                    self.logger.warning(f"Could not fetch profile: {e}")
                
                return True
            else:
                self.logger.error(f"[ERROR] SmartAPI login failed: {data}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ API initialization error: {e}")
            return False
    
    def place_order(self, symbol, transaction_type, quantity=None):
        """Place order using SmartAPI"""
        try:
            if not self.config.SMART_API_OBJ:
                self.logger.error("❌ SmartAPI not connected - Cannot place orders")
                return False
            
            # Get token for the symbol
            token = self.tokens.get(symbol)
            if not token:
                self.logger.error(f"❌ Token not found for {symbol}")
                return False
            
            # Get current price for logging
            current_price = self.live_feed.get_live_price(token)
            if not current_price:
                self.logger.error(f"❌ No price data for {symbol}")
                return False
            
            # Use default quantity if not provided
            if not quantity:
                quantity = getattr(self.config, 'QUANTITY', 1)
            
            # Order parameters
            order_params = {
                "variety": "NORMAL",
                "tradingsymbol": symbol,
                "symboltoken": str(token),
                "transactiontype": transaction_type,  # BUY or SELL
                "exchange": "NFO",
                "ordertype": "MARKET",
                "producttype": "INTRADAY",
                "duration": "DAY",
                "price": "0",  # Market order
                "squareoff": "0",
                "stoploss": "0",
                "quantity": str(quantity)
            }
            
            self.logger.info(f"📤 Placing {transaction_type} order for {symbol}")
            self.logger.info(f"   Quantity: {quantity}, Price: {current_price:.2f}")
            
            # Place the order
            order_response = self.config.SMART_API_OBJ.placeOrder(order_params)
            
            if order_response and order_response.get('status'):
                order_id = order_response.get('data', {}).get('orderid')
                self.logger.info(f"✅ Order placed successfully - ID: {order_id}")
                return order_id
            else:
                self.logger.error(f"❌ Order placement failed: {order_response}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error placing order: {e}")
            return False
    
    def get_order_status(self, order_id):
        """Check order status"""
        try:
            if not self.config.SMART_API_OBJ:
                return None
            
            order_book = self.config.SMART_API_OBJ.orderBook()
            if order_book and order_book.get('status'):
                orders = order_book.get('data', [])
                for order in orders:
                    if order.get('orderid') == order_id:
                        return order.get('orderstatus')
            return None
            
        except Exception as e:
            self.logger.error(f"Error checking order status: {e}")
            return None
    
    def get_positions_from_broker(self):
        """Get actual positions from broker"""
        try:
            if not self.config.SMART_API_OBJ:
                return {}
            
            positions_response = self.config.SMART_API_OBJ.position()
            
            if positions_response and positions_response.get('status') and positions_response.get('data'):
                broker_positions = {}
                positions_data = positions_response.get('data', [])
                
                # Handle case where data might be None
                if positions_data is None:
                    return {}
                    
                for pos in positions_data:
                    symbol = pos.get('tradingsymbol')
                    if symbol and symbol in self.tokens:
                        net_qty = int(pos.get('netqty', 0))
                        if net_qty != 0:  # Only include non-zero positions
                            broker_positions[symbol] = {
                                'quantity': net_qty,
                                'avg_price': float(pos.get('avgprice', 0)),
                                'pnl': float(pos.get('pnl', 0)),
                                'direction': 'LONG' if net_qty > 0 else 'SHORT'
                            }
                return broker_positions
            
            return {}
            
        except Exception as e:
            self.logger.error(f"Error getting broker positions: {e}")
            return {}
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info("Shutdown signal received, cleaning up...")
        self.shutdown_flag = True
        self.cleanup()
        sys.exit(0)
    
    def load_data(self):
        """Load persistent trading data"""
        try:
            data_folder = os.path.join(os.path.dirname(__file__), 'Data')
            
            # Load positions
            pf_file = os.path.join(data_folder, 'pf.pickle')
            if os.path.exists(pf_file):
                with open(pf_file, 'rb') as f:
                    self.positions = pickle.load(f)
                self.logger.info("Loaded existing positions data")
            
            # Load swing levels
            swing_file = os.path.join(data_folder, 'swing_level.pickle')
            if os.path.exists(swing_file):
                with open(swing_file, 'rb') as f:
                    self.swing_levels = pickle.load(f)
                self.logger.info("Loaded existing swing levels data")
            
            # Load token mapping
            tokens_file = 'tickers_config.json'
            if os.path.exists(tokens_file):
                with open(tokens_file, 'r') as f:
                    token_config = json.load(f)
                
                # Extract proper symbol-to-token mapping
                self.tokens = {}
                if 'token_map' in token_config:
                    # Map symbols to tokens
                    for symbol, token in token_config['token_map'].items():
                        self.tokens[symbol] = token
                
                # Also add direct mappings from all_tickers if available
                if 'all_tickers' in token_config:
                    for token, symbol in token_config['all_tickers'].items():
                        # Use symbol as key and token as value
                        if symbol not in self.tokens:
                            self.tokens[symbol] = token
                
                if self.tokens:
                    self.logger.info(f"Loaded tokens: {list(self.tokens.keys())}")
                else:
                    self.logger.warning("No valid tokens found in config")
            else:
                self.logger.warning("tickers_config.json not found")
            
        except Exception as e:
            self.logger.error(f"Error loading data: {e}")
    
    def save_data(self):
        """Save persistent trading data"""
        try:
            data_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Data')
            os.makedirs(data_folder, exist_ok=True)
            
            # Save positions
            with open(os.path.join(data_folder, 'pf.pickle'), 'wb') as f:
                pickle.dump(self.positions, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            # Save swing levels
            with open(os.path.join(data_folder, 'swing_level.pickle'), 'wb') as f:
                pickle.dump(self.swing_levels, f, protocol=pickle.HIGHEST_PROTOCOL)
            
            self.logger.debug("Data saved successfully")
            
        except Exception as e:
            self.logger.error(f"Error saving data: {e}")
    
    def get_historical_data(self, token, interval='ONE_HOUR', days=None):
        """Get historical data for swing level calculation"""
        try:
            if not self.config.SMART_API_OBJ:
                self.logger.error("SmartAPI object not available")
                return None
            
            days = days or self.lookback
            from_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M")
            to_date = datetime.now().strftime("%Y-%m-%d %H:%M")
            
            historicParam = {
                "exchange": "NFO",
                "symboltoken": str(token),
                "interval": interval,
                "fromdate": from_date,
                "todate": to_date
            }
            
            data = self.config.SMART_API_OBJ.getCandleData(historicParam)
            
            if data and 'data' in data and data['data']:
                df = pd.DataFrame(data['data'], 
                                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)
                return df
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting historical data for {token}: {e}")
            return None
    
    def update_swing_levels(self, symbol):
        """Update swing levels for a symbol"""
        try:
            # Skip invalid symbols
            if symbol in ['all_tickers', 'tickers', 'token_map', 'tokens_for_subscription']:
                return
                
            if symbol not in self.tokens:
                return
            
            token = self.tokens[symbol]
            
            # Validate token
            try:
                token = str(token).strip()
                if not token.isdigit():
                    return
            except:
                return
                
            df = self.get_historical_data(token)
            
            if df is None or df.empty:
                self.logger.warning(f"No historical data for {symbol}")
                return
            
            # Initialize swing levels if not exists
            if symbol not in self.swing_levels:
                self.swing_levels[symbol] = {
                    'swing_high': None,
                    'buy_level': None, 
                    'swing_high_timestamp': None,
                    'swing_low': None,
                    'sell_level': None,
                    'swing_low_timestamp': None,
                    'last_updated': None
                }
            
            # Get swing highs (resistance)
            buy_levels = self.swing_detector.get_buy_level(df)
            if buy_levels:
                self.swing_levels[symbol]['swing_high'] = buy_levels[0]['high']
                self.swing_levels[symbol]['buy_level'] = buy_levels[0]['high'] * (1 + self.entry_buffer)
                self.swing_levels[symbol]['swing_high_timestamp'] = buy_levels[0]['date'].strftime('%Y-%m-%d %H:%M:%S')
                self.logger.info(f"📈 {symbol} - Swing High: {self.swing_levels[symbol]['swing_high']:.2f} at {self.swing_levels[symbol]['swing_high_timestamp']}, "
                               f"Buy Level: {self.swing_levels[symbol]['buy_level']:.2f}")
            
            # Get swing lows (support)
            sell_levels = self.swing_detector.get_sell_level(df)
            if sell_levels:
                self.swing_levels[symbol]['swing_low'] = sell_levels[0]['low']
                self.swing_levels[symbol]['sell_level'] = sell_levels[0]['low'] * (1 - self.entry_buffer)
                self.swing_levels[symbol]['swing_low_timestamp'] = sell_levels[0]['date'].strftime('%Y-%m-%d %H:%M:%S')
                self.logger.info(f"📉 {symbol} - Swing Low: {self.swing_levels[symbol]['swing_low']:.2f} at {self.swing_levels[symbol]['swing_low_timestamp']}, "
                               f"Sell Level: {self.swing_levels[symbol]['sell_level']:.2f}")
            
            self.swing_levels[symbol]['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.last_swing_update = datetime.now()
            
        except Exception as e:
            self.logger.error(f"Error updating swing levels for {symbol}: {e}")
    
    def check_entry_signals(self, symbol, current_price):
        """Check for entry signals"""
        if symbol not in self.swing_levels:
            return None
        
        # Skip if already in position
        if symbol in self.positions and self.positions[symbol].get('position', 0) != 0:
            return None
        
        swing_data = self.swing_levels[symbol]
        
        # Long entry: Price breaks above swing high
        if swing_data.get('buy_level') and current_price > swing_data['buy_level']:
            self.logger.info(f"🚀 LONG SIGNAL: {symbol} price {current_price:.2f} > buy level {swing_data['buy_level']:.2f}")
            return 'LONG'
        
        # Short entry: Price breaks below swing low
        if swing_data.get('sell_level') and current_price < swing_data['sell_level']:
            self.logger.info(f"🔻 SHORT SIGNAL: {symbol} price {current_price:.2f} < sell level {swing_data['sell_level']:.2f}")
            return 'SHORT'
        
        return None
    
    def check_exit_signals(self, symbol, current_price):
        """Check for exit signals"""
        if symbol not in self.positions:
            return False
        
        position = self.positions[symbol]
        if position.get('position', 0) == 0 or not position.get('stop_loss'):
            return False
        
        # Long position exit
        if position['position'] == 1 and current_price < position['stop_loss']:
            self.logger.info(f"❌ LONG EXIT: {symbol} price {current_price:.2f} < SL {position['stop_loss']:.2f}")
            return True
        
        # Short position exit
        if position['position'] == -1 and current_price > position['stop_loss']:
            self.logger.info(f"❌ SHORT EXIT: {symbol} price {current_price:.2f} > SL {position['stop_loss']:.2f}")
            return True
        
        return False
    
    def enter_position(self, symbol, direction, current_price):
        """Enter a new position with actual order placement"""
        try:
            # Determine transaction type
            transaction_type = 'BUY' if direction == 'LONG' else 'SELL'
            
            # Place the order
            order_id = self.place_order(symbol, transaction_type)
            if not order_id:
                self.logger.error(f"❌ Failed to place {direction} order for {symbol}")
                return False
            
            # Initialize position if not exists
            if symbol not in self.positions:
                self.positions[symbol] = {
                    'position': 0, 'entry_price': None, 'stop_loss': None,
                    'entry_time': None, 'quantity': 0, 'order_id': None
                }
            
            position = self.positions[symbol]
            swing_data = self.swing_levels.get(symbol, {})
            
            if direction == 'LONG':
                position['position'] = 1
                position['entry_price'] = current_price
                position['entry_time'] = datetime.now()
                position['order_id'] = order_id
                
                # Set stop loss - use swing low or 1% below entry
                if swing_data.get('sell_level'):
                    position['stop_loss'] = swing_data['sell_level']
                else:
                    position['stop_loss'] = current_price * 0.99
                
                self.logger.info(f"✅ LONG POSITION ENTERED - {symbol} (Order ID: {order_id})")
                self.logger.info(f"   Entry: {position['entry_price']:.2f}")
                self.logger.info(f"   Stop Loss: {position['stop_loss']:.2f}")
                
            elif direction == 'SHORT':
                position['position'] = -1
                position['entry_price'] = current_price
                position['entry_time'] = datetime.now()
                position['order_id'] = order_id
                
                # Set stop loss - use swing high or 1% above entry
                if swing_data.get('buy_level'):
                    position['stop_loss'] = swing_data['buy_level']
                else:
                    position['stop_loss'] = current_price * 1.01
                
                self.logger.info(f"✅ SHORT POSITION ENTERED - {symbol} (Order ID: {order_id})")
                self.logger.info(f"   Entry: {position['entry_price']:.2f}")
                self.logger.info(f"   Stop Loss: {position['stop_loss']:.2f}")
            
            self.save_data()
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error entering position for {symbol}: {e}")
            return False
    
    def exit_position(self, symbol, current_price):
        """Exit current position with actual order placement"""
        try:
            if symbol not in self.positions:
                return False
            
            position = self.positions[symbol]
            if position.get('position', 0) == 0:
                return False
            
            # Determine exit transaction type (opposite of entry)
            if position['position'] == 1:  # Long position
                transaction_type = 'SELL'
                direction_text = 'LONG'
            else:  # Short position
                transaction_type = 'BUY'
                direction_text = 'SHORT'
            
            # Place exit order
            order_id = self.place_order(symbol, transaction_type)
            if not order_id:
                self.logger.error(f"❌ Failed to place exit order for {symbol}")
                return False
            
            # Calculate P&L
            if position['position'] == 1:  # Long
                pnl = current_price - position['entry_price']
                pnl_pct = (pnl / position['entry_price']) * 100
            else:  # Short
                pnl = position['entry_price'] - current_price
                pnl_pct = (pnl / position['entry_price']) * 100
            
            self.logger.info(f"📊 {direction_text} POSITION CLOSED - {symbol} (Exit Order ID: {order_id})")
            self.logger.info(f"   Entry: {position['entry_price']:.2f}")
            self.logger.info(f"   Exit: {current_price:.2f}")
            self.logger.info(f"   P&L: {pnl:.2f} ({pnl_pct:.2f}%)")
            
            # Reset position
            position['position'] = 0
            position['entry_price'] = None
            position['stop_loss'] = None
            position['entry_time'] = None
            position['order_id'] = None
            
            self.save_data()
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error exiting position for {symbol}: {e}")
            return False
    
    def update_trailing_stop(self, symbol):
        """Update trailing stop loss"""
        if (symbol not in self.positions or 
            symbol not in self.swing_levels or
            self.positions[symbol].get('position', 0) == 0):
            return
        
        try:
            position = self.positions[symbol]
            swing_data = self.swing_levels[symbol]
            
            if position['position'] == 1 and swing_data.get('sell_level'):  # Long position
                if swing_data['sell_level'] > position['stop_loss']:
                    old_sl = position['stop_loss']
                    position['stop_loss'] = swing_data['sell_level']
                    self.logger.info(f"📈 STOP LOSS TRAILED - {symbol}: {old_sl:.2f} → {position['stop_loss']:.2f}")
            
            elif position['position'] == -1 and swing_data.get('buy_level'):  # Short position
                if swing_data['buy_level'] < position['stop_loss']:
                    old_sl = position['stop_loss']
                    position['stop_loss'] = swing_data['buy_level']
                    self.logger.info(f"📉 STOP LOSS TRAILED - {symbol}: {old_sl:.2f} → {position['stop_loss']:.2f}")
            
        except Exception as e:
            self.logger.error(f"Error updating trailing stop for {symbol}: {e}")
    
    def update_all_swing_levels(self):
        """Update swing levels for all valid symbols"""
        valid_symbols = [s for s in self.tokens.keys() 
                       if s not in ['all_tickers', 'tickers', 'token_map', 'tokens_for_subscription']
                       and isinstance(self.tokens[s], (str, int))
                       and str(self.tokens[s]).strip().isdigit()]
        
        for symbol in valid_symbols:
            self.update_swing_levels(symbol)
    
    def log_live_prices(self):
        """Log current live prices for all symbols"""
        valid_symbols = [s for s in self.tokens.keys() 
                       if s not in ['all_tickers', 'tickers', 'token_map', 'tokens_for_subscription']
                       and isinstance(self.tokens[s], (str, int))
                       and str(self.tokens[s]).strip().isdigit()]
        
        price_info = []
        for symbol in valid_symbols:
            token = str(self.tokens[symbol]).strip()
            price = self.live_feed.get_live_price(token)
            if price:
                price_info.append(f"{symbol}:{price:.2f}")
        
        if price_info:
            self.logger.info(f"[PRICES] {' | '.join(price_info)}")
    
    def get_current_price(self, symbol):
        """Get current live price for a symbol"""
        if symbol not in self.tokens:
            return None
        
        token = str(self.tokens[symbol]).strip()
        return self.live_feed.get_live_price(token)
    
    def get_swing_levels(self, symbol):
        """Get current swing levels for a symbol"""
        return self.swing_levels.get(symbol, {})
    
    def buy_market(self, symbol, quantity=None):
        """Place a market buy order"""
        try:
            order_id = self.place_order(symbol, 'BUY', quantity)
            if order_id:
                current_price = self.get_current_price(symbol)
                self.logger.info(f"[BUY] {symbol} - Order ID: {order_id}, Price: {current_price:.2f}")
                return order_id
            return False
        except Exception as e:
            self.logger.error(f"[ERROR] Buy order failed for {symbol}: {e}")
            return False
    
    def sell_market(self, symbol, quantity=None):
        """Place a market sell order"""
        try:
            order_id = self.place_order(symbol, 'SELL', quantity)
            if order_id:
                current_price = self.get_current_price(symbol)
                self.logger.info(f"[SELL] {symbol} - Order ID: {order_id}, Price: {current_price:.2f}")
                return order_id
            return False
        except Exception as e:
            self.logger.error(f"[ERROR] Sell order failed for {symbol}: {e}")
            return False
    
    def check_order_status(self, order_id):
        """Check the status of an order"""
        status = self.get_order_status(order_id)
        self.logger.info(f"[ORDER] ID {order_id} - Status: {status}")
        return status
    
    def get_broker_positions(self):
        """Get current positions from broker"""
        positions = self.get_positions_from_broker()
        if positions:
            self.logger.info("[POSITIONS] Current broker positions:")
            for symbol, pos in positions.items():
                self.logger.info(f"   {symbol}: {pos['direction']} {pos['quantity']} @ {pos['avg_price']:.2f} (P&L: {pos['pnl']:.2f})")
        else:
            self.logger.info("[POSITIONS] No current positions")
        return positions
    
    def show_status(self):
        """Show current strategy status"""
        print("\n" + "=" * 50)
        print("STRATEGY STATUS")
        print("=" * 50)
        
        # Show live prices
        print("\n[LIVE PRICES]")
        valid_symbols = [s for s in self.tokens.keys() 
                       if s not in ['all_tickers', 'tickers', 'token_map', 'tokens_for_subscription']]
        
        for symbol in valid_symbols:
            price = self.get_current_price(symbol)
            if price:
                print(f"  {symbol}: {price:.2f}")
        
        # Show swing levels
        print("\n[SWING LEVELS]")
        for symbol in valid_symbols:
            levels = self.get_swing_levels(symbol)
            if levels:
                swing_high = levels.get('swing_high', 'N/A')
                buy_level = levels.get('buy_level', 'N/A')
                swing_high_time = levels.get('swing_high_timestamp', 'N/A')
                swing_low = levels.get('swing_low', 'N/A')
                sell_level = levels.get('sell_level', 'N/A')
                swing_low_time = levels.get('swing_low_timestamp', 'N/A')
                
                print(f"  {symbol}:")
                print(f"    Swing High: {swing_high} at {swing_high_time}")
                print(f"    Buy Level:  {buy_level}")
                print(f"    Swing Low:  {swing_low} at {swing_low_time}")
                print(f"    Sell Level: {sell_level}")
        
        # Show positions
        print("\n[POSITIONS]")
        positions = self.get_positions_from_broker()
        if positions:
            for symbol, pos in positions.items():
                print(f"  {symbol}: {pos['direction']} {pos['quantity']} @ {pos['avg_price']:.2f}")
        else:
            print("  No current positions")
        
        print("\n" + "=" * 50)
    
    def process_tick(self, symbol, current_price):
        """Process a price tick for a symbol - for monitoring only"""
        try:
            # Just log significant price movements (optional)
            if symbol in self.swing_levels:
                levels = self.swing_levels[symbol]
                buy_level = levels.get('buy_level')
                sell_level = levels.get('sell_level')
                
                # Log if price is near swing levels
                if buy_level and abs(current_price - buy_level) < (buy_level * 0.001):  # Within 0.1%
                    self.logger.info(f"[ALERT] {symbol} near BUY level: {current_price:.2f} (Target: {buy_level:.2f})")
                elif sell_level and abs(current_price - sell_level) < (sell_level * 0.001):  # Within 0.1%
                    self.logger.info(f"[ALERT] {symbol} near SELL level: {current_price:.2f} (Target: {sell_level:.2f})")
            
        except Exception as e:
            self.logger.error(f"[ERROR] Error processing tick for {symbol}: {e}")
    
    def run_strategy(self):
        """Main strategy execution loop - Feed only"""
        self.logger.info("[STRATEGY] Starting Live Data Feed...")
        self.logger.info(f"[SYMBOLS] Available: {list(self.tokens.keys())}")
        
        # Start live data feed
        if not self.live_feed.start_feed():
            self.logger.error("[ERROR] Failed to start live data feed")
            return
        
        if not self.live_feed.wait_for_data():
            self.logger.error("[ERROR] Failed to establish live data connection")
            return
        
        self.logger.info("[SUCCESS] Live feed established - Ready for trading")
        
        # Main monitoring loop
        while not self.shutdown_flag and datetime.now().time() < time(15, 30):
            try:
                current_time = datetime.now()
                
                # Update swing levels every hour
                if current_time - self.last_swing_update >= timedelta(hours=1):
                    self.logger.info("[UPDATE] Refreshing swing levels...")
                    self.update_all_swing_levels()
                    self.last_swing_update = current_time
                
                # Log live prices every 30 seconds
                if current_time.second % 30 == 0:
                    self.log_live_prices()
                
                # Check data freshness every 60 seconds
                if current_time.second % 60 == 0 and not self.live_feed.is_data_fresh():
                    self.logger.warning("[WARNING] Live data appears stale")
                
                # Save data every 5 minutes
                if current_time.minute % 5 == 0 and current_time.second == 0:
                    self.save_data()
                
                t.sleep(1)  # 1 second update interval
                
            except KeyboardInterrupt:
                self.logger.info("[STOP] Strategy stopped by user")
                break
            except Exception as e:
                self.logger.error(f"[ERROR] Main loop error: {e}")
                t.sleep(5)  # Wait before retrying
        
        self.logger.info("[END] Strategy monitoring stopped")
    
    def cleanup(self):
        """Cleanup resources"""
        try:
            self.save_data()
            self.live_feed.stop_feed()
            self.logger.info("✅ Cleanup completed")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
    
    def get_status(self):
        """Get current strategy status"""
        status = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'positions': {},
            'swing_levels': self.swing_levels,
            'data_fresh': self.live_feed.is_data_fresh()
        }
        
        for symbol in self.tokens.keys():
            if symbol in self.positions:
                pos = self.positions[symbol]
                status['positions'][symbol] = {
                    'position': pos.get('position', 0),
                    'entry_price': pos.get('entry_price'),
                    'stop_loss': pos.get('stop_loss'),
                    'entry_time': pos.get('entry_time'),
                    'order_id': pos.get('order_id')
                }
        
        return status


def main():
    """Main function"""
    try:
        # Initialize strategy
        strategy = TradingStrategy()
        
        # Display startup status
        print("=" * 50)
        print("SWING LEVELS STRATEGY - LIVE FEED")
        print("=" * 50)
        print(f"Symbols: {list(strategy.tokens.keys())}")
        print(f"API Status: {'Connected' if strategy.config.SMART_API_OBJ else 'Disconnected'}")
        print(f"Feed Status: Ready")
        print("-" * 50)
        print("Available Commands:")
        print("  strategy.show_status()     - Show current status")
        print("  strategy.buy_market(sym)   - Place buy order")
        print("  strategy.sell_market(sym)  - Place sell order")
        print("  strategy.get_current_price(sym) - Get live price")
        print("  strategy.get_broker_positions() - Show positions")
        print("=" * 50)
        
        # Run strategy
        strategy.run_strategy()
        
    except Exception as e:
        print(f"[ERROR] Fatal error: {e}")
        print(traceback.format_exc())
    finally:
        print("[END] Strategy execution completed")
        print("👋 Strategy execution completed")


if __name__ == "__main__":
    main()
