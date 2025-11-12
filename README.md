# Modular Automated Trading System

📚 **Documentation**: [docs/](docs/)

A comprehensive, modular automated trading system built with Python.

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure credentials:**
   Edit `config/credentials.py` with your broker API details

3. **Test connection:**
   ```bash
   python tests/broker_login_test.py
   ```

4. **Run the system:**
   ```bash
   python main.py --mode paper
   ```

## 📖 Full Documentation

See [docs/index.md](docs/index.md) for complete documentation, including:
- Detailed setup instructions
- API testing guide
- Module documentation
- Troubleshooting

## 📁 Project Structure

- `docs/` - Documentation
- `modules/` - Core application modules
- `config/` - Configuration and credentials
- `tests/` - Test suites
- `data/` - Data storage
- `logs/` - Application logs