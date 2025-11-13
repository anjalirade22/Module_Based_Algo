# Data Module - Quick Start Guide

## Installation Complete! 🎉

The Data Module has been successfully implemented in your trading system. Here's everything you need to know to get started.

## What's Been Created

### 📁 Package Structure

```
modules/data_module/
├── __init__.py              # Package exports and initialization
├── live_feed.py             # LiveDataFeed class (manages subprocess)
├── feed_process.py          # WebSocket feed subprocess
├── historical_data.py       # HistoricalDataManager class
├── data_processor.py        # DataProcessor utilities
└── __main__.py              # CLI entry point
```

### 📄 Documentation

```
docs/
└── DATA_MODULE_GUIDE.md     # Comprehensive 400+ line guide
```

## Quick Test

### 1. Test Module Import

```python
from modules.data_module import (
    get_live_feed,
    get_historical_manager,
    get_data_processor
)

print("✓ Data module imported successfully!")
```

### 2. Test Historical Data

```python
from modules.data_module import get_historical_manager

# Fetch 5 days of NIFTY data
hist_mgr = get_historical_manager()
df = hist_mgr.fetch_and_save_historical_data(
    symbol="NIFTY",
    token="99926000",
    interval="FIVE_MINUTE",
    days=5
)

if df is not None:
    print(f"✓ Fetched {len(df)} candles")
    print(df.head())
```

### 3. Test Live Feed (During Market Hours)

```python
from modules.data_module import get_live_feed
import time

feed = get_live_feed()

# Start feed
if feed.start_feed():
    print("✓ Feed started")
    
    # Wait for data
    if feed.wait_for_data(timeout=30):
        print("✓ Data available")
        
        # Get price
        price = feed.get_live_price()
        print(f"✓ Live price: {price}")
    
    # Stop feed
    feed.stop_feed()
    print("✓ Feed stopped")
```

## Command Line Usage

### Fetch Historical Data

```bash
# Fetch 5 days of 5-minute NIFTY data
python -m modules.data_module --historical NIFTY 99926000

# Fetch 10 days of 15-minute data
python -m modules.data_module --historical NIFTY 99926000 FIFTEEN_MINUTE 10
```

### Update Existing Data

```bash
# Update with latest candles
python -m modules.data_module --update NIFTY 99926000
```

### Start Live Feed

```bash
# Start live feed (Ctrl+C to stop)
python -m modules.data_module --live
```

### Run Tests

```bash
python -m modules.data_module --test
```

## Integration Examples

### Example 1: Execution Module

```python
# modules/execution_module.py

from modules.data_module import get_live_feed

class ExecutionEngine:
    def __init__(self):
        self.feed = get_live_feed()
    
    def start(self):
        self.feed.start_feed()
        self.feed.wait_for_data()
    
    def get_current_price(self):
        return self.feed.get_live_price()
    
    def stop(self):
        self.feed.stop_feed()
```

### Example 2: Strategy Module

```python
# modules/strategy_module.py

from modules.data_module import get_historical_manager, get_data_processor

class MovingAverageStrategy:
    def __init__(self):
        self.hist_mgr = get_historical_manager()
        self.processor = get_data_processor()
    
    def analyze(self, symbol, token):
        # Load historical data
        df = self.hist_mgr.load_historical_data(symbol, "FIVE_MINUTE")
        
        # Add indicators
        df = self.processor.add_sma(df, period=20)
        df = self.processor.add_rsi(df, period=14)
        
        # Generate signal
        if df['close'].iloc[-1] > df['sma_20'].iloc[-1]:
            return "BUY"
        else:
            return "SELL"
```

## Architecture Overview

```
┌──────────┐
│  Config  │ → Credentials, API Settings
└────┬─────┘
     │
     ↓
┌──────────┐
│   API    │ → SmartAPI Instance
└────┬─────┘
     │
     ↓
┌─────────────────────────────────────┐
│         Data Module                  │
│  ┌──────────────┐  ┌──────────────┐ │
│  │ LiveDataFeed │  │ Historical   │ │
│  │  (Manager)   │  │ DataManager  │ │
│  └──────┬───────┘  └──────┬───────┘ │
│         │                 │          │
│         ↓                 ↓          │
│  ┌──────────────┐  ┌──────────────┐ │
│  │ WebSocket    │  │ CSV Files    │ │
│  │ (subprocess) │  │ Data/*.csv   │ │
│  └──────┬───────┘  └──────────────┘ │
│         │                            │
│         ↓                            │
│  ┌──────────────┐                   │
│  │ live_feed    │                   │
│  │  _data.json  │                   │
│  └──────────────┘                   │
└─────────────────────────────────────┘
     │                    │
     │                    │
     ↓                    ↓
┌──────────────┐   ┌──────────────┐
│  Execution   │   │   Strategy   │
│   Module     │   │    Module    │
└──────────────┘   └──────────────┘
```

## Key Features

### ✅ Subprocess Architecture
- Feed runs independently from main process
- Crash isolation - feed crash won't affect trading
- No GIL contention

### ✅ JSON for Live Data
- Simple file-based IPC
- Updated every 2 seconds
- Easy to read from any module

### ✅ CSV for Historical Data
- Pandas-optimized format
- One file per symbol/interval
- Easy backtesting

### ✅ Data Processing
- Validation utilities
- Technical indicators (SMA, EMA, RSI)
- Caching with TTL
- Resampling

## File Locations

### Live Feed Data
```
Project Root/
└── data/
    └── live/
        └── live_feed_data.json    # Updated by feed subprocess
```

### Historical Data
```
Project Root/
└── data/
    └── historical/
        ├── NIFTY_FIVE_MINUTE.csv
        ├── NIFTY_FIFTEEN_MINUTE.csv
        ├── BANKNIFTY_FIVE_MINUTE.csv
        └── ... (one file per symbol/interval)
```

### Cache
```
Project Root/
└── data/
    └── cache/
        └── cache.json     # Optional disk cache
```

## Configuration

### Modify WebSocket Subscriptions

Edit `modules/data_module/feed_process.py`:

```python
# In WebSocketFeed.on_open() method
"tokenList": [
    {
        "exchangeType": 1,  # NSE
        "tokens": [
            "99926000",     # NIFTY 50
            "99926009",     # BANKNIFTY
            # Add more tokens here
        ]
    }
]
```

### Change Feed Update Interval

Edit `modules/data_module/feed_process.py`:

```python
# In WebSocketFeed.__init__()
self.write_interval = 2  # seconds (default: 2)
```

## Common Operations

### Get Live Price
```python
from modules.data_module import get_live_feed

feed = get_live_feed()
feed.start_feed()
feed.wait_for_data()

price = feed.get_live_price()
print(f"Current price: {price}")

feed.stop_feed()
```

### Fetch Historical Data
```python
from modules.data_module import get_historical_manager

hist_mgr = get_historical_manager()

# Fetch and save
df = hist_mgr.fetch_and_save_historical_data(
    symbol="NIFTY",
    token="99926000",
    interval="FIVE_MINUTE",
    days=5
)
```

### Load Existing Data
```python
from modules.data_module import get_historical_manager

hist_mgr = get_historical_manager()

# Load from CSV
df = hist_mgr.load_historical_data("NIFTY", "FIVE_MINUTE")
```

### Add Technical Indicators
```python
from modules.data_module import get_data_processor

processor = get_data_processor()

# Add indicators
df = processor.add_sma(df, period=20)
df = processor.add_ema(df, period=50)
df = processor.add_rsi(df, period=14)
```

### Cache Data
```python
from modules.data_module import get_data_processor

processor = get_data_processor()

# Cache for 5 minutes
processor.cache_data("my_data", df, ttl_seconds=300)

# Retrieve
cached = processor.get_cached_data("my_data")
```

## Troubleshooting

### Feed Not Starting?
1. Check credentials are configured
2. Verify `feed_process.py` exists
3. Check logs for errors

### No Live Data?
1. Ensure market is open
2. Check WebSocket subscription tokens
3. Verify network connection
4. Check `live_feed_data.json` is being updated

### Historical Data Fails?
1. Verify API is logged in
2. Check token and exchange are correct
3. Ensure date range is valid
4. Check API rate limits

## Next Steps

1. ✅ **Test the module** - Run `python -m modules.data_module --test`

2. ✅ **Fetch some data** - Get historical data for your symbols

3. ✅ **Test live feed** - Start feed during market hours

4. ✅ **Integrate** - Use in your Strategy and Execution modules

5. ✅ **Read the guide** - Check `docs/DATA_MODULE_GUIDE.md` for detailed examples

## Documentation

📖 **Complete Guide**: `docs/DATA_MODULE_GUIDE.md`
- 400+ lines of comprehensive documentation
- Architecture explanations
- Integration examples
- Troubleshooting
- Best practices
- API reference

## Support

If you encounter issues:

1. Check the logs in `logs/` directory
2. Review `docs/DATA_MODULE_GUIDE.md`
3. Run tests: `python -m modules.data_module --test`
4. Verify credentials and API connection

---

**Version**: 1.0.0  
**Status**: ✅ Ready for Use  
**Last Updated**: 2024

Happy Trading! 🚀
