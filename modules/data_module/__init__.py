"""Data module for live and historical market data management.

This package provides comprehensive market data management with:
- Live data streaming via WebSocket (subprocess-based)
- Historical data fetching and CSV storage
- Data processing and caching utilities
- Clean interface for Strategy and Execution modules

Architecture:
    Config → API Module → Data Module
                ↓
    Live Data (JSON) → Execution Module
                ↓
    Historical Data (CSV) → Strategy Module

Components:
    - LiveDataFeed: Manages live data feed subprocess
    - HistoricalDataManager: Handles historical data in CSV format
    - DataProcessor: Data processing and caching utilities
    - feed_process: WebSocket subprocess (runs independently)

Usage:
    from modules.data_module import get_live_feed, get_historical_manager
    
    # Start live feed
    feed = get_live_feed()
    feed.start_feed()
    
    # Get historical data
    hist_mgr = get_historical_manager()
    hist_mgr.fetch_and_save_historical_data("NIFTY", "99926000")

For detailed documentation, see: docs/DATA_MODULE_GUIDE.md
"""

from .live_feed import LiveDataFeed, get_live_feed
from .historical_data import HistoricalDataManager, get_historical_manager
from .data_processor import DataProcessor, get_data_processor

__all__ = [
    'LiveDataFeed',
    'get_live_feed',
    'HistoricalDataManager',
    'get_historical_manager',
    'DataProcessor',
    'get_data_processor'
]

__version__ = '1.0.0'
__author__ = 'Trading System'
__description__ = 'Market data management package for live and historical data'
