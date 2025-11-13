"""Instrument master management and token lookup.

This module handles downloading, caching, and querying the instrument
master from Angel One. The master file is downloaded once and cached
locally to avoid repeated downloads.

Key Features:
    - Download instrument master from Angel One
    - Cache locally with automatic expiry (24 hours)
    - Fast token lookup by symbol
    - Symbol search functionality
    - Support for all exchanges (NSE, NFO, BSE, etc.)

Usage:
    from utils import get_instrument_master
    
    # Get cached instance
    inst = get_instrument_master()
    
    # Get token
    token = inst.get_token("NIFTY25NOVFUT", "NFO")
    
    # Search symbol
    results = inst.search_symbol("SBIN", "NSE")
"""

import json
import requests
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from modules.logger_module import get_logger

# Constants
INSTRUMENT_MASTER_URL = "https://margincalculator.angelone.in/OpenAPI_File/files/OpenAPIScripMaster.json"
CACHE_FILE_NAME = "instrument_master.json"
CACHE_METADATA_FILE = "instrument_master_meta.json"
CACHE_VALIDITY_HOURS = 24

# Global instance
_instrument_master_instance = None

logger = get_logger(__name__)


def get_instrument_master(force_download: bool = False):
    """Get singleton instance of InstrumentMaster.
    
    Args:
        force_download: Force fresh download even if cache is valid
        
    Returns:
        InstrumentMaster: Singleton instance with cached instrument data
        
    Example:
        >>> inst = get_instrument_master()
        >>> token = inst.get_token("SBIN-EQ", "NSE")
    """
    global _instrument_master_instance
    
    if _instrument_master_instance is None:
        _instrument_master_instance = InstrumentMaster()
    
    if force_download:
        _instrument_master_instance.download_instruments(force=True)
    
    return _instrument_master_instance


class InstrumentMaster:
    """Manages instrument master data with smart caching.
    
    This class downloads the instrument master from Angel One and caches
    it locally. The cache is valid for 24 hours, after which it will be
    refreshed automatically. This prevents repeated downloads of the large
    file and improves performance.
    
    Attributes:
        cache_dir (Path): Directory for cached files
        cache_file (Path): Path to cached instrument data
        metadata_file (Path): Path to cache metadata
        instruments (pd.DataFrame): Loaded instrument data
        
    Example:
        >>> inst = InstrumentMaster()
        >>> 
        >>> # First time downloads and caches
        >>> token = inst.get_token("SBIN-EQ", "NSE")
        >>> 
        >>> # Subsequent calls use cache (fast)
        >>> token2 = inst.get_token("RELIANCE-EQ", "NSE")
    """
    
    def __init__(self, cache_dir: str = "data/cache"):
        """Initialize InstrumentMaster.
        
        Args:
            cache_dir: Directory for cache files (default: data/cache)
        """
        self.logger = get_logger(__name__)
        
        # Setup cache directory
        project_root = Path(__file__).parent.parent
        self.cache_dir = project_root / cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.cache_file = self.cache_dir / CACHE_FILE_NAME
        self.metadata_file = self.cache_dir / CACHE_METADATA_FILE
        
        # Instrument data (lazy loaded)
        self.instruments: Optional[pd.DataFrame] = None
        
        # Load instruments (from cache or download)
        self._load_instruments()
        
        self.logger.info("InstrumentMaster initialized")
    
    def _is_cache_valid(self) -> bool:
        """Check if cached data is still valid.
        
        Returns:
            bool: True if cache exists and is less than 24 hours old
        """
        try:
            if not self.cache_file.exists() or not self.metadata_file.exists():
                return False
            
            # Read metadata
            with open(self.metadata_file, 'r') as f:
                metadata = json.load(f)
            
            # Check cache age
            cached_time = datetime.fromisoformat(metadata['downloaded_at'])
            age = datetime.now() - cached_time
            
            if age.total_seconds() > CACHE_VALIDITY_HOURS * 3600:
                self.logger.info(f"Cache expired (age: {age.total_seconds() / 3600:.1f} hours)")
                return False
            
            self.logger.info(f"Using cached instruments (age: {age.total_seconds() / 3600:.1f} hours)")
            return True
            
        except Exception as e:
            self.logger.error(f"Error checking cache validity: {e}")
            return False
    
    def _load_from_cache(self) -> bool:
        """Load instruments from cached file.
        
        Returns:
            bool: True if loaded successfully, False otherwise
        """
        try:
            self.logger.info(f"Loading instruments from cache: {self.cache_file}")
            
            with open(self.cache_file, 'r') as f:
                data = json.load(f)
            
            self.instruments = pd.DataFrame(data)
            
            self.logger.info(f"Loaded {len(self.instruments)} instruments from cache")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading from cache: {e}", exc_info=True)
            return False
    
    def _save_to_cache(self, data: List[Dict]) -> bool:
        """Save instruments to cache file.
        
        Args:
            data: List of instrument dictionaries
            
        Returns:
            bool: True if saved successfully, False otherwise
        """
        try:
            self.logger.info(f"Saving {len(data)} instruments to cache")
            
            # Save instrument data
            with open(self.cache_file, 'w') as f:
                json.dump(data, f)
            
            # Save metadata
            metadata = {
                'downloaded_at': datetime.now().isoformat(),
                'instrument_count': len(data),
                'source': INSTRUMENT_MASTER_URL
            }
            
            with open(self.metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            self.logger.info(f"Cached instruments successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving to cache: {e}", exc_info=True)
            return False
    
    def download_instruments(self, force: bool = False) -> bool:
        """Download instrument master from Angel One.
        
        Downloads the complete instrument list and caches it locally.
        If cache is valid and force=False, skips download.
        
        Args:
            force: Force download even if cache is valid (default: False)
            
        Returns:
            bool: True if download/load successful, False otherwise
            
        Example:
            >>> inst = InstrumentMaster()
            >>> 
            >>> # Normal load (uses cache if valid)
            >>> inst.download_instruments()
            >>> 
            >>> # Force fresh download
            >>> inst.download_instruments(force=True)
        """
        try:
            # Check if cache is valid
            if not force and self._is_cache_valid():
                return self._load_from_cache()
            
            # Download from Angel One
            self.logger.info(f"Downloading instruments from: {INSTRUMENT_MASTER_URL}")
            
            response = requests.get(INSTRUMENT_MASTER_URL, timeout=30)
            response.raise_for_status()
            
            # Parse JSON
            data = response.json()
            
            if not isinstance(data, list):
                self.logger.error("Invalid response format (expected list)")
                return False
            
            self.logger.info(f"Downloaded {len(data)} instruments")
            
            # Save to cache
            if self._save_to_cache(data):
                # Load into DataFrame
                self.instruments = pd.DataFrame(data)
                self.logger.info("Instruments loaded successfully")
                return True
            else:
                # Even if cache save fails, keep data in memory
                self.instruments = pd.DataFrame(data)
                self.logger.warning("Cache save failed, but data loaded in memory")
                return True
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error downloading instruments: {e}")
            # Try to load from cache as fallback
            if self.cache_file.exists():
                self.logger.info("Attempting to load from expired cache as fallback")
                return self._load_from_cache()
            return False
            
        except Exception as e:
            self.logger.error(f"Error downloading instruments: {e}", exc_info=True)
            return False
    
    def _load_instruments(self):
        """Load instruments (from cache or download).
        
        Called during initialization. Tries cache first, downloads if needed.
        """
        # Try cache first
        if self._is_cache_valid() and self._load_from_cache():
            return
        
        # Download if cache invalid or missing
        self.download_instruments()
    
    def get_token(self, symbol: str, exchange: str = "NSE") -> Optional[str]:
        """Get token for a trading symbol.
        
        Args:
            symbol: Trading symbol (e.g., "SBIN-EQ", "NIFTY25NOVFUT")
            exchange: Exchange segment (default: NSE)
                     Options: NSE, NFO, BSE, BFO, MCX, etc.
            
        Returns:
            str: Token if found, None otherwise
            
        Example:
            >>> inst = get_instrument_master()
            >>> 
            >>> # Equity
            >>> token = inst.get_token("SBIN-EQ", "NSE")
            >>> 
            >>> # Futures
            >>> token = inst.get_token("NIFTY25NOVFUT", "NFO")
            >>> 
            >>> # Options
            >>> token = inst.get_token("NIFTY25NOV19500CE", "NFO")
        """
        try:
            if self.instruments is None:
                self.logger.error("Instruments not loaded")
                return None
            
            # Normalize inputs
            symbol = symbol.upper().strip()
            exchange = exchange.upper().strip()
            
            # Map exchange to exch_seg format
            exch_seg_map = {
                "NSE": "NSE_CM",
                "NFO": "NFO_FO", 
                "BSE": "BSE_CM",
                "BFO": "BFO_FO",
                "MCX": "MCX_FO",
                "CDS": "CDS_FO"
            }
            
            exch_seg = exch_seg_map.get(exchange, exchange)
            
            # Search for instrument
            result = self.instruments[
                (self.instruments['symbol'] == symbol) & 
                (self.instruments['exch_seg'].str.upper() == exch_seg)
            ]
            
            if len(result) > 0:
                token = result.iloc[0]['token']
                self.logger.debug(f"Found token for {symbol} on {exchange}: {token}")
                return str(token)
            else:
                self.logger.warning(f"Token not found for {symbol} on {exchange}")
                return None
            
        except Exception as e:
            self.logger.error(f"Error getting token: {e}", exc_info=True)
            return None
    
    def search_symbol(self, search_term: str, exchange: str = "NSE", 
                     limit: int = 10) -> List[Dict[str, Any]]:
        """Search for symbols matching search term.
        
        Args:
            search_term: Term to search (e.g., "SBIN", "NIFTY")
            exchange: Exchange to filter by (default: NSE)
            limit: Maximum results to return (default: 10)
            
        Returns:
            list: List of matching instruments with details
            
        Example:
            >>> inst = get_instrument_master()
            >>> results = inst.search_symbol("SBIN", "NSE")
            >>> for r in results:
            ...     print(f"{r['symbol']} - {r['name']} ({r['token']})")
        """
        try:
            if self.instruments is None:
                self.logger.error("Instruments not loaded")
                return []
            
            # Normalize inputs
            search_term = search_term.upper().strip()
            exchange = exchange.upper().strip()
            
            # Map exchange
            exch_seg_map = {
                "NSE": "NSE_CM",
                "NFO": "NFO_FO",
                "BSE": "BSE_CM",
                "BFO": "BFO_FO",
                "MCX": "MCX_FO",
                "CDS": "CDS_FO"
            }
            
            exch_seg = exch_seg_map.get(exchange, exchange)
            
            # Search
            results = self.instruments[
                (self.instruments['symbol'].str.contains(search_term, case=False, na=False)) &
                (self.instruments['exch_seg'].str.upper() == exch_seg)
            ].head(limit)
            
            # Convert to list of dicts
            instruments_list = []
            for _, row in results.iterrows():
                instruments_list.append({
                    'token': str(row['token']),
                    'symbol': row['symbol'],
                    'name': row.get('name', ''),
                    'exchange': row['exch_seg'],
                    'instrument_type': row.get('instrumenttype', ''),
                    'expiry': row.get('expiry', ''),
                    'strike': row.get('strike', ''),
                    'lotsize': row.get('lotsize', '')
                })
            
            self.logger.info(f"Found {len(instruments_list)} matches for '{search_term}' on {exchange}")
            return instruments_list
            
        except Exception as e:
            self.logger.error(f"Error searching symbol: {e}", exc_info=True)
            return []
    
    def get_instrument_details(self, token: str) -> Optional[Dict[str, Any]]:
        """Get complete instrument details by token.
        
        Args:
            token: Instrument token
            
        Returns:
            dict: Instrument details, or None if not found
            
        Example:
            >>> inst = get_instrument_master()
            >>> details = inst.get_instrument_details("3045")
            >>> print(f"Symbol: {details['symbol']}")
            >>> print(f"Name: {details['name']}")
        """
        try:
            if self.instruments is None:
                self.logger.error("Instruments not loaded")
                return None
            
            result = self.instruments[self.instruments['token'] == token]
            
            if len(result) > 0:
                return result.iloc[0].to_dict()
            else:
                self.logger.warning(f"Instrument not found for token: {token}")
                return None
            
        except Exception as e:
            self.logger.error(f"Error getting instrument details: {e}", exc_info=True)
            return None
    
    def get_futures_by_symbol(self, symbol: str, exchange: str = "NFO") -> List[Dict[str, Any]]:
        """Get all futures contracts for a symbol.
        
        Args:
            symbol: Base symbol (e.g., "NIFTY", "BANKNIFTY")
            exchange: Exchange (default: NFO)
            
        Returns:
            list: List of futures contracts with expiry dates
            
        Example:
            >>> inst = get_instrument_master()
            >>> contracts = inst.get_futures_by_symbol("NIFTY")
            >>> for c in contracts:
            ...     print(f"{c['symbol']} expires on {c['expiry']}")
        """
        try:
            if self.instruments is None:
                self.logger.error("Instruments not loaded")
                return []
            
            # Normalize
            symbol = symbol.upper().strip()
            exchange = exchange.upper().strip()
            
            exch_seg_map = {"NFO": "NFO_FO", "BFO": "BFO_FO"}
            exch_seg = exch_seg_map.get(exchange, exchange)
            
            # Filter futures
            results = self.instruments[
                (self.instruments['name'] == symbol) &
                (self.instruments['exch_seg'].str.upper() == exch_seg) &
                (self.instruments['instrumenttype'] == 'FUTIDX')
            ]
            
            # Convert to list
            futures_list = []
            for _, row in results.iterrows():
                futures_list.append({
                    'token': str(row['token']),
                    'symbol': row['symbol'],
                    'name': row['name'],
                    'expiry': row.get('expiry', ''),
                    'lotsize': row.get('lotsize', '')
                })
            
            # Sort by expiry
            futures_list.sort(key=lambda x: x['expiry'])
            
            self.logger.info(f"Found {len(futures_list)} futures for {symbol}")
            return futures_list
            
        except Exception as e:
            self.logger.error(f"Error getting futures: {e}", exc_info=True)
            return []
    
    def refresh_cache(self) -> bool:
        """Force refresh the cached instrument data.
        
        Returns:
            bool: True if refresh successful
            
        Example:
            >>> inst = get_instrument_master()
            >>> # Refresh once a day
            >>> inst.refresh_cache()
        """
        return self.download_instruments(force=True)
    
    def get_cache_info(self) -> Dict[str, Any]:
        """Get information about cached data.
        
        Returns:
            dict: Cache metadata (download time, count, age, etc.)
            
        Example:
            >>> inst = get_instrument_master()
            >>> info = inst.get_cache_info()
            >>> print(f"Cache age: {info['age_hours']:.1f} hours")
            >>> print(f"Instruments: {info['count']}")
        """
        try:
            if not self.metadata_file.exists():
                return {'valid': False, 'message': 'No cache metadata'}
            
            with open(self.metadata_file, 'r') as f:
                metadata = json.load(f)
            
            cached_time = datetime.fromisoformat(metadata['downloaded_at'])
            age = datetime.now() - cached_time
            
            return {
                'valid': True,
                'downloaded_at': metadata['downloaded_at'],
                'age_hours': age.total_seconds() / 3600,
                'count': metadata.get('instrument_count', 0),
                'source': metadata.get('source', ''),
                'cache_file': str(self.cache_file),
                'is_valid': age.total_seconds() < CACHE_VALIDITY_HOURS * 3600
            }
            
        except Exception as e:
            return {'valid': False, 'error': str(e)}
