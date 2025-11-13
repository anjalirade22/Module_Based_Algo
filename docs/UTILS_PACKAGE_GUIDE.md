# Utils Package - Documentation

## Overview

The Utils package provides essential utilities for instrument management and contract name generation in the trading system.

## 📦 **Package Structure**

```
utils/
├── __init__.py           # Package exports
├── instruments.py        # Instrument master & token lookup
└── contract_utils.py     # Futures/options contract names
```

## 🎯 **Key Features**

### **1. Smart Caching**
- Downloads instrument master **once** on first use
- Caches locally for 24 hours
- Subsequent calls use cached data (ultra-fast)
- Automatic refresh when cache expires

### **2. Instrument Master**
- Complete instrument database from Angel One
- Token lookup by symbol
- Symbol search functionality
- Support for all exchanges (NSE, NFO, BSE, etc.)

### **3. Contract Name Generation**
- Automatic futures contract names (current, next, far month)
- Option contract name generation
- Expiry date calculation
- Supports NIFTY, BANKNIFTY, FINNIFTY, and all symbols

---

## 🚀 **Quick Start**

### **Installation**

No additional dependencies required - uses standard libraries.

### **Basic Usage**

```python
from utils import get_instrument_master, get_futures_contracts

# Get instrument master (downloads and caches on first use)
inst = get_instrument_master()

# Get futures contracts
contracts = get_futures_contracts("NIFTY")
print(contracts)
# Output: ["NIFTY25NOVFUT", "NIFTY25DECFUT", "NIFTY26JANFUT"]

# Get token for a contract
token = inst.get_token(contracts[0], "NFO")
print(f"Token: {token}")
```

---

## 📚 **Detailed Usage**

### **Instrument Master**

#### **Initialize and Get Token**

```python
from utils import get_instrument_master

# Get singleton instance (cached)
inst = get_instrument_master()

# Get token for equity
token = inst.get_token("SBIN-EQ", "NSE")
print(f"SBIN Token: {token}")

# Get token for futures
token = inst.get_token("NIFTY25NOVFUT", "NFO")
print(f"NIFTY FUT Token: {token}")

# Get token for options
token = inst.get_token("NIFTY25NOV19500CE", "NFO")
print(f"NIFTY Option Token: {token}")
```

#### **Search Symbols**

```python
# Search for SBIN instruments
results = inst.search_symbol("SBIN", "NSE")

for r in results:
    print(f"{r['symbol']}: {r['token']} - {r['name']}")

# Output:
# SBIN-EQ: 3045 - STATE BANK OF INDIA
# SBIN-BE: 4884 - STATE BANK OF INDIA
# ...
```

#### **Get Instrument Details**

```python
# Get complete details by token
details = inst.get_instrument_details("3045")

print(f"Symbol: {details['symbol']}")
print(f"Name: {details['name']}")
print(f"Exchange: {details['exch_seg']}")
print(f"Lot Size: {details['lotsize']}")
```

#### **Get All Futures for a Symbol**

```python
# Get all NIFTY futures
futures = inst.get_futures_by_symbol("NIFTY", "NFO")

for f in futures:
    print(f"{f['symbol']}: Expires {f['expiry']}")

# Output:
# NIFTY25NOVFUT: Expires 27NOV2025
# NIFTY25DECFUT: Expires 25DEC2025
# NIFTY26JANFUT: Expires 29JAN2026
```

#### **Cache Management**

```python
# Check cache status
info = inst.get_cache_info()
print(f"Cache age: {info['age_hours']:.1f} hours")
print(f"Instruments: {info['count']}")
print(f"Valid: {info['is_valid']}")

# Force refresh cache
inst.refresh_cache()
```

---

### **Contract Name Generation**

#### **Get Futures Contracts**

```python
from utils import get_futures_contracts

# Get all three monthly contracts
contracts = get_futures_contracts("NIFTY")
# Returns: ["NIFTY25NOVFUT", "NIFTY25DECFUT", "NIFTY26JANFUT"]

# Get only current and next month
contracts = get_futures_contracts("BANKNIFTY", far_month=False)
# Returns: ["BANKNIFTY25NOVFUT", "BANKNIFTY25DECFUT"]

# Get only current month
contracts = get_futures_contracts("FINNIFTY", next_month=False, far_month=False)
# Returns: ["FINNIFTY25NOVFUT"]
```

#### **Get Individual Contracts**

```python
from utils.contract_utils import (
    get_current_month_contract,
    get_next_month_contract,
    get_far_month_contract
)

# Current month
current = get_current_month_contract("NIFTY")
print(current)  # NIFTY25NOVFUT

# Next month
next_month = get_next_month_contract("NIFTY")
print(next_month)  # NIFTY25DECFUT

# Far month
far = get_far_month_contract("NIFTY")
print(far)  # NIFTY26JANFUT
```

#### **Get Contracts with Expiry Dates**

```python
from utils.contract_utils import get_contract_expiry_dates

contracts = get_contract_expiry_dates("NIFTY")

for c in contracts:
    print(f"{c['contract']}: {c['expiry'].strftime('%d-%b-%Y')}")

# Output:
# NIFTY25NOVFUT: 27-Nov-2025
# NIFTY25DECFUT: 25-Dec-2025
# NIFTY26JANFUT: 29-Jan-2026
```

#### **Generate Option Contract Names**

```python
from utils.contract_utils import get_option_contract_name

# Current month NIFTY 19500 Call
contract = get_option_contract_name("NIFTY", 19500, "CE")
print(contract)  # NIFTY25NOV19500CE

# BANKNIFTY 44000 Put
contract = get_option_contract_name("BANKNIFTY", 44000, "PE")
print(contract)  # BANKNIFTY25NOV44000PE

# Specific month
contract = get_option_contract_name("NIFTY", 20000, "CE", year=2025, month=12)
print(contract)  # NIFTY25DEC20000CE
```

---

## 🔗 **Integration with Data Module**

### **Complete Workflow**

```python
from utils import get_instrument_master, get_futures_contracts
from modules.data_module import get_historical_manager

# Step 1: Get futures contracts
contracts = get_futures_contracts("NIFTY")
current_contract = contracts[0]
print(f"Trading: {current_contract}")

# Step 2: Get token
inst = get_instrument_master()
token = inst.get_token(current_contract, "NFO")
print(f"Token: {token}")

# Step 3: Fetch historical data
hist_mgr = get_historical_manager()
df = hist_mgr.fetch_and_save_historical_data(
    symbol=current_contract,
    token=token,
    exchange="NFO",
    interval="FIVE_MINUTE",
    days=10
)

print(f"Fetched {len(df)} candles for {current_contract}")
```

### **Strategy Integration**

```python
from utils import get_instrument_master, get_futures_contracts
from modules.data_module import get_historical_manager, get_data_processor

class FuturesStrategy:
    def __init__(self, symbol):
        self.symbol = symbol
        self.inst = get_instrument_master()
        self.hist_mgr = get_historical_manager()
        self.processor = get_data_processor()
        
    def load_data(self):
        # Get current month contract
        contracts = get_futures_contracts(self.symbol, next_month=False, far_month=False)
        contract = contracts[0]
        
        # Get token
        token = self.inst.get_token(contract, "NFO")
        
        if token is None:
            raise ValueError(f"Token not found for {contract}")
        
        # Load historical data
        df = self.hist_mgr.load_historical_data(contract, "FIVE_MINUTE")
        
        if df is None:
            # Fetch fresh
            df = self.hist_mgr.fetch_and_save_historical_data(
                symbol=contract,
                token=token,
                exchange="NFO",
                interval="FIVE_MINUTE",
                days=10
            )
        
        # Add indicators
        df = self.processor.add_sma(df, 20)
        df = self.processor.add_rsi(df, 14)
        
        return df
    
    def generate_signal(self):
        df = self.load_data()
        
        # Your strategy logic here
        latest_rsi = df['rsi_14'].iloc[-1]
        
        if latest_rsi < 30:
            return "BUY"
        elif latest_rsi > 70:
            return "SELL"
        else:
            return "HOLD"

# Usage
strategy = FuturesStrategy("NIFTY")
signal = strategy.generate_signal()
print(f"Signal: {signal}")
```

---

## 📁 **Cache Files**

### **Location**

```
Project Root/
└── data/
    └── cache/
        ├── instrument_master.json       # Cached instrument data
        └── instrument_master_meta.json  # Cache metadata
```

### **Cache Metadata Example**

```json
{
  "downloaded_at": "2025-11-13T10:30:00",
  "instrument_count": 45823,
  "source": "https://margincalculator.angelone.in/..."
}
```

### **Cache Validity**

- **Duration**: 24 hours
- **Auto-refresh**: Downloads automatically when expired
- **Manual refresh**: Call `inst.refresh_cache()`

---

## ⚙️ **Configuration**

### **Exchange Mappings**

The package automatically maps exchange codes:

```python
Exchange Codes:
- NSE  → NSE_CM  (Equity)
- NFO  → NFO_FO  (Futures & Options)
- BSE  → BSE_CM  (BSE Equity)
- BFO  → BFO_FO  (BSE F&O)
- MCX  → MCX_FO  (Commodities)
- CDS  → CDS_FO  (Currency)
```

### **Cache Settings**

```python
# In instruments.py (constants at top)
CACHE_VALIDITY_HOURS = 24  # Cache valid for 24 hours
```

---

## 🔧 **API Reference**

### **InstrumentMaster Class**

```python
class InstrumentMaster:
    def get_token(symbol: str, exchange: str = "NSE") -> Optional[str]
    def search_symbol(search_term: str, exchange: str = "NSE", limit: int = 10) -> List[Dict]
    def get_instrument_details(token: str) -> Optional[Dict]
    def get_futures_by_symbol(symbol: str, exchange: str = "NFO") -> List[Dict]
    def refresh_cache() -> bool
    def get_cache_info() -> Dict[str, Any]
```

### **Contract Utilities**

```python
def get_futures_contracts(symbol: str, current_month: bool = True, 
                         next_month: bool = True, far_month: bool = True) -> List[str]

def get_current_month_contract(symbol: str) -> str
def get_next_month_contract(symbol: str) -> str
def get_far_month_contract(symbol: str) -> str

def get_contract_expiry_dates(symbol: str) -> List[dict]
def get_monthly_expiry_date(year: int, month: int) -> datetime

def get_option_contract_name(symbol: str, strike: int, option_type: str,
                             year: Optional[int] = None, month: Optional[int] = None) -> str
```

---

## 🎯 **Performance**

### **First Call (Download)**
- Downloads ~45,000 instruments from Angel One
- Takes ~2-5 seconds (depending on network)
- Caches locally

### **Subsequent Calls (Cached)**
- Reads from local cache
- Takes ~0.1-0.2 seconds
- Ultra-fast token lookups

### **Cache Expiry**
- After 24 hours, automatically downloads fresh data
- Can manually refresh anytime

---

## 📊 **Example: Complete Trading Workflow**

```python
from utils import get_instrument_master, get_futures_contracts
from modules.data_module import get_historical_manager, get_live_feed

# 1. Get contracts for NIFTY
contracts = get_futures_contracts("NIFTY")
print(f"Available contracts: {contracts}")

# 2. Select current month
current_contract = contracts[0]
print(f"Trading: {current_contract}")

# 3. Get token
inst = get_instrument_master()
token = inst.get_token(current_contract, "NFO")
print(f"Token: {token}")

# 4. Get lot size
details = inst.get_instrument_details(token)
lot_size = details['lotsize']
print(f"Lot size: {lot_size}")

# 5. Fetch historical data
hist_mgr = get_historical_manager()
df = hist_mgr.fetch_and_save_historical_data(
    symbol=current_contract,
    token=token,
    exchange="NFO",
    interval="FIVE_MINUTE",
    days=10
)

print(f"Historical data: {len(df)} candles")

# 6. Start live feed
# Note: You'll need to configure feed_process.py with the token
feed = get_live_feed()
feed.start_feed()
feed.wait_for_data()

# 7. Get live price
live_price = feed.get_live_price()
print(f"Live price: {live_price}")

# 8. Stop feed
feed.stop_feed()
```

---

## 🐛 **Troubleshooting**

### **Issue: Cache Not Loading**

```python
# Force fresh download
inst = get_instrument_master(force_download=True)
```

### **Issue: Token Not Found**

```python
# Search to verify symbol format
inst = get_instrument_master()
results = inst.search_symbol("NIFTY", "NFO")

for r in results:
    print(f"{r['symbol']}: {r['token']}")

# Use exact symbol format from results
```

### **Issue: Network Error**

```python
# The package will try to use expired cache as fallback
# If cache exists, it will load old data
# Otherwise, retry download later
```

---

## ✅ **Best Practices**

1. **Use Singleton**: Always use `get_instrument_master()` for cached instance
2. **Check Cache**: Use `get_cache_info()` to monitor cache age
3. **Refresh Daily**: Consider refreshing cache at start of trading day
4. **Error Handling**: Always check if `get_token()` returns None
5. **Contract Validation**: Verify contract names before trading

---

## 🔄 **Daily Refresh Example**

```python
from utils import get_instrument_master
from datetime import datetime

def refresh_if_needed():
    inst = get_instrument_master()
    info = inst.get_cache_info()
    
    # Refresh if older than 12 hours
    if info['age_hours'] > 12:
        print("Refreshing instrument cache...")
        inst.refresh_cache()
        print("Cache refreshed!")
    else:
        print(f"Cache is fresh (age: {info['age_hours']:.1f} hours)")

# Call at start of trading day
refresh_if_needed()
```

---

**Version**: 1.0.0  
**Last Updated**: November 2025  
**Status**: ✅ Production Ready
