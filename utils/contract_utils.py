"""Contract name generation utilities for futures and options.

This module provides utilities for generating contract names for
derivatives trading, particularly for monthly futures contracts.

Key Features:
    - Generate current, next, and far month futures names
    - Calculate monthly expiry dates
    - Support for NIFTY, BANKNIFTY, FINNIFTY, and custom symbols
    - Automatic year/month formatting

Usage:
    from utils import get_futures_contracts
    
    # Get all three monthly contracts
    contracts = get_futures_contracts("NIFTY")
    # Returns: ["NIFTY25NOVFUT", "NIFTY25DECFUT", "NIFTY26JANFUT"]
    
    # Get only current month
    current = get_current_month_contract("BANKNIFTY")
    # Returns: "BANKNIFTY25NOVFUT"
"""

from datetime import datetime, timedelta
from typing import List, Optional
from modules.logger_module import get_logger

logger = get_logger(__name__)


def get_monthly_expiry_date(year: int, month: int) -> datetime:
    """Calculate monthly expiry date (last Thursday of the month).
    
    For Indian derivatives, monthly contracts expire on the last Thursday
    of the expiry month.
    
    Args:
        year: Expiry year
        month: Expiry month (1-12)
        
    Returns:
        datetime: Expiry date (last Thursday of the month)
        
    Example:
        >>> expiry = get_monthly_expiry_date(2025, 11)
        >>> print(expiry.strftime("%d-%b-%Y"))
        27-Nov-2025
    """
    # Get last day of month
    if month == 12:
        last_day = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        last_day = datetime(year, month + 1, 1) - timedelta(days=1)
    
    # Find last Thursday
    # Thursday is weekday 3 (0=Monday, 6=Sunday)
    offset = (last_day.weekday() - 3) % 7
    expiry_date = last_day - timedelta(days=offset)
    
    return expiry_date


def get_current_month_contract(symbol: str) -> str:
    """Get current month futures contract name.
    
    Args:
        symbol: Base symbol (e.g., "NIFTY", "BANKNIFTY")
        
    Returns:
        str: Current month contract name
        
    Example:
        >>> contract = get_current_month_contract("NIFTY")
        >>> print(contract)
        NIFTY25NOVFUT
    """
    now = datetime.now()
    
    # Check if current month has expired
    expiry = get_monthly_expiry_date(now.year, now.month)
    
    if now > expiry:
        # Current month expired, next month becomes current
        if now.month == 12:
            year = now.year + 1
            month = 1
        else:
            year = now.year
            month = now.month + 1
    else:
        year = now.year
        month = now.month
    
    # Format: SYMBOL + YY + MMM + FUT
    year_str = str(year)[-2:]  # Last 2 digits
    month_str = datetime(year, month, 1).strftime("%b").upper()
    
    contract_name = f"{symbol.upper()}{year_str}{month_str}FUT"
    
    logger.debug(f"Current month contract: {contract_name}")
    return contract_name


def get_next_month_contract(symbol: str) -> str:
    """Get next month futures contract name.
    
    Args:
        symbol: Base symbol (e.g., "NIFTY", "BANKNIFTY")
        
    Returns:
        str: Next month contract name
        
    Example:
        >>> contract = get_next_month_contract("NIFTY")
        >>> print(contract)
        NIFTY25DECFUT
    """
    now = datetime.now()
    
    # Get current month contract details
    expiry = get_monthly_expiry_date(now.year, now.month)
    
    if now > expiry:
        # Current expired, next is +1, far is +2
        base_month = now.month + 1
        base_year = now.year
    else:
        # Current active, next is +1
        base_month = now.month + 1
        base_year = now.year
    
    # Handle year rollover
    if base_month > 12:
        base_month = base_month - 12
        base_year += 1
    
    # Next month is one month ahead
    year = base_year
    month = base_month + 1
    
    if month > 12:
        month = month - 12
        year += 1
    
    # Format contract name
    year_str = str(year)[-2:]
    month_str = datetime(year, month, 1).strftime("%b").upper()
    
    contract_name = f"{symbol.upper()}{year_str}{month_str}FUT"
    
    logger.debug(f"Next month contract: {contract_name}")
    return contract_name


def get_far_month_contract(symbol: str) -> str:
    """Get far month (third month) futures contract name.
    
    Args:
        symbol: Base symbol (e.g., "NIFTY", "BANKNIFTY")
        
    Returns:
        str: Far month contract name
        
    Example:
        >>> contract = get_far_month_contract("NIFTY")
        >>> print(contract)
        NIFTY26JANFUT
    """
    now = datetime.now()
    
    # Get current month contract details
    expiry = get_monthly_expiry_date(now.year, now.month)
    
    if now > expiry:
        # Current expired, far is +2
        base_month = now.month + 1
        base_year = now.year
    else:
        # Current active, far is +2
        base_month = now.month
        base_year = now.year
    
    # Far month is two months ahead of base
    year = base_year
    month = base_month + 2
    
    # Handle year rollover
    while month > 12:
        month -= 12
        year += 1
    
    # Format contract name
    year_str = str(year)[-2:]
    month_str = datetime(year, month, 1).strftime("%b").upper()
    
    contract_name = f"{symbol.upper()}{year_str}{month_str}FUT"
    
    logger.debug(f"Far month contract: {contract_name}")
    return contract_name


def get_futures_contracts(
    symbol: str,
    current_month: bool = True,
    next_month: bool = True,
    far_month: bool = True
) -> List[str]:
    """Get futures contract names for current, next, and far months.
    
    Returns a list of contract names for the three trading months.
    You can selectively get specific months by setting flags.
    
    Args:
        symbol: Base symbol (e.g., "NIFTY", "BANKNIFTY", "FINNIFTY")
        current_month: Include current month contract (default: True)
        next_month: Include next month contract (default: True)
        far_month: Include far month contract (default: True)
        
    Returns:
        list: List of contract names
        
    Example:
        >>> # Get all three contracts
        >>> contracts = get_futures_contracts("NIFTY")
        >>> print(contracts)
        ["NIFTY25NOVFUT", "NIFTY25DECFUT", "NIFTY26JANFUT"]
        >>> 
        >>> # Get only current and next
        >>> contracts = get_futures_contracts("BANKNIFTY", far_month=False)
        >>> print(contracts)
        ["BANKNIFTY25NOVFUT", "BANKNIFTY25DECFUT"]
        >>> 
        >>> # Get only current
        >>> contracts = get_futures_contracts("FINNIFTY", next_month=False, far_month=False)
        >>> print(contracts)
        ["FINNIFTY25NOVFUT"]
    """
    contracts = []
    
    if current_month:
        contracts.append(get_current_month_contract(symbol))
    
    if next_month:
        contracts.append(get_next_month_contract(symbol))
    
    if far_month:
        contracts.append(get_far_month_contract(symbol))
    
    logger.info(f"Generated {len(contracts)} contracts for {symbol}: {contracts}")
    return contracts


def get_contract_expiry_dates(symbol: str) -> List[dict]:
    """Get contract names with their expiry dates.
    
    Returns a list of dictionaries containing contract name and expiry date
    for current, next, and far month contracts.
    
    Args:
        symbol: Base symbol (e.g., "NIFTY")
        
    Returns:
        list: List of dicts with 'contract' and 'expiry' keys
        
    Example:
        >>> contracts = get_contract_expiry_dates("NIFTY")
        >>> for c in contracts:
        ...     print(f"{c['contract']}: {c['expiry'].strftime('%d-%b-%Y')}")
        NIFTY25NOVFUT: 27-Nov-2025
        NIFTY25DECFUT: 25-Dec-2025
        NIFTY26JANFUT: 29-Jan-2026
    """
    now = datetime.now()
    expiry = get_monthly_expiry_date(now.year, now.month)
    
    # Determine base month
    if now > expiry:
        base_month = now.month + 1
        base_year = now.year
        if base_month > 12:
            base_month = 1
            base_year += 1
    else:
        base_month = now.month
        base_year = now.year
    
    contracts_with_expiry = []
    
    # Generate three months
    for offset in range(3):
        year = base_year
        month = base_month + offset
        
        while month > 12:
            month -= 12
            year += 1
        
        # Get expiry date
        expiry_date = get_monthly_expiry_date(year, month)
        
        # Format contract name
        year_str = str(year)[-2:]
        month_str = datetime(year, month, 1).strftime("%b").upper()
        contract_name = f"{symbol.upper()}{year_str}{month_str}FUT"
        
        contracts_with_expiry.append({
            'contract': contract_name,
            'expiry': expiry_date,
            'year': year,
            'month': month
        })
    
    logger.debug(f"Generated contracts with expiry for {symbol}: {[c['contract'] for c in contracts_with_expiry]}")
    return contracts_with_expiry


def get_option_contract_name(
    symbol: str,
    strike: int,
    option_type: str,
    year: Optional[int] = None,
    month: Optional[int] = None
) -> str:
    """Generate option contract name.
    
    Args:
        symbol: Base symbol (e.g., "NIFTY", "BANKNIFTY")
        strike: Strike price (e.g., 19500)
        option_type: "CE" for Call or "PE" for Put
        year: Expiry year (default: current year)
        month: Expiry month (default: current month)
        
    Returns:
        str: Option contract name
        
    Example:
        >>> # Current month NIFTY 19500 Call
        >>> contract = get_option_contract_name("NIFTY", 19500, "CE")
        >>> print(contract)
        NIFTY25NOV19500CE
        >>> 
        >>> # Specific month
        >>> contract = get_option_contract_name("BANKNIFTY", 44000, "PE", 2025, 12)
        >>> print(contract)
        BANKNIFTY25DEC44000PE
    """
    now = datetime.now()
    
    if year is None:
        year = now.year
    
    if month is None:
        month = now.month
    
    # Format: SYMBOL + YY + MMM + STRIKE + CE/PE
    year_str = str(year)[-2:]
    month_str = datetime(year, month, 1).strftime("%b").upper()
    option_type = option_type.upper()
    
    contract_name = f"{symbol.upper()}{year_str}{month_str}{strike}{option_type}"
    
    logger.debug(f"Generated option contract: {contract_name}")
    return contract_name
