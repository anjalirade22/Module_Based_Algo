"""Utility package for trading system helpers.

This package provides utility functions for:
- Instrument master management and token lookup
- Contract name generation for futures and options
- Market utilities and helpers

Components:
    - InstrumentMaster: Download and manage instrument data
    - get_futures_contracts: Generate futures contract names
    - get_token: Quick token lookup
    - search_symbol: Search for instruments

Usage:
    from utils import get_instrument_master, get_futures_contracts
    
    # Get instrument master (cached)
    inst = get_instrument_master()
    
    # Get futures contract names
    contracts = get_futures_contracts("NIFTY")
    
    # Get token
    token = inst.get_token("NIFTY25NOVFUT", "NFO")
"""

from .instruments import InstrumentMaster, get_instrument_master
from .contract_utils import (
    get_futures_contracts,
    get_current_month_contract,
    get_next_month_contract,
    get_far_month_contract,
    get_monthly_expiry_date
)

__all__ = [
    'InstrumentMaster',
    'get_instrument_master',
    'get_futures_contracts',
    'get_current_month_contract',
    'get_next_month_contract',
    'get_far_month_contract',
    'get_monthly_expiry_date'
]

__version__ = '1.0.0'
__author__ = 'Trading System'
