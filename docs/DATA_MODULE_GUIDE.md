# Data Module - Comprehensive Guide

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Installation](#installation)
4. [Components](#components)
5. [Live Data Feed](#live-data-feed)
6. [Historical Data](#historical-data)
7. [Data Processing](#data-processing)
8. [Integration Examples](#integration-examples)
9. [Configuration](#configuration)
10. [Troubleshooting](#troubleshooting)
11. [Best Practices](#best-practices)
12. [API Reference](#api-reference)

---

## Overview

The Data Module is a comprehensive market data management package for the trading system. It provides both live data streaming and historical data management with clean interfaces for Strategy and Execution modules.

### Key Features

- **Live Data Streaming**: WebSocket-based real-time market data via subprocess architecture
- **Historical Data**: CSV-based storage for historical candles
- **Data Processing**: Utilities for validation, caching, and technical indicators
- **Crash Isolation**: Feed runs in separate subprocess for reliability
- **Inter-Process Communication**: JSON-based data sharing
- **Clean Interface**: Simple API for other modules to consume data

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Data Module Architecture                     │
└─────────────────────────────────────────────────────────────────────┘

┌──────────┐
│  Config  │ (Credentials, API Settings)
└────┬─────┘
     │
     ↓
┌──────────┐
│   API    │ (SmartAPI Instance)
└────┬─────┘
     │
     ↓
┌─────────────────────────────────────────────────────────────────────┐
│                          Data Module                                 │
│  ┌────────────────────┐         ┌──────────────────────┐            │
│  │  LiveDataFeed      │         │ HistoricalDataManager│            │
│  │  - start_feed()    │         │ - fetch_data()       │            │
│  │  - get_price()     │         │ - save_to_csv()      │            │
│  │  - stop_feed()     │         │ - update_data()      │            │
│  └──────┬─────────────┘         └──────┬───────────────┘            │
│         │                              │                             │
│         │ manages                      │ writes                      │
│         ↓                              ↓                             │
│  ┌──────────────────┐         ┌──────────────────────┐              │
│  │  WebSocketFeed   │         │    CSV Files         │              │
│  │  (subprocess)    │         │  data/historical/    │              │
│  └──────┬───────────┘         └──────────────────────┘              │
│         │ writes                                                     │
│         ↓                                                            │
│  ┌──────────────────┐                                               │
│  │  data/live/      │                                               │
│  │ live_feed_data   │                                               │
│  │     .json        │                                               │
│  └──────────────────┘                                               │
└─────────────────────────────────────────────────────────────────────┘
     │                              │
     │ reads                        │ reads
     ↓                              ↓
┌──────────────┐         ┌──────────────────┐
│  Execution   │         │    Strategy      │
│   Module     │         │     Module       │
└──────────────┘         └──────────────────┘
```

### Data Flow

1. **Live Data Flow**:
   - Config → API → LiveDataFeed → WebSocketFeed (subprocess)
   - WebSocketFeed → live_feed_data.json
   - Execution Module reads JSON for live prices

2. **Historical Data Flow**:
   - Config → API → HistoricalDataManager
   - HistoricalDataManager → Data/*.csv
   - Strategy Module reads CSV for analysis

---

## Architecture

### Why Subprocess Architecture?

The Data Module uses a **subprocess-based** architecture for the live feed instead of threading. Here's why:

#### Advantages of Subprocess:

1. **Crash Isolation**: If the WebSocket feed crashes, it doesn't bring down the main trading application
2. **GIL Freedom**: Python's Global Interpreter Lock doesn't affect the feed process
3. **Clean Separation**: Feed process is completely independent
4. **Resource Management**: OS handles process cleanup automatically
5. **Monitoring**: Easy to monitor process health via PID

#### Data Sharing Strategy:

- **Live Data**: JSON file (`data/live/live_feed_data.json`)
  - Updated every 2 seconds by feed subprocess
  - Read by Execution module for live prices
  - Atomic writes to prevent corruption

- **Historical Data**: CSV files (`data/historical/*.csv`)
  - Written by HistoricalDataManager
  - Read by Strategy module for backtesting/analysis
  - Pandas-optimized format

### Process Communication

```
Main Process                      Feed Subprocess
┌─────────────────┐              ┌─────────────────┐
│  LiveDataFeed   │              │ WebSocketFeed   │
│                 │              │                 │
│  start_feed()   │─────────────>│   __init__()    │
│                 │   spawn       │                 │
│  validate()     │              │   connect()     │
│                 │              │                 │
│  get_price()    │<─────────────│  write_json()   │
│                 │   via JSON    │   every 2s      │
│  stop_feed()    │─────────────>│   cleanup()     │
│                 │   terminate   │                 │
└─────────────────┘              └─────────────────┘
        ↓                                 ↓
  Reads JSON                         Writes JSON
        ↓                                 ↓
┌──────────────────────────────────────────────────┐
│          live_feed_data.json                     │
│  {                                               │
│    "timestamp": "2024-01-01T09:15:30",          │
│    "data": [{                                    │
│      "trading_symbol": "NIFTY",                  │
│      "last_traded_price": 19520.50,              │
│      "volume": 1250000,                          │
│      "exchange_timestamp": "..."                 │
│    }]                                            │
│  }                                               │
└──────────────────────────────────────────────────┘
```

---

## Installation

### Prerequisites

```bash
# Python 3.11+
# SmartAPI library
pip install smartapi-python
pip install pandas
```

### Verify Installation

```python
# Test imports
from modules.data_module import (
    get_live_feed,
    get_historical_manager,
    get_data_processor
)

print("Data module imported successfully!")
```

---

## Components

### 1. LiveDataFeed

**Purpose**: Manages WebSocket feed subprocess for live market data

**Key Methods**:
- `start_feed()`: Start WebSocket subprocess
- `stop_feed()`: Stop subprocess gracefully
- `get_live_price()`: Get current live price
- `is_data_fresh()`: Check if data is recent
- `validate_feed_file()`: Validate JSON file

**Location**: `modules/data_module/live_feed.py`

### 2. WebSocketFeed (Subprocess)

**Purpose**: Independent process that connects to SmartAPI WebSocket

**Features**:
- Runs as separate process
- Writes to JSON every 2 seconds
- Automatic reconnection on errors
- Heartbeat monitoring

**Location**: `modules/data_module/feed_process.py`

### 3. HistoricalDataManager

**Purpose**: Fetch and store historical candle data

**Key Methods**:
- `fetch_historical_data()`: Fetch from API
- `save_to_csv()`: Save to CSV file
- `load_historical_data()`: Load from CSV
- `update_historical_data()`: Append new candles

**Location**: `modules/data_module/historical_data.py`

### 4. DataProcessor

**Purpose**: Data validation, caching, and processing utilities with market hours filtering

**Key Methods**:
- `validate_candle_data()`: Validate OHLC data
- `clean_candle_data()`: Clean and sort data
- `filter_market_hours()`: Remove candles after market close (15:30)
- `cache_data()`: Cache with TTL
- `resample_data()`: Resample to different timeframes (retains all candles including partial ones)
- `update_resampled_data()`: Automated resampling pipeline for all timeframes

**Market Hours Configuration**:
- `MARKET_OPEN = "09:15"`: Market opening time (IST)
- `MARKET_CLOSE = "15:30"`: Market closing time (IST)

**Data Handling**:
- Filters out candles after 15:30 for data cleanliness
- Retains all resampled candles including partial ones at end of day
- Ensures complete data coverage for all timeframes

**Location**: `modules/data_module/data_processor.py`

---

## Live Data Feed

### Starting the Feed

```python
from modules.data_module import get_live_feed

# Get feed instance
feed = get_live_feed()

# Start feed subprocess
if feed.start_feed():
    print("Feed started successfully")
    
    # Wait for data to be available
    if feed.wait_for_data(timeout=30):
        print("Data is ready")
    else:
        print("Timeout waiting for data")
else:
    print("Failed to start feed")
```

### Reading Live Prices

```python
# Get current live price
price = feed.get_live_price()
print(f"Current price: {price}")

# Check if data is fresh (updated within 5 seconds)
if feed.is_data_fresh(max_age_seconds=5):
    price = feed.get_live_price()
    print(f"Fresh price: {price}")
else:
    print("Data is stale, waiting...")
```

### Getting Complete Feed Data

```python
# Get complete tick data
data = feed.get_feed_data()

if data:
    tick = data['data'][0]  # First instrument
    print(f"Symbol: {tick['trading_symbol']}")
    print(f"Price: {tick['last_traded_price']}")
    print(f"Volume: {tick['volume']}")
    print(f"Timestamp: {tick['exchange_timestamp']}")
```

### Stopping the Feed

```python
# Stop feed gracefully
feed.stop_feed()
print("Feed stopped")
```

### Feed Lifecycle Management

```python
from modules.data_module import get_live_feed
import time

feed = get_live_feed()

# Start feed
feed.start_feed()
feed.wait_for_data()

try:
    # Trading loop
    while True:
        # Check data freshness
        if not feed.is_data_fresh():
            print("Data is stale, restarting feed...")
            feed.restart_feed()
            continue
        
        # Get live price
        price = feed.get_live_price()
        print(f"Live price: {price}")
        
        # Your trading logic here
        # ...
        
        time.sleep(1)
        
except KeyboardInterrupt:
    print("Stopping feed...")
    feed.stop_feed()
```

### JSON File Format

The feed writes to `live_feed_data.json` with this structure:

```json
{
  "timestamp": "2024-01-01T09:15:30.123456",
  "data": [
    {
      "trading_symbol": "NIFTY",
      "last_traded_price": 19520.50,
      "open": 19500.00,
      "high": 19550.00,
      "low": 19480.00,
      "close": 19520.50,
      "volume": 1250000,
      "exchange_timestamp": "01-Jan-2024 09:15:30"
    }
  ]
}
```

---

## Historical Data

### Fetching Historical Data

```python
from modules.data_module import get_historical_manager

# Get manager instance
hist_mgr = get_historical_manager()

# Fetch and save 5-minute data for last 5 days
df = hist_mgr.fetch_and_save_historical_data(
    symbol="NIFTY",
    token="99926000",
    exchange="NSE",
    interval="FIVE_MINUTE",
    days=5
)

if df is not None:
    print(f"Fetched {len(df)} candles")
    print(df.head())
```

### Supported Intervals

```python
# Available intervals
intervals = {
    "ONE_MINUTE": "1min",
    "THREE_MINUTE": "3min",
    "FIVE_MINUTE": "5min",
    "TEN_MINUTE": "10min",
    "FIFTEEN_MINUTE": "15min",
    "THIRTY_MINUTE": "30min",
    "ONE_HOUR": "1hour",
    "ONE_DAY": "1day"
}

# Example: Fetch 15-minute data
df = hist_mgr.fetch_and_save_historical_data(
    symbol="BANKNIFTY",
    token="99926009",
    interval="FIFTEEN_MINUTE",
    days=10
)
```

### Loading Existing Data

```python
# Load previously saved data
df = hist_mgr.load_historical_data("NIFTY", "FIVE_MINUTE")

if df is not None:
    print(f"Loaded {len(df)} candles")
    print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"Latest close: {df['close'].iloc[-1]}")
```

### Updating Historical Data

```python
# Update existing data with latest candles
df = hist_mgr.update_historical_data(
    symbol="NIFTY",
    token="99926000",
    interval="FIVE_MINUTE"
)

if df is not None:
    print(f"Updated data, total: {len(df)} candles")
    print(f"Latest: {df['timestamp'].max()}")
```

### Late Start / Partial-Day Backfill

The system automatically handles scenarios where the script starts after market open:

**Problem**: If your script starts at 13:45 instead of 9:15, you're missing morning data.

**Solution**: Automatic backfill detects and fills missing data from market open.

```python
# Automatic backfill when calling update_intraday_data
# If existing data is from previous day, automatically backfills missing morning data

df = hist_mgr.update_intraday_data(
    symbol="NIFTY",
    token="99926000",
    auto_backfill=True  # Default: True
)

# Manual backfill for specific time window
from datetime import datetime

start_time = datetime(2024, 1, 15, 9, 15)  # Market open
end_time = datetime(2024, 1, 15, 13, 15)    # Last complete hour

df = hist_mgr.backfill_intraday_data(
    symbol="NIFTY",
    token="99926000",
    start_time=start_time,
    end_time=end_time
)
```

**Backfill Scenarios**:

1. **Script starts during market hours** (e.g., 13:45):
   - Detects latest data is from previous day
   - Calculates last complete hour window (13:15)
   - Backfills from 9:15 to 13:15
   - Automatically resamples to all timeframes (3min, 5min, 10min, 15min, 30min, 1H)

2. **Script starts after market close** (e.g., 18:00):
   - Detects latest data is from previous day
   - Backfills full trading day from 9:15 to 15:30
   - Automatically resamples to all timeframes

3. **Script starts before market open** (e.g., 8:00):
   - No backfill needed
   - Normal hourly updates begin at 9:15

**Example Workflow**:
```python
# Day 1: Script ran normally, data up to 15:30
# Day 2: Script starts at 13:45 (late start!)

hist_mgr = get_historical_manager()

# First call detects late start and auto-backfills
df = hist_mgr.update_intraday_data("NIFTY", "99926000")

# Output:
# ⚠ Late start detected! Initiating automatic backfill...
# ============================================================
# BACKFILLING MISSING INTRADAY DATA
# ============================================================
# Symbol: NIFTY
# Window: 2024-01-16 09:15:00 → 2024-01-16 13:15:00
# Step 1: Fetching 1-minute data for missing window...
# ✓ Fetched 241 1-minute candles
# Step 2: Merging with existing 1-minute data...
# ✓ Merged: added 241 new candles, total: 1850
# Step 3: Saving updated 1-minute data...
# ✓ Saved 1850 1-minute candles to CSV
# Step 4: Resampling to higher timeframes...
# ✓ Resampling complete: 6/6 timeframes successful
#   ✓ 3min
#   ✓ 5min
#   ✓ 10min
#   ✓ 15min
#   ✓ 30min
#   ✓ 1H
# ============================================================
# BACKFILL COMPLETE
# ============================================================
```

**Benefits**:
- **Automatic**: No manual intervention needed
- **Complete Data**: All morning data backfilled seamlessly
- **Resampled**: All timeframes updated automatically
- **Intelligent**: Calculates last complete hour window
- **Handles Gaps**: Merges and deduplicates gracefully

### Custom Date Range

```python
from datetime import datetime

# Fetch specific date range
df = hist_mgr.fetch_historical_data(
    symbol="NIFTY",
    token="99926000",
    interval="FIVE_MINUTE",
    from_date=datetime(2024, 1, 1),
    to_date=datetime(2024, 1, 31)
)
```

### CSV File Format

Files are stored in `data/historical/` directory with format: `{SYMBOL}_{INTERVAL}.csv`

Example: `data/historical/NIFTY_FIVE_MINUTE.csv`

```csv
timestamp,open,high,low,close,volume
2024-01-01 09:15:00,19500.00,19520.00,19495.00,19510.00,1250000
2024-01-01 09:20:00,19510.00,19530.00,19505.00,19525.00,1180000
2024-01-01 09:25:00,19525.00,19540.00,19520.00,19535.00,1320000
```

### Listing Available Data

```python
# Get list of available data files
files = hist_mgr.get_available_data_files()

for f in files:
    print(f"Symbol: {f['symbol']}")
    print(f"Interval: {f['interval']}")
    print(f"Path: {f['filepath']}")
    print()
```

---

## Data Processing

### Data Validation

```python
from modules.data_module import get_data_processor

processor = get_data_processor()

# Validate candle data
if processor.validate_candle_data(df):
    print("Data is valid")
else:
    print("Data validation failed")

# Clean data (remove duplicates, sort, remove NaN)
df_clean = processor.clean_candle_data(df)
```

### Data Caching

```python
# Cache data with 5-minute TTL
processor.cache_data("nifty_data", df, ttl_seconds=300)

# Retrieve cached data
cached_df = processor.get_cached_data("nifty_data")

if cached_df is not None:
    print("Using cached data")
else:
    print("Cache miss or expired")

# Clear cache
processor.clear_cache("nifty_data")  # Clear specific key
processor.clear_cache()  # Clear all
```

### Resampling Data

```python
# Resample 1-minute data to 5-minute
df_5min = processor.resample_data(df, target_interval='5min')

# Resample to 15-minute
df_15min = processor.resample_data(df, target_interval='15min')

# Resample to hourly
df_hourly = processor.resample_data(df, target_interval='1H')
```

### Market Hours Filtering

```python
# Filter out any candles after market close (15:30)
df_filtered = processor.filter_market_hours(df)

# Market hours configuration
print(f"Market opens at: {processor.MARKET_OPEN}")  # 09:15
print(f"Market closes at: {processor.MARKET_CLOSE}")  # 15:30
```

### Resampling with Complete Data Coverage

The DataProcessor resamples data while retaining all candles including partial ones:

**Approach**: All candles are retained for complete data coverage across all timeframes.

**Benefits**:
- **Complete Data**: No data loss - all available market data is preserved
- **Flexibility**: Strategies can choose how to handle partial candles
- **Consistency**: Same behavior across all timeframes (5min, 15min, 30min, 1H)

```python
# Example: Resampling retains all candles
df_1min = hist_mgr.load_historical_data("NIFTY", "ONE_MINUTE")

# 5min: All candles including partial ones
df_5min = processor.resample_data(df_1min, target_interval='5min')
# Result: Includes all candles from 9:15 to last available data

# 15min: All candles including partial ones
df_15min = processor.resample_data(df_1min, target_interval='15min')
# Result: Includes all candles from 9:15 to last available data

# 30min: All candles including partial ones
df_30min = processor.resample_data(df_1min, target_interval='30min')
# Result: Includes all candles from 9:15 to last available data (e.g., 15:00)

# 1H: All candles including partial ones
df_1h = processor.resample_data(df_1min, target_interval='1H')
# Result: Includes all candles from 9:15 to last available data (e.g., 14:15)
```

**Market Close Filtering**:
- Only filters out candles with timestamps **after** 15:30
- All candles up to and including 15:30 are retained
- Last 15 minutes (15:15-15:30) creates valid candles for all timeframes

**Example Timeline**:
```
Market Hours: 09:15 ──────────────────────────────> 15:30

All Timeframes:
  - 5min:  Includes candles at 15:15, 15:20, 15:25, 15:30
  - 15min: Includes candle at 15:15 (covers 15:15-15:30)
  - 30min: Includes candle at 15:00 (covers 15:00-15:30, may be partial)
  - 1H:    Includes candle at 14:15 (covers 14:15-15:15, may be partial)

✓ All candles retained - no data loss
✓ Strategies can handle partial candles as needed
```

---

## Integration Examples

### Example 1: Execution Module Integration

```python
"""
Execution module reading live prices from Data Module
File: modules/execution_module.py
"""

from modules.data_module import get_live_feed
from modules.logger_module import get_logger
import time

logger = get_logger(__name__)

class ExecutionEngine:
    def __init__(self):
        self.feed = get_live_feed()
        self.logger = logger
        
    def start(self):
        """Start execution engine with live feed."""
        # Start live feed
        self.logger.info("Starting live feed...")
        if not self.feed.start_feed():
            self.logger.error("Failed to start feed")
            return False
        
        # Wait for data
        if not self.feed.wait_for_data(timeout=30):
            self.logger.error("Timeout waiting for feed data")
            return False
        
        self.logger.info("Live feed ready")
        return True
    
    def execute_order(self, order_type, quantity):
        """Execute order at live price."""
        # Get fresh live price
        if not self.feed.is_data_fresh(max_age_seconds=3):
            self.logger.warning("Data is stale, waiting for update...")
            time.sleep(1)
        
        # Get current price
        live_price = self.feed.get_live_price()
        
        if live_price is None:
            self.logger.error("No live price available")
            return False
        
        self.logger.info(f"Executing {order_type} order at {live_price}")
        
        # Execute order via API
        # ... order execution logic ...
        
        return True
    
    def stop(self):
        """Stop execution engine."""
        self.logger.info("Stopping live feed...")
        self.feed.stop_feed()


# Usage
if __name__ == "__main__":
    engine = ExecutionEngine()
    
    try:
        # Start engine
        engine.start()
        
        # Trading loop
        while True:
            # Check for signals and execute orders
            engine.execute_order("BUY", 1)
            time.sleep(5)
            
    except KeyboardInterrupt:
        engine.stop()
```

### Example 2: Strategy Module Integration

```python
"""
Strategy module reading historical data from Data Module
File: modules/strategy_module.py
"""

from modules.data_module import get_historical_manager, get_data_processor
from modules.logger_module import get_logger
import pandas as pd

logger = get_logger(__name__)

class MovingAverageCrossover:
    def __init__(self, symbol, token):
        self.symbol = symbol
        self.token = token
        self.hist_mgr = get_historical_manager()
        self.processor = get_data_processor()
        self.logger = logger
        
    def load_data(self, interval="FIVE_MINUTE", days=10):
        """Load historical data."""
        # Check if data exists
        df = self.hist_mgr.load_historical_data(self.symbol, interval)
        
        if df is None:
            # Fetch fresh data
            self.logger.info(f"Fetching {days} days of data...")
            df = self.hist_mgr.fetch_and_save_historical_data(
                symbol=self.symbol,
                token=self.token,
                interval=interval,
                days=days
            )
        else:
            # Update existing data
            self.logger.info("Updating existing data...")
            df = self.hist_mgr.update_historical_data(
                symbol=self.symbol,
                token=self.token,
                interval=interval
            )
        
        return df
    
    def generate_signals(self):
        """Generate trading signals based on MA crossover."""
        # Load data
        df = self.load_data()
        
        if df is None:
            self.logger.error("Failed to load data")
            return None
        
        # Validate data
        if not self.processor.validate_candle_data(df):
            self.logger.error("Data validation failed")
            return None
        
        # Your strategy logic here using clean OHLC data
        # For example: price action, custom indicators, etc.
        
        return "HOLD"


# Usage
if __name__ == "__main__":
    strategy = MovingAverageCrossover("NIFTY", "99926000")
    
    # Generate signals
    signal = strategy.generate_signals()
    print(f"Signal: {signal}")
```

### Example 3: Combined Live + Historical Strategy

```python
"""
Strategy that uses both live feed and historical data
"""

from modules.data_module import (
    get_live_feed,
    get_historical_manager,
    get_data_processor
)
from modules.logger_module import get_logger
import time

logger = get_logger(__name__)

class HybridStrategy:
    def __init__(self, symbol, token):
        self.symbol = symbol
        self.token = token
        self.feed = get_live_feed()
        self.hist_mgr = get_historical_manager()
        self.processor = get_data_processor()
        self.logger = logger
        
    def initialize(self):
        """Initialize strategy with data."""
        # Load historical data for analysis
        self.logger.info("Loading historical data...")
        self.df = self.hist_mgr.load_historical_data(self.symbol, "FIVE_MINUTE")
        
        if self.df is None:
            self.logger.info("Fetching fresh historical data...")
            self.df = self.hist_mgr.fetch_and_save_historical_data(
                symbol=self.symbol,
                token=self.token,
                interval="FIVE_MINUTE",
                days=10
            )
        
        # Validate data
        if not self.processor.validate_candle_data(self.df):
            self.logger.error("Data validation failed")
            return False
        
        # Start live feed
        self.logger.info("Starting live feed...")
        if not self.feed.start_feed():
            self.logger.error("Failed to start feed")
            return False
        
        if not self.feed.wait_for_data(timeout=30):
            self.logger.error("Timeout waiting for feed")
            return False
        
        self.logger.info("Strategy initialized successfully")
        return True
    
    def run(self):
        """Run strategy loop."""
        try:
            while True:
                # Get live price
                live_price = self.feed.get_live_price()
                
                if live_price is None:
                    time.sleep(1)
                    continue
                
                # Get latest historical values
                latest_close = self.df['close'].iloc[-1]
                latest_high = self.df['high'].iloc[-1]
                latest_low = self.df['low'].iloc[-1]
                
                # Your trading logic here
                # Example: Simple price-based logic
                if live_price > latest_high:
                    self.logger.info(f"BUY signal at {live_price}")
                    # Execute buy order
                    
                elif live_price < latest_low:
                    self.logger.info(f"SELL signal at {live_price}")
                    # Execute sell order
                
                time.sleep(5)
                
        except KeyboardInterrupt:
            self.logger.info("Stopping strategy...")
            self.feed.stop_feed()


# Usage
if __name__ == "__main__":
    strategy = HybridStrategy("NIFTY", "99926000")
    
    if strategy.initialize():
        strategy.run()
```

### Example 4: End-of-Day Resampling Workflow

```python
"""
Complete workflow showing end-of-day handling for all timeframes
"""

from modules.data_module import get_historical_manager, get_data_processor
from modules.logger_module import get_logger

logger = get_logger(__name__)

def demo_end_of_day_resampling():
    """Demonstrate smart end-of-day candle handling."""
    
    hist_mgr = get_historical_manager()
    processor = get_data_processor()
    
    # Step 1: Load 1-minute data for the day
    logger.info("Loading 1-minute data...")
    df_1min = hist_mgr.load_historical_data("NIFTY", "ONE_MINUTE")
    
    if df_1min is None:
        logger.error("Failed to load data")
        return
    
    # Step 2: Filter market hours (removes any candles after 15:30)
    logger.info(f"Original data: {len(df_1min)} candles")
    df_filtered = processor.filter_market_hours(df_1min)
    logger.info(f"After filtering: {len(df_filtered)} candles")
    
    # Step 3: Resample to different timeframes
    logger.info("\n" + "="*60)
    logger.info("RESAMPLING - ALL CANDLES RETAINED")
    logger.info("="*60)
    
    # 5-minute: All candles retained
    logger.info("\n5-Minute Timeframe:")
    df_5min = processor.resample_data(df_filtered, target_interval='5min')
    last_5_candles = df_5min.tail(5)
    logger.info(f"Total candles: {len(df_5min)}")
    logger.info("Last 5 candles:")
    for idx, row in last_5_candles.iterrows():
        logger.info(f"  {row['timestamp']} - Close: {row['close']}")
    logger.info("✓ All candles retained including 15:15, 15:20, 15:25")
    
    # 15-minute: All candles retained
    logger.info("\n15-Minute Timeframe:")
    df_15min = processor.resample_data(df_filtered, target_interval='15min')
    last_3_candles = df_15min.tail(3)
    logger.info(f"Total candles: {len(df_15min)}")
    logger.info("Last 3 candles:")
    for idx, row in last_3_candles.iterrows():
        logger.info(f"  {row['timestamp']} - Close: {row['close']}")
    logger.info("✓ All candles retained including 15:15 (covers 15:15-15:30)")
    
    # 30-minute: All candles retained including partial
    logger.info("\n30-Minute Timeframe:")
    df_30min = processor.resample_data(df_filtered, target_interval='30min')
    last_3_candles = df_30min.tail(3)
    logger.info(f"Total candles: {len(df_30min)}")
    logger.info("Last 3 candles:")
    for idx, row in last_3_candles.iterrows():
        logger.info(f"  {row['timestamp']} - Close: {row['close']}")
    logger.info("✓ All candles retained including 15:00 (partial candle covering 15:00-15:30)")
    
    # 1-hour: All candles retained including partial
    logger.info("\n1-Hour Timeframe:")
    df_1h = processor.resample_data(df_filtered, target_interval='1H')
    last_3_candles = df_1h.tail(3)
    logger.info(f"Total candles: {len(df_1h)}")
    logger.info("Last 3 candles:")
    for idx, row in last_3_candles.iterrows():
        logger.info(f"  {row['timestamp']} - Close: {row['close']}")
    logger.info("✓ All candles retained including 14:15 (partial candle covering 14:15-15:15)")
    
    # Step 4: Automated resampling for all timeframes
    logger.info("\n" + "="*60)
    logger.info("AUTOMATED RESAMPLING PIPELINE")
    logger.info("="*60)
    
    results = processor.update_resampled_data("NIFTY", df_1min)
    
    for timeframe, success in results.items():
        status = "✓" if success else "✗"
        logger.info(f"{status} {timeframe}: {'Success' if success else 'Failed'}")
    
    logger.info("\n" + "="*60)
    logger.info("All timeframes created - complete data coverage!")
    logger.info("="*60)


if __name__ == "__main__":
    demo_end_of_day_resampling()
```

### Example 5: Late Start Backfill Workflow

```python
"""
Handling late start scenarios with automatic backfill
"""

from modules.data_module import get_historical_manager
from modules.logger_module import get_logger
from datetime import datetime

logger = get_logger(__name__)

def demo_late_start_backfill():
    """Demonstrate automatic late-start backfill functionality."""
    
    hist_mgr = get_historical_manager()
    
    logger.info("="*60)
    logger.info("LATE START SCENARIO DEMONSTRATION")
    logger.info("="*60)
    logger.info("Scenario: Script starts at 13:45, last data was from previous day")
    logger.info("")
    
    # Simulate: Last data from previous day, script starting at 13:45
    logger.info("Calling update_intraday_data with auto_backfill=True...")
    
    df = hist_mgr.update_intraday_data(
        symbol="NIFTY",
        token="99926000",
        auto_backfill=True  # Enables automatic backfill
    )
    
    if df is not None:
        logger.info(f"\n✓ Success! Total 1-minute candles: {len(df)}")
        logger.info(f"Data range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        
        # Check if all timeframes were created
        import os
        timeframes = ['THREE_MINUTE', 'FIVE_MINUTE', 'TEN_MINUTE', 
                     'FIFTEEN_MINUTE', 'THIRTY_MINUTE', 'ONE_HOUR']
        
        logger.info("\nVerifying resampled timeframes:")
        for tf in timeframes:
            path = f"data/historical/NIFTY_{tf}/NIFTY_{tf}.csv"
            exists = os.path.exists(path)
            status = "✓" if exists else "✗"
            logger.info(f"  {status} {tf}: {'Created' if exists else 'Missing'}")
    else:
        logger.error("Failed to update data")
    
    logger.info("="*60)
    logger.info("DEMONSTRATION COMPLETE")
    logger.info("="*60)


def demo_manual_backfill():
    """Demonstrate manual backfill for specific time window."""
    
    hist_mgr = get_historical_manager()
    
    logger.info("="*60)
    logger.info("MANUAL BACKFILL DEMONSTRATION")
    logger.info("="*60)
    
    # Define custom backfill window
    start_time = datetime(2024, 1, 15, 9, 15)   # Market open
    end_time = datetime(2024, 1, 15, 12, 15)     # Specific end time
    
    logger.info(f"Backfilling from {start_time} to {end_time}")
    
    df = hist_mgr.backfill_intraday_data(
        symbol="BANKNIFTY",
        token="99926009",
        start_time=start_time,
        end_time=end_time
    )
    
    if df is not None:
        logger.info(f"\n✓ Backfill successful!")
        logger.info(f"Total candles: {len(df)}")
        logger.info(f"Time range: {df['timestamp'].min()} to {df['timestamp'].max()}")
        
        # Calculate expected candles (3 hours * 60 minutes + 1)
        expected = 181  # 9:15-12:15 = 181 minutes
        logger.info(f"Expected: ~{expected} candles, Actual: {len(df)}")
    
    logger.info("="*60)


def demo_post_market_backfill():
    """Demonstrate backfill when starting after market close."""
    
    hist_mgr = get_historical_manager()
    
    logger.info("="*60)
    logger.info("POST-MARKET BACKFILL DEMONSTRATION")
    logger.info("="*60)
    logger.info("Scenario: Script starts at 18:00, last data from previous day")
    logger.info("")
    
    # This will automatically detect post-market and backfill full day (9:15-15:30)
    df = hist_mgr.update_intraday_data(
        symbol="NIFTY",
        token="99926000",
        auto_backfill=True
    )
    
    if df is not None:
        logger.info(f"\n✓ Full day backfilled!")
        logger.info(f"Total candles: {len(df)}")
        
        # Market hours: 9:15 to 15:30 = 375 minutes
        today_candles = df[df['timestamp'].dt.date == datetime.now().date()]
        logger.info(f"Today's candles: {len(today_candles)}")
        logger.info(f"Expected: ~375 candles (full trading day)")
    
    logger.info("="*60)


if __name__ == "__main__":
    # Demo 1: Automatic late start detection
    demo_late_start_backfill()
    
    # Demo 2: Manual backfill for custom window
    demo_manual_backfill()
    
    # Demo 3: Post-market backfill
    demo_post_market_backfill()
```

**Output Example**:
```
============================================================
LATE START SCENARIO DEMONSTRATION
============================================================
Scenario: Script starts at 13:45, last data was from previous day

Calling update_intraday_data with auto_backfill=True...
⚠ Late start detected! Initiating automatic backfill...
============================================================
BACKFILLING MISSING INTRADAY DATA
============================================================
Symbol: NIFTY
Window: 2024-01-16 09:15:00 → 2024-01-16 13:15:00
Step 1: Fetching 1-minute data for missing window...
✓ Fetched 241 1-minute candles
Step 2: Merging with existing 1-minute data...
✓ Merged: added 241 new candles, total: 1850
Step 3: Saving updated 1-minute data...
✓ Saved 1850 1-minute candles to CSV
Step 4: Resampling to higher timeframes...
✓ Resampling complete: 6/6 timeframes successful
  ✓ 3min
  ✓ 5min
  ✓ 10min
  ✓ 15min
  ✓ 30min
  ✓ 1H
============================================================
BACKFILL COMPLETE
============================================================

✓ Success! Total 1-minute candles: 1850
Data range: 2024-01-15 09:15:00 to 2024-01-16 13:15:00

Verifying resampled timeframes:
  ✓ THREE_MINUTE: Created
  ✓ FIVE_MINUTE: Created
  ✓ TEN_MINUTE: Created
  ✓ FIFTEEN_MINUTE: Created
  ✓ THIRTY_MINUTE: Created
  ✓ ONE_HOUR: Created
============================================================
DEMONSTRATION COMPLETE
============================================================
```

**Output Example**:
```
============================================================
RESAMPLING - ALL CANDLES RETAINED
============================================================

5-Minute Timeframe:
Total candles: 75
Last 5 candles:
  2024-01-15 15:05:00 - Close: 19520.50
  2024-01-15 15:10:00 - Close: 19525.25
  2024-01-15 15:15:00 - Close: 19530.00
  2024-01-15 15:20:00 - Close: 19535.75
  2024-01-15 15:25:00 - Close: 19540.00
✓ All candles retained including 15:15, 15:20, 15:25

15-Minute Timeframe:
Total candles: 25
Last 3 candles:
  2024-01-15 14:45:00 - Close: 19515.00
  2024-01-15 15:00:00 - Close: 19522.50
  2024-01-15 15:15:00 - Close: 19538.25
✓ All candles retained including 15:15 (covers 15:15-15:30)

30-Minute Timeframe:
Total candles: 13
Last 3 candles:
  2024-01-15 14:00:00 - Close: 19505.25
  2024-01-15 14:30:00 - Close: 19518.75
  2024-01-15 15:00:00 - Close: 19537.50
✓ All candles retained including 15:00 (partial candle covering 15:00-15:30)

1-Hour Timeframe:
Total candles: 7
Last 3 candles:
  2024-01-15 12:15:00 - Close: 19475.50
  2024-01-15 13:15:00 - Close: 19495.25
  2024-01-15 14:15:00 - Close: 19528.75
✓ All candles retained including 14:15 (partial candle covering 14:15-15:15)
```

---

## Configuration

### WebSocket Subscription

To modify which instruments are subscribed in the live feed, edit `modules/data_module/feed_process.py`:

```python
# In WebSocketFeed.on_open() method
subscription_data = {
    "correlationID": CORRELATION_ID,
    "action": 1,  # 1 = Subscribe
    "params": {
        "mode": 3,  # 1=LTP, 2=Quote, 3=Snap Quote
        "tokenList": [
            {
                "exchangeType": 1,  # 1=NSE, 2=NFO, 3=BSE
                "tokens": [
                    "99926000",  # NIFTY 50
                    "99926009",  # BANKNIFTY
                    # Add more tokens here
                ]
            }
        ]
    }
}
```

### Feed Update Interval

To change how often the feed writes to JSON (default: 2 seconds):

```python
# In WebSocketFeed.__init__() method
self.write_interval = 2  # Change to desired interval in seconds
```

### Data Storage Locations

```python
# Live feed data
LIVE_FEED_FILE = "data/live/live_feed_data.json"

# Historical data
HISTORICAL_DATA_DIR = "data/historical/"

# Cache
CACHE_DIR = "data/cache/"
```

---

## Troubleshooting

### Issue 1: Feed Process Not Starting

**Symptoms**: `feed.start_feed()` returns False

**Solutions**:
1. Check credentials are configured:
   ```python
   from config.credentials import get_credentials
   creds = get_credentials()
   print(creds)
   ```

2. Check if feed script exists:
   ```python
   from pathlib import Path
   feed_script = Path("modules/data_module/feed_process.py")
   print(f"Exists: {feed_script.exists()}")
   ```

3. Check logs for errors:
   ```
   Check logs/ directory for error messages
   ```

### Issue 2: No Data in JSON File

**Symptoms**: `feed.get_live_price()` returns None

**Solutions**:
1. Check if feed file exists and is being updated:
   ```python
   feed_file = Path("live_feed_data.json")
   if feed_file.exists():
       print(f"Last modified: {datetime.fromtimestamp(feed_file.stat().st_mtime)}")
   ```

2. Verify WebSocket connection in logs

3. Check subscription tokens are correct

4. Verify market is open (live data only during market hours)

### Issue 3: Historical Data Fetch Fails

**Symptoms**: `fetch_historical_data()` returns None

**Solutions**:
1. Verify API instance is logged in:
   ```python
   from modules.api_module import get_api_instance
   api = get_api_instance()
   # Check if auth_token exists
   ```

2. Check token and exchange are correct

3. Verify date range (can't fetch future dates)

4. Check API rate limits

### Issue 4: Stale Data

**Symptoms**: `is_data_fresh()` returns False

**Solutions**:
1. Restart feed:
   ```python
   feed.restart_feed()
   ```

2. Check if feed process is still running:
   ```python
   if feed.feed_process:
       print(f"PID: {feed.feed_process.pid}")
       print(f"Running: {feed.feed_process.poll() is None}")
   ```

3. Check network connection

4. Verify WebSocket hasn't disconnected

### Issue 5: CSV File Corruption

**Symptoms**: Error loading historical data

**Solutions**:
1. Validate CSV file manually

2. Re-fetch data:
   ```python
   # Delete old file
   import os
   os.remove("data/historical/NIFTY_FIVE_MINUTE.csv")
   
   # Fetch fresh
   hist_mgr.fetch_and_save_historical_data(...)
   ```

3. Check disk space

---

## Best Practices

### 1. Feed Lifecycle Management

```python
# Always use try-finally to ensure cleanup
feed = get_live_feed()

try:
    feed.start_feed()
    feed.wait_for_data()
    
    # Your code here
    
finally:
    feed.stop_feed()
```

### 2. Data Validation

```python
# Always validate data before using
processor = get_data_processor()

df = hist_mgr.load_historical_data("NIFTY", "FIVE_MINUTE")

if df is not None and processor.validate_candle_data(df):
    # Safe to use data
    pass
else:
    # Handle invalid data
    pass
```

### 3. Error Handling

```python
# Handle potential failures gracefully
try:
    df = hist_mgr.fetch_and_save_historical_data(...)
    if df is None:
        logger.error("Failed to fetch data")
        # Fallback logic
except Exception as e:
    logger.error(f"Error: {e}", exc_info=True)
    # Error handling
```

### 4. Data Freshness Checks

```python
# Always check data freshness before trading
if feed.is_data_fresh(max_age_seconds=3):
    price = feed.get_live_price()
    # Execute trade
else:
    logger.warning("Data too old, skipping trade")
```

### 5. Caching for Performance

```python
# Cache data for performance
processor = get_data_processor()

# Check cache first
df = processor.get_cached_data("nifty_data")

if df is None:
    # Load and cache
    df = hist_mgr.load_historical_data("NIFTY", "FIVE_MINUTE")
    processor.cache_data("nifty_data", df, ttl_seconds=300)
```

### 6. Resource Cleanup

```python
# Proper cleanup on shutdown
import atexit

feed = get_live_feed()

def cleanup():
    feed.stop_feed()

atexit.register(cleanup)
```

### 7. Market Hours Filtering

```python
# Always filter market hours before processing
processor = get_data_processor()

# Load raw data
df_1min = hist_mgr.load_historical_data("NIFTY", "ONE_MINUTE")

# Filter out candles after market close (15:30)
df_filtered = processor.filter_market_hours(df_1min)

# Resample - all candles including partial ones are retained
df_5min = processor.resample_data(df_filtered, target_interval='5min')
df_30min = processor.resample_data(df_filtered, target_interval='30min')
df_1h = processor.resample_data(df_filtered, target_interval='1H')

# All timeframes include complete data coverage
# - 5min: Includes all candles up to last available data
# - 30min: Includes all candles including partial (e.g., 15:00-15:30)
# - 1H: Includes all candles including partial (e.g., 14:15-15:15)
```

### 8. Handling Partial Candles in Strategies

```python
# All timeframes retain partial candles for complete data coverage
# Strategies can choose how to handle them

# Option 1: Use all candles as-is
df_30min = processor.resample_data(df_1min, target_interval='30min')
# Uses all candles including last partial candle

# Option 2: Manually exclude last candle if partial
df_30min = processor.resample_data(df_1min, target_interval='30min')
df_30min_complete = df_30min.iloc[:-1]  # Exclude last candle
# Strategy-specific decision to handle partial data

# Option 3: Use all data for analysis
# Particularly useful for:
# - Real-time decision making
# - Complete market coverage
# - Exit signal generation
```

---

## API Reference

### LiveDataFeed

```python
class LiveDataFeed:
    """Manages live market data feed using subprocess."""
    
    def __init__(self, feed_file: str = "live_feed_data.json"):
        """Initialize LiveDataFeed."""
    
    def start_feed(self) -> bool:
        """Start feed subprocess. Returns True if successful."""
    
    def stop_feed(self) -> bool:
        """Stop feed subprocess. Returns True if successful."""
    
    def restart_feed(self) -> bool:
        """Restart feed subprocess. Returns True if successful."""
    
    def validate_feed_file(self) -> bool:
        """Validate feed file exists and has recent data."""
    
    def wait_for_data(self, timeout: int = 30) -> bool:
        """Wait for feed data to become available."""
    
    def get_live_price(self, symbol: Optional[str] = None) -> Optional[float]:
        """Get current live price."""
    
    def get_feed_data(self) -> Optional[Dict[str, Any]]:
        """Get complete feed data structure."""
    
    def is_data_fresh(self, max_age_seconds: int = 5) -> bool:
        """Check if data is fresh (recently updated)."""
```

### HistoricalDataManager

```python
class HistoricalDataManager:
    """Manages historical market data fetching and CSV storage."""
    
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
    
    def __init__(self, data_dir: str = "Data"):
        """Initialize HistoricalDataManager."""
    
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
        """Fetch historical candle data from SmartAPI."""
    
    def save_to_csv(self, df: pd.DataFrame, symbol: str, interval: str) -> bool:
        """Save DataFrame to CSV file."""
    
    def load_historical_data(self, symbol: str, interval: str) -> Optional[pd.DataFrame]:
        """Load historical data from CSV file."""
    
    def fetch_and_save_historical_data(...) -> Optional[pd.DataFrame]:
        """Fetch and save in one step."""
    
    def update_historical_data(
        self,
        symbol: str,
        token: str,
        exchange: str = "NSE",
        interval: str = "FIVE_MINUTE"
    ) -> Optional[pd.DataFrame]:
        """Update existing data with latest candles."""
    
    def get_available_data_files(self) -> List[Dict[str, str]]:
        """Get list of available CSV files."""
```

### DataProcessor

```python
class DataProcessor:
    """Utilities for processing and caching market data with market hours filtering."""
    
    # Market hours configuration (IST)
    MARKET_OPEN = "09:15"
    MARKET_CLOSE = "15:30"
    
    def __init__(self, cache_dir: str = "data/cache"):
        """Initialize DataProcessor."""
    
    def validate_candle_data(self, df: pd.DataFrame) -> bool:
        """Validate candle data DataFrame."""
    
    def clean_candle_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean data by removing duplicates and sorting."""
    
    def filter_market_hours(self, df: pd.DataFrame) -> pd.DataFrame:
        """Filter candle data to only include candles within market hours.
        
        Removes any candles with timestamps after market close (15:30).
        """
    
    def cache_data(self, key: str, data: Any, ttl_seconds: int = 300) -> bool:
        """Cache data with TTL."""
    
    def get_cached_data(self, key: str) -> Optional[Any]:
        """Get cached data if not expired."""
    
    def clear_cache(self, key: Optional[str] = None):
        """Clear cache."""
    
    def resample_data(self, df: pd.DataFrame, target_interval: str = '5min') -> pd.DataFrame:
        """Resample data to different timeframe.
        
        Filters out candles after market close but retains all candles including
        partial ones for complete data coverage. Strategies can choose how to
        handle partial candles based on their specific needs.
        """
    
    def update_resampled_data(
        self,
        symbol: str,
        df_1min: pd.DataFrame,
        timeframes: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """Automatically resample 1-minute data into multiple timeframes and save to CSV.
        
        Creates resampled versions for all supported timeframes (3min, 5min, 10min, 
        15min, 30min, 1H). All candles including partial ones are retained for
        complete data coverage.
        """
```


---

## Command Line Interface

The data module can be run from command line:

### Start Live Feed

```bash
python -m modules.data_module --live
```

### Fetch Historical Data

```bash
# Basic: 5 days of 5-minute data
python -m modules.data_module --historical NIFTY 99926000

# With custom interval and days
python -m modules.data_module --historical NIFTY 99926000 FIFTEEN_MINUTE 10
```

### Update Historical Data

```bash
# Update existing data with latest candles
python -m modules.data_module --update NIFTY 99926000

# With custom interval
python -m modules.data_module --update NIFTY 99926000 FIVE_MINUTE
```

### Run Tests

```bash
python -m modules.data_module --test
```

---

## Conclusion

The Data Module provides a robust, production-ready solution for managing both live and historical market data. Its subprocess architecture ensures reliability, while the clean interface makes integration with Strategy and Execution modules straightforward.

### Key Takeaways:

1. **Subprocess Architecture**: Feed runs independently for crash isolation
2. **JSON for Live Data**: Simple file-based IPC for live prices
3. **CSV for Historical**: Pandas-optimized format for backtesting
4. **Clean Interface**: Easy to integrate with other modules
5. **Comprehensive**: Covers live streaming, historical fetching, and data processing

### Next Steps:

1. Configure credentials in `config/credentials.py`
2. Test live feed: `python -m modules.data_module --live`
3. Fetch historical data for your symbols
4. Integrate with your strategy and execution modules
5. Monitor logs for any issues

For support, check the logs in `logs/` directory or refer to the main README.md.

---

**Version**: 1.0.0  
**Last Updated**: 2024  
**Author**: Trading System Development Team
