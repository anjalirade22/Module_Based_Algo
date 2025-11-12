# Modular Automated Trading System

> 📚 **Documentation**: See [docs/index.md](index.md) for complete documentation index

A comprehensive, modular automated trading system built with Python, featuring encrypted credentials, risk management, and swing trading strategies.

## 🚀 Features

- **Modular Architecture**: Clean separation of concerns with dedicated modules for API, data, strategy, risk management, and execution
- **Encrypted Credentials**: Fernet encryption for secure storage of API keys and sensitive data
- **Risk Management**: Comprehensive position sizing, stop losses, and portfolio risk controls
- **Swing Trading**: Built-in swing level detection and trading strategies
- **Live & Paper Trading**: Support for both live and paper trading modes
- **Real-time Data**: WebSocket integration for live market data
- **Logging**: Centralized logging with configurable levels
- **Backtesting Ready**: Framework for strategy backtesting and optimization

## 📁 Project Structure

```
├── config/
│   ├── __init__.py          # Config package entry point
│   ├── settings.py          # Global settings and Config class
│   ├── credentials.py       # Encrypted credential management
│   ├── credentials.enc      # Encrypted credentials (gitignored)
│   └── fernet_key.json      # Encryption key (gitignored)
├── modules/
│   ├── api_module.py        # Broker API integration
│   ├── data_module.py       # Market data management
│   ├── strategy_module.py   # Trading strategies
│   ├── rms_module.py        # Risk management system
│   ├── execution_module.py  # Order execution
│   └── logging_config.py    # Centralized logging
├── data/
│   ├── cache/               # Cached historical data
│   ├── historical/          # Historical market data
│   └── live/                # Live data storage
├── logs/                    # Application logs
├── strategies/              # Custom strategy implementations
├── tests/                   # Unit and integration tests
├── utils/                   # Utility functions
├── main.py                  # System entry point
├── encrypt_credentials.py   # Credential encryption utility
└── README.md               # This file
```

## 🛠️ Installation & Setup

### Prerequisites

- Python 3.8+
- pip package manager
- Git

### 1. Clone the Repository

```bash
git clone <repository-url>
cd Module_Based_Algo
```

### 2. Install Dependencies

```bash
pip install cryptography python-dotenv pytz pandas
```

For full functionality, also install:

```bash
pip install smartapi-python pyotp
```

### 3. Setup Credentials

#### Generate Encryption Key

```bash
python encrypt_credentials.py
```

This creates `fernet_key.json` with your encryption key.

#### Create Credentials File

Create `credentials.json` with your broker credentials:

```json
{
  "API_KEY": "your_api_key",
  "USERNAME": "your_username",
  "PIN": "your_pin",
  "TOTP_TOKEN": "your_totp_secret",
  "BOT_TOKEN": "telegram_bot_token",
  "CHAT_ID": "telegram_chat_id"
}
```

#### Encrypt Credentials

```bash
python encrypt_credentials.py
```

This creates `credentials.enc` and optionally deletes the plain `credentials.json`.

### 4. Configuration

Edit `config/settings.py` to customize:

- Trading parameters (lot sizes, risk limits, etc.)
- Broker settings
- Risk management rules
- Logging configuration

## 🚀 Usage

### Running the System

#### Paper Trading (Recommended for testing)

```bash
python main.py --mode paper
```

#### Live Trading (Use with caution)

```bash
python main.py --mode live
```

#### Custom Symbols

```bash
python main.py --mode paper --symbols NIFTY BANKNIFTY
```

#### Debug Logging

```bash
python main.py --mode paper --log-level DEBUG
```

### Command Line Options

- `--mode`: Trading mode (`live`, `paper`, `test`)
- `--symbols`: List of symbols to trade
- `--log-level`: Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)

## 📊 Modules Overview

### API Module (`api_module.py`)

Handles broker integration with Angel One SmartAPI:

- Authentication with TOTP
- Order placement and management
- Market data fetching
- Position and holdings management

### Data Module (`data_module.py`)

Manages market data:

- Live data streaming via WebSocket
- Historical data fetching and caching
- Data preprocessing and formatting
- Multiple data source support

### Strategy Module (`strategy_module.py`)

Implements trading strategies:

- Swing level detection
- Signal generation
- Strategy backtesting framework
- Custom strategy integration

### RMS Module (`rms_module.py`)

Risk management system:

- Position sizing calculations
- Stop loss management
- Portfolio risk monitoring
- Daily loss limits and drawdown controls

### Execution Module (`execution_module.py`)

Order execution layer:

- Signal processing
- Order routing
- Execution monitoring
- Position synchronization

## 🔧 Configuration

### Key Settings in `config/settings.py`

```python
# Trading parameters
PRODUCT_TYPE = 'CARRYFORWARD'
ORDER_TYPE = 'MARKET'
LOT_SIZE = {'nifty': 75, 'banknifty': 35}

# Risk management
MAX_POSITIONS = 10
MAX_DAILY_LOSS = 50000.0
POSITION_SIZE_PERCENT = 0.02
STOP_LOSS_PERCENT = 0.05

# Trading hours
TIME_ZONE = pytz.timezone('Asia/Kolkata')
```

### Environment Variables

You can override credentials using environment variables:

```bash
export API_KEY="your_key"
export USERNAME="your_username"
export PIN="your_pin"
export TOTP_TOKEN="your_totp"
```

## 🧪 Testing

Run basic tests:

```bash
python -m tests.test_system
```

For full test suite (requires pytest):

```bash
pip install pytest
pytest tests/ -v
```

## 📝 Logging

Logs are stored in the `logs/` directory with rotation. Configure logging level in `modules/logging_config.py`.

Log levels:
- `DEBUG`: Detailed debugging information
- `INFO`: General information
- `WARNING`: Warning messages
- `ERROR`: Error messages

## 🚨 Troubleshooting

### Common Issues

#### 1. "SmartApi package not installed"

```bash
pip install smartapi-python
```

#### 2. "No module named 'config'"

Run from project root directory:

```bash
cd /path/to/Module_Based_Algo
python main.py
```

#### 3. Authentication failed

- Check credentials in `credentials.enc`
- Verify TOTP token is correct
- Check broker API status

#### 4. No market data

- Verify API authentication
- Check symbol names
- Confirm market hours

#### 5. Position size calculation returns 0

- Check risk management settings
- Verify stop loss distance
- Confirm sufficient portfolio value

### Debug Mode

Run with debug logging:

```bash
python main.py --mode paper --log-level DEBUG
```

### Log Files

Check `logs/` directory for detailed error information.

## 🔒 Security

- Credentials are encrypted using Fernet (AES-128-CBC + HMAC-SHA256)
- Sensitive files are gitignored
- API keys never logged in plain text
- Environment variable fallback for credentials

## 📈 Strategy Development

### Creating Custom Strategies

1. Create a new strategy class inheriting from base strategy
2. Implement signal generation logic
3. Add to strategy manager in `main.py`

Example:

```python
from modules.strategy_module import SwingStrategy

class MyStrategy(SwingStrategy):
    def generate_signals(self, data):
        # Your strategy logic here
        signals = []
        # ... generate signals ...
        return signals
```

### Backtesting

The framework supports backtesting. Implement historical data loading and signal evaluation.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Disclaimer

This software is for educational and research purposes only. Use at your own risk. The authors are not responsible for any financial losses incurred through the use of this software.

Always test thoroughly in paper trading mode before using live trading features.