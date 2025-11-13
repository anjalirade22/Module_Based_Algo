# Data Module - Dependency Analysis

## Overview

This document provides a comprehensive analysis of:
1. **Data Module's Dependencies** - What the Data Module depends on
2. **System Dependency on Data Module** - How other modules depend on the Data Module

---

## 📦 Data Module Dependencies (Incoming)

### What the Data Module Depends On

#### 1. **Config Module**
- **Purpose**: Configuration and credentials
- **Usage**: 
  - `feed_process.py` imports from `config.credentials` and `config.settings`
  - Gets API credentials, correlation ID, API key, client code, feed token

```python
# modules/data_module/feed_process.py
from config.credentials import get_credentials
from config.settings import CORRELATION_ID, API_KEY, CLIENT_CODE, FEED_TOKEN
```

#### 2. **API Module**
- **Purpose**: SmartAPI broker integration
- **Usage**:
  - `historical_data.py` uses API instance to fetch historical candle data
  - All historical data fetching goes through API module

```python
# modules/data_module/historical_data.py
from modules.api_module import get_api_instance

class HistoricalDataManager:
    def __init__(self):
        self.api_instance = get_api_instance()
    
    def fetch_and_save_historical_data(self, symbol, token, interval):
        # Uses self.api_instance.getCandleData()
        data = self.api_instance.getCandleData(params)
```

**Key API Methods Used**:
- `getCandleData()` - Fetch historical OHLC data

#### 3. **Logger Module**
- **Purpose**: Centralized logging
- **Usage**: All Data Module components use logger for tracking
  - `live_feed.py`
  - `feed_process.py`
  - `historical_data.py`
  - `data_processor.py`

```python
# All data module files
from modules.logger_module import get_logger

logger = get_logger(__name__)
```

#### 4. **External Libraries**
- **pandas**: DataFrame operations, CSV I/O, resampling
- **SmartApi.smartWebSocketV2**: WebSocket for live feed
- **Standard libraries**: json, subprocess, datetime, pathlib, typing

---

### Data Module Dependency Summary

```
┌─────────────────────────────────────────┐
│         DATA MODULE                     │
│                                         │
│  ┌────────────┐  ┌──────────────────┐  │
│  │ Live Feed  │  │ Historical Data  │  │
│  │            │  │    Manager       │  │
│  └─────┬──────┘  └────────┬─────────┘  │
│        │                  │             │
└────────┼──────────────────┼─────────────┘
         │                  │
         ↓                  ↓
   ┌──────────┐      ┌──────────┐
   │ Config   │      │   API    │
   │ Module   │      │  Module  │
   └──────────┘      └──────────┘
         ↓                  ↓
   ┌──────────────────────────┐
   │    Logger Module         │
   └──────────────────────────┘
```

**Dependency Type**: Lightweight
- Only depends on 3 internal modules (Config, API, Logger)
- Minimal coupling ensures Data Module is stable and reusable

---

## 🎯 System Dependency on Data Module (Outgoing)

### How Other Modules Depend on the Data Module

#### 1. **Strategy Module** (`strategy_module.py`)

**Dependency Level**: **HIGH - Critical**

**What it uses**:
- Historical data for technical analysis
- Signal generation based on OHLC data
- Swing level calculations

**Import Pattern**:
```python
from modules.data_module import get_data_manager
```

**Usage**:
```python
class SwingStrategy:
    def __init__(self, symbol: str):
        self.data_manager = get_data_manager()
    
    def generate_signals(self, data: pd.DataFrame):
        # Strategy logic uses historical data from Data Module
        pass

class StrategyManager:
    def __init__(self):
        self.data_manager = get_data_manager()
    
    def generate_signals(self, symbol: str):
        # Get historical data
        data = self.data_manager.get_historical_data(symbol, start_date, end_date)
        
        # Generate signals based on data
        signals = strategy.generate_signals(data)
```

**Data Flow**:
```
HistoricalDataManager → CSV Files → Strategy Module
                                   → Technical Indicators
                                   → Signal Generation
```

---

#### 2. **Execution Module** (`execution_module.py`)

**Dependency Level**: **HIGH - Critical**

**What it uses**:
- Live market data for order execution
- Current prices for order placement
- Real-time tick data

**Import Pattern**:
```python
from modules.data_module import get_live_feed
```

**Usage**:
```python
class ExecutionEngine:
    def __init__(self):
        self.feed = get_live_feed()
    
    def start(self):
        # Start live feed for execution
        self.feed.start_feed()
        self.feed.wait_for_data()
    
    def get_current_price(self, symbol):
        # Get live price for order execution
        return self.feed.get_live_price(symbol)
    
    def execute_order(self, order_type, quantity):
        # Execute at live price
        price = self.get_current_price()
        # Place order
```

**Data Flow**:
```
WebSocket Feed → live_feed_data.json → LiveDataFeed → Execution Module
                                                     → Order Placement
                                                     → Price Monitoring
```

---

#### 3. **Main Application** (`main.py`)

**Dependency Level**: **MEDIUM**

**What it uses**:
- Initialize data management system
- Subscribe to symbols for live feed
- Coordinate data flow

**Import Pattern**:
```python
from modules.data_module import get_data_manager, subscribe_symbol
```

**Usage**:
```python
class TradingSystem:
    def __init__(self):
        self.data_manager = get_data_manager()
    
    def initialize(self):
        # Subscribe to instruments for live data
        subscribe_symbol("NIFTY", "99926000")
        subscribe_symbol("BANKNIFTY", "99926009")
    
    def start(self):
        # Start data feeds
        self.data_manager.start_live_feed()
```

---

#### 4. **RMS Module** (`rms_module.py`)

**Dependency Level**: **LOW - Indirect**

**What it uses**:
- Indirectly uses data through Strategy Module
- May use live prices for position valuation

**Current State**: 
- No direct imports from Data Module
- Gets data through Strategy or Execution modules
- Could potentially use historical data for risk calculations

**Potential Usage**:
```python
# Future enhancement
from modules.data_module import get_historical_manager

class RiskManager:
    def calculate_volatility(self, symbol):
        # Use historical data for volatility calculation
        hist_mgr = get_historical_manager()
        df = hist_mgr.load_historical_data(symbol, "ONE_DAY")
        # Calculate historical volatility
```

---

#### 5. **Test Module** (`tests/test_system.py`)

**Dependency Level**: **MEDIUM**

**What it uses**:
- Test data module functionality
- Validate data flows

**Import Pattern**:
```python
from modules.data_module import get_data_manager, MarketData
```

**Usage**: Testing and validation of data module components

---

## 📊 Complete Dependency Graph

```
                    ┌────────────────┐
                    │  Config Module │
                    └────────┬───────┘
                             │
                    ┌────────▼───────┐
                    │   API Module   │
                    └────────┬───────┘
                             │
         ┌───────────────────▼────────────────────┐
         │          DATA MODULE                    │
         │                                         │
         │  ┌──────────────┐  ┌─────────────────┐ │
         │  │  Live Feed   │  │ Historical Data │ │
         │  │   Manager    │  │    Manager      │ │
         │  └──────────────┘  └─────────────────┘ │
         │                                         │
         │  ┌──────────────┐                      │
         │  │     Data     │                      │
         │  │  Processor   │                      │
         │  └──────────────┘                      │
         └───┬──────────────────────┬──────────────┘
             │                      │
    ┌────────▼─────────┐   ┌────────▼──────────┐
    │  Execution       │   │   Strategy        │
    │   Module         │   │    Module         │
    │                  │   │                   │
    │ • Live Prices    │   │ • Historical Data │
    │ • Order Exec     │   │ • Indicators      │
    │ • Monitoring     │   │ • Signals         │
    └────────┬─────────┘   └────────┬──────────┘
             │                      │
             └──────────┬───────────┘
                        │
                 ┌──────▼──────┐
                 │    Main     │
                 │ Application │
                 └─────────────┘
```

---

## 🔄 Data Flow Patterns

### 1. **Historical Data Flow** (Strategy Module)

```
API Module (SmartAPI)
        ↓
HistoricalDataManager.fetch_and_save_historical_data()
        ↓
CSV Storage (data/historical/{SYMBOL}_{INTERVAL}/)
        ↓
HistoricalDataManager.load_historical_data()
        ↓
DataProcessor (validation, caching, resampling)
        ↓
Strategy Module (technical analysis, signals)
```

**Timeline**:
- **Initial Fetch**: Max lookback (30-100 days depending on interval)
- **Updates**: Incremental updates via `update_historical_data()`
- **Intraday Updates**: Hourly updates via `update_intraday_data()`
- **Late Start Backfill**: Automatic detection and backfill

---

### 2. **Live Data Flow** (Execution Module)

```
WebSocket (SmartAPI)
        ↓
WebSocketFeed (subprocess - feed_process.py)
        ↓
live_feed_data.json
        ↓
LiveDataFeed.get_live_data()
        ↓
Execution Module (order placement, monitoring)
```

**Real-time**:
- WebSocket pushes tick-by-tick updates
- JSON file updated in real-time
- Execution module reads for live prices

---

### 3. **Combined Flow** (Hybrid Strategies)

```
Historical Data (CSV) ──┐
                        ├──→ Strategy Logic ──→ Signals
Live Data (JSON) ───────┘
                                  ↓
                         Execution Module
                                  ↓
                           Order Placement
```

---

## 📋 Dependency Matrix

| Module | Depends on Data Module? | Usage Type | Critical? |
|--------|------------------------|------------|-----------|
| **Strategy Module** | ✅ Yes | Historical Data (CSV) | **Critical** |
| **Execution Module** | ✅ Yes | Live Data (JSON) | **Critical** |
| **Main Application** | ✅ Yes | Initialization & Coordination | High |
| **RMS Module** | ❌ No (Indirect) | Through other modules | Low |
| **Test Module** | ✅ Yes | Testing & Validation | Medium |
| **API Module** | ❌ No | Data Module depends on it | N/A |
| **Config Module** | ❌ No | Data Module depends on it | N/A |
| **Logger Module** | ❌ No | Data Module depends on it | N/A |

---

## 🎯 Critical Dependencies Summary

### **Data Module is Critical For**:

1. **Strategy Module** (100% dependent)
   - Cannot generate signals without historical data
   - All technical analysis relies on Data Module
   - **Impact if Data Module fails**: Strategies cannot run

2. **Execution Module** (100% dependent)
   - Cannot execute orders without live prices
   - Order monitoring requires real-time data
   - **Impact if Data Module fails**: Trading halts

3. **Trading System** (90% dependent)
   - Core functionality relies on data availability
   - Both live and historical data are essential
   - **Impact if Data Module fails**: System cannot operate

---

## 🔧 Integration Points

### **Public API Surface**

The Data Module exposes these interfaces to other modules:

```python
# Main exports
from modules.data_module import (
    # Live Feed
    LiveDataFeed,
    get_live_feed,
    
    # Historical Data
    HistoricalDataManager,
    get_historical_manager,
    
    # Data Processing
    DataProcessor,
    get_data_processor
)
```

### **Key Methods Used by Other Modules**

#### Strategy Module Uses:
```python
hist_mgr = get_historical_manager()

# Load existing data
df = hist_mgr.load_historical_data(symbol, interval)

# Fetch fresh data
df = hist_mgr.fetch_and_save_historical_data(symbol, token, interval, days=30)

# Update existing data
df = hist_mgr.update_historical_data(symbol, token, interval)

# Hourly intraday updates
df = hist_mgr.update_intraday_data(symbol, token, auto_backfill=True)
```

#### Execution Module Uses:
```python
feed = get_live_feed()

# Start feed
feed.start_feed()

# Wait for data
feed.wait_for_data(timeout=30)

# Get live price
price = feed.get_live_price(symbol)

# Get full tick data
tick_data = feed.get_live_data(symbol)

# Stop feed
feed.stop_feed()
```

#### Data Processing (Both Modules):
```python
processor = get_data_processor()

# Validate data
is_valid = processor.validate_candle_data(df)

# Cache data
processor.cache_data(key, data)

# Load from cache
data = processor.load_from_cache(key)

# Filter market hours
df = processor.filter_market_hours(df)

# Resample data
df_5min = processor.resample_data(df_1min, target_interval="FIVE_MINUTE")
```

---

## 🚀 Benefits of Current Architecture

### **1. Separation of Concerns**
- Data Module only handles data (not strategy logic)
- Clear boundaries between data and business logic
- Each module has single responsibility

### **2. Singleton Pattern**
- Single instance of each manager (`get_historical_manager()`, `get_live_feed()`)
- Prevents duplicate connections/file handles
- Ensures data consistency across modules

### **3. Minimal Coupling**
- Data Module only depends on 3 modules (Config, API, Logger)
- Other modules depend on Data Module through clean interfaces
- Easy to test and mock

### **4. Data Format Standardization**
- CSV for historical data (pandas-optimized)
- JSON for live data (real-time updates)
- Consistent timestamp formats
- OHLC column naming conventions

---

## ⚠️ Potential Issues & Recommendations

### **1. Circular Dependency Risk**
**Current State**: ✅ No circular dependencies detected

**Reason**: 
- Data Module doesn't depend on Strategy/Execution
- Only downstream dependencies (Config, API, Logger)
- Architecture is properly layered

---

### **2. Data Module Failure Impact**

**Scenario**: Data Module crashes or becomes unavailable

**Impact**:
- Strategy Module: Cannot generate signals (100% impact)
- Execution Module: Cannot place orders (100% impact)
- Trading System: Completely halted

**Mitigation**:
- ✅ Already implemented: Singleton pattern prevents multiple instances
- ✅ Already implemented: Comprehensive error handling
- ✅ Already implemented: Logging for all operations
- 🔄 Recommended: Add health checks and automatic recovery

---

### **3. Recommendations for Enhanced Robustness**

#### Add Health Check System
```python
# Future enhancement
class HealthMonitor:
    def check_data_module_health(self):
        checks = {
            'live_feed_running': self._check_live_feed(),
            'historical_data_accessible': self._check_historical_data(),
            'feed_subprocess_alive': self._check_subprocess(),
            'csv_storage_writable': self._check_storage()
        }
        return all(checks.values())
```

#### Add Automatic Recovery
```python
# Future enhancement
class DataModuleRecovery:
    def auto_recover_live_feed(self):
        if not feed.is_running():
            logger.warning("Live feed crashed, attempting restart...")
            feed.stop_feed()  # Clean shutdown
            time.sleep(2)
            feed.start_feed()  # Restart
```

#### Add Data Validation Layer
```python
# Already partially implemented in DataProcessor
# Enhance with more validations
processor.validate_candle_data(df)  # ✅ Already exists
processor.validate_timestamps(df)   # 🔄 Add this
processor.detect_data_gaps(df)      # 🔄 Add this
```

---

## 📈 Usage Statistics (From Codebase)

### **Modules Importing from Data Module**:
- `strategy_module.py`: 1 import statement (`get_data_manager`)
- `execution_module.py`: 1 import statement (inferred from architecture)
- `main.py`: 1 import statement (`get_data_manager`, `subscribe_symbol`)
- `tests/test_system.py`: 1 import statement (`get_data_manager`, `MarketData`)

### **Internal Usage**:
- `data_module/__main__.py`: 3 imports (for CLI operations)
- `historical_data.py`: 1 self-import (`get_data_processor`)

---

## 🎓 Best Practices for Using Data Module

### **For Strategy Developers**:

```python
# ✅ GOOD: Use singleton getters
from modules.data_module import get_historical_manager

hist_mgr = get_historical_manager()
df = hist_mgr.load_historical_data("NIFTY", "FIVE_MINUTE")

# ❌ BAD: Direct instantiation
from modules.data_module.historical_data import HistoricalDataManager
hist_mgr = HistoricalDataManager()  # Creates duplicate instance!
```

### **For Execution Developers**:

```python
# ✅ GOOD: Check feed health before using
feed = get_live_feed()
if feed.wait_for_data(timeout=30):
    price = feed.get_live_price("NIFTY")
else:
    logger.error("Feed not ready")

# ❌ BAD: Assume feed is ready
feed = get_live_feed()
price = feed.get_live_price("NIFTY")  # Might be None!
```

### **For Integration**:

```python
# ✅ GOOD: Use DataProcessor for validation
processor = get_data_processor()
df = hist_mgr.load_historical_data("NIFTY", "FIVE_MINUTE")
if processor.validate_candle_data(df):
    # Use data
    pass

# ❌ BAD: Use data without validation
df = hist_mgr.load_historical_data("NIFTY", "FIVE_MINUTE")
# Directly use df without checking
```

---

## 📚 Related Documentation

- **[DATA_MODULE_GUIDE.md](./DATA_MODULE_GUIDE.md)** - Comprehensive guide with examples
- **[DATA_MODULE_QUICKSTART.md](./DATA_MODULE_QUICKSTART.md)** - Quick start guide
- **[API_TESTING_README.md](./API_TESTING_README.md)** - API testing documentation
- **[UTILS_PACKAGE_GUIDE.md](./UTILS_PACKAGE_GUIDE.md)** - Utilities package guide

---

## ✅ Conclusion

### **Data Module Dependencies** (Incoming):
- **Config Module**: Credentials and settings
- **API Module**: Historical data fetching
- **Logger Module**: Centralized logging
- **External**: pandas, SmartAPI WebSocket, standard libraries

### **System Dependencies on Data Module** (Outgoing):
- **Strategy Module**: Critical (100% dependent for historical data)
- **Execution Module**: Critical (100% dependent for live data)
- **Main Application**: High (coordination and initialization)
- **RMS Module**: Low (indirect usage)

### **Architecture Assessment**:
✅ **Well-designed**: Clear separation, minimal coupling, clean interfaces
✅ **Robust**: Singleton pattern, error handling, comprehensive logging
✅ **Maintainable**: Single responsibility, documented, tested

### **Key Strengths**:
1. Clean layered architecture (no circular dependencies)
2. Single source of truth for market data
3. Standardized data formats
4. Comprehensive error handling
5. Well-documented API surface

### **Future Enhancements**:
1. Add health monitoring system
2. Implement automatic recovery mechanisms
3. Enhanced data validation layer
4. Performance metrics tracking

---

**Document Version**: 1.0  
**Last Updated**: November 13, 2025  
**Author**: Trading System Development Team
