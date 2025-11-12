"""Basic tests for the trading system modules.

This module provides unit tests and integration tests for:
- Configuration loading
- Module imports
- Basic functionality validation
- Risk management calculations
- Strategy signal generation

Run with: python tests/test_system.py
"""
# import pytest  # Commented out since pytest may not be installed
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Import all modules to test
from config import config
from modules.logging_config import logger
from modules.api_module import get_api_client
from modules.data_module import get_data_manager, MarketData
from modules.strategy_module import get_strategy_manager, Signal, SignalType
from modules.rms_module import get_risk_manager
from modules.execution_module import get_execution_engine


class TestConfig:
    """Test configuration loading."""

    def test_config_import(self):
        """Test that config imports successfully."""
        assert config is not None
        assert hasattr(config, 'API_KEY')
        assert hasattr(config, 'TRADING_MODE')

    def test_config_values(self):
        """Test that config has expected default values."""
        assert config.TRADING_MODE in ['live', 'paper', 'test']
        assert isinstance(config.MAX_POSITIONS, int)
        assert config.MAX_POSITIONS > 0


class TestModules:
    """Test module imports and basic functionality."""

    def test_all_modules_import(self):
        """Test that all modules import successfully."""
        # These should not raise exceptions
        api = get_api_client()
        data = get_data_manager()
        strategy = get_strategy_manager()
        risk = get_risk_manager()
        execution = get_execution_engine()

        assert api is not None
        assert data is not None
        assert strategy is not None
        assert risk is not None
        assert execution is not None

    def test_logging_integration(self):
        """Test that logging works across modules."""
        logger.info("Test log message")
        # If we get here without exception, logging works
        assert True


class TestRiskManager:
    """Test risk management functionality."""

    def setup_method(self):
        """Setup for each test."""
        self.risk_manager = get_risk_manager()
        # Reset portfolio for testing
        self.risk_manager.portfolio_value = 100000.0
        self.risk_manager.positions.clear()
        self.risk_manager.daily_pnl = 0.0

    def test_position_size_calculation(self):
        """Test position size calculation."""
        entry_price = 100.0
        stop_loss = 95.0  # 5% stop loss
        side = 'long'

        quantity = self.risk_manager.calculate_position_size(
            'TEST', entry_price, stop_loss, side
        )

        # Should return a positive quantity
        assert quantity > 0
        assert isinstance(quantity, int)

    def test_open_position(self):
        """Test opening a position."""
        success = self.risk_manager.open_position(
            symbol='TEST',
            side='long',
            quantity=10,
            entry_price=100.0,
            stop_loss=95.0
        )

        assert success
        assert 'TEST' in self.risk_manager.positions
        assert self.risk_manager.positions['TEST'].side == 'long'

    def test_close_position(self):
        """Test closing a position."""
        # First open a position
        self.risk_manager.open_position('TEST', 'long', 10, 100.0, 95.0)

        # Then close it
        success = self.risk_manager.close_position('TEST', 105.0)

        assert success
        assert 'TEST' not in self.risk_manager.positions

    def test_risk_metrics(self):
        """Test risk metrics calculation."""
        metrics = self.risk_manager.get_risk_metrics()

        assert metrics is not None
        assert hasattr(metrics, 'total_portfolio_value')
        assert hasattr(metrics, 'total_risk_amount')
        assert metrics.total_portfolio_value >= 0


class TestStrategy:
    """Test strategy functionality."""

    def setup_method(self):
        """Setup for each test."""
        self.strategy_manager = get_strategy_manager()
        self.strategy_manager.strategies.clear()

    def test_add_strategy(self):
        """Test adding a strategy."""
        self.strategy_manager.add_strategy('TEST')

        assert 'TEST' in self.strategy_manager.strategies

    def test_generate_signals_no_data(self):
        """Test signal generation with no data."""
        signals = self.strategy_manager.generate_signals('TEST')

        # Should return empty dict or list
        assert isinstance(signals, dict)

    def test_signal_creation(self):
        """Test creating signals."""
        signal = Signal(
            symbol='TEST',
            signal_type=SignalType.BUY,
            price=100.0,
            confidence=0.8
        )

        assert signal.symbol == 'TEST'
        assert signal.signal_type == SignalType.BUY
        assert signal.price == 100.0
        assert signal.confidence == 0.8


class TestDataManager:
    """Test data management functionality."""

    def setup_method(self):
        """Setup for each test."""
        self.data_manager = get_data_manager()
        self.data_manager.live_data.clear()
        self.data_manager.subscriptions.clear()

    def test_subscribe_symbol(self):
        """Test subscribing to a symbol."""
        success = self.data_manager.subscribe_symbol('TEST')

        assert success
        assert 'TEST' in self.data_manager.subscriptions

    def test_market_data_creation(self):
        """Test creating market data."""
        data = MarketData('TEST')

        assert data.symbol == 'TEST'
        assert data.data == {}
        assert not data.is_stale()


class TestExecutionEngine:
    """Test execution engine functionality."""

    def setup_method(self):
        """Setup for each test."""
        self.execution_engine = get_execution_engine()
        self.execution_engine.pending_orders.clear()
        self.execution_engine.completed_orders.clear()

    def test_signal_processing(self):
        """Test processing a signal."""
        signal = Signal('TEST', SignalType.BUY, 100.0)

        # Should not raise exception (even if it doesn't execute)
        result = self.execution_engine.process_signal(signal)

        # Result should be boolean
        assert isinstance(result, bool)


class TestIntegration:
    """Integration tests for module interaction."""

    def test_full_system_initialization(self):
        """Test that all modules can be initialized together."""
        # This should not raise any exceptions
        api = get_api_client()
        data = get_data_manager()
        strategy = get_strategy_manager()
        risk = get_risk_manager()
        execution = get_execution_engine()

        # Test basic interactions
        assert api.is_authenticated() == False  # Not authenticated in test

        # Test data subscription
        data.subscribe_symbol('NIFTY')

        # Test strategy addition
        strategy.add_strategy('NIFTY')

        # Test risk metrics
        metrics = risk.get_risk_metrics()
        assert metrics.total_portfolio_value > 0

    def test_data_strategy_integration(self):
        """Test data and strategy module integration."""
        data_manager = get_data_manager()
        strategy_manager = get_strategy_manager()

        # Subscribe to symbol
        data_manager.subscribe_symbol('TEST')

        # Add strategy
        strategy_manager.add_strategy('TEST')

        # Generate signals (should not crash)
        signals = strategy_manager.generate_signals('TEST')
        assert isinstance(signals, dict)


def run_basic_tests():
    """Run basic functionality tests without pytest."""
    print("Running basic system tests...")

    try:
        # Test config
        from config import config
        assert config is not None
        print("✅ Config test passed")

        # Test module imports
        api = get_api_client()
        data = get_data_manager()
        strategy = get_strategy_manager()
        risk = get_risk_manager()
        execution = get_execution_engine()
        print("✅ Module imports test passed")

        # Test risk calculations
        quantity = risk.calculate_position_size('TEST', 100.0, 95.0, 'long')
        assert quantity > 0
        print("✅ Risk calculation test passed")

        # Test data subscription
        success = data.subscribe_symbol('TEST')
        assert success
        print("✅ Data subscription test passed")

        # Test strategy addition
        strategy.add_strategy('TEST')
        assert 'TEST' in strategy.strategies
        print("✅ Strategy addition test passed")

        print("🎉 All basic tests passed!")

    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        return False

    return True


if __name__ == "__main__":
    run_basic_tests()