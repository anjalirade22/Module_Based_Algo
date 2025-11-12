# API Module Testing Guide

## Overview
The `test_api_module.py` script provides comprehensive testing for the broker API authentication and basic operations. It tests actual broker login using credentials from the config package.

## ⚠️ Important Warnings
- **These tests make REAL API calls to the broker!**
- **Use valid credentials only**
- **Test in paper/demo mode first**
- **Be aware of API rate limits**

## Prerequisites
1. **Valid broker credentials configured** in `config/credentials.py`
2. **All dependencies installed** (see `requirements.txt`)
3. **Virtual environment activated**

## Required Credentials
The following must be configured in your credentials:
- `API_KEY` - Your Angel One API key
- `USERNAME` - Broker username
- `PIN` - Account PIN
- `TOTP_TOKEN` - TOTP secret for 2FA

## How to Run Tests

### Method 1: Direct Execution
```bash
# Activate virtual environment
venv\Scripts\activate

# Run the test script
python tests/test_api_module.py
```

### Method 2: Import and Run Specific Tests
```python
from tests.test_api_module import TestAPIAuthentication, TestAPIBasicOperations

# Create test instances
auth_tests = TestAPIAuthentication()
ops_tests = TestAPIBasicOperations()

# Run individual tests
auth_tests.test_credentials_available()
auth_tests.test_broker_authentication()
# etc.
```

## Test Structure

### Authentication Tests
1. **`test_credentials_available()`** - Checks if all required credentials are configured
2. **`test_api_client_initialization()`** - Verifies API client setup
3. **`test_broker_authentication()`** - Tests actual broker login
4. **`test_session_renewal()`** - Tests session token renewal
5. **`test_get_user_details()`** - Retrieves and displays user profile

### Basic Operations Tests
1. **`test_get_positions()`** - Tests position retrieval
2. **`test_get_holdings()`** - Tests portfolio holdings
3. **`test_get_order_book()`** - Tests order history

## Expected Output
```
🚀 Starting API Module Tests...
⚠️  WARNING: These tests make real API calls to the broker!

==================================================
🔐 RUNNING AUTHENTICATION TESTS
==================================================

▶️  Running test_credentials_available...
✅ All required credentials are available
✅ test_credentials_available PASSED

▶️  Running test_broker_authentication...
🔐 Testing broker authentication...
✅ Broker authentication successful!
🎫 JWT Token received
🎫 Feed Token received
✅ test_broker_authentication PASSED

... (more tests)

==================================================
📊 API MODULE TEST RESULTS
==================================================
Total Tests: 8
✅ Passed: 8
❌ Failed: 0
⏭️  Skipped: 0
📊 Success Rate: 100.0%
🎉 All tests passed! API module is working correctly.
```

## Troubleshooting

### Common Issues

1. **Missing Credentials**
   ```
   ⚠️  Missing credentials: ['API_KEY', 'USERNAME']
   ```
   **Solution:** Configure credentials in `config/credentials.py`

2. **Authentication Failed**
   ```
   ❌ Broker authentication failed
   ```
   **Solution:** Check credentials, network, and broker account status

3. **Import Errors**
   ```
   ModuleNotFoundError: No module named 'SmartApi'
   ```
   **Solution:** Install dependencies with `pip install -r requirements.txt`

### Test Results Interpretation
- **PASSED (✅)**: Test completed successfully
- **FAILED (❌)**: Test failed - check logs for details
- **SKIPPED (⏭️)**: Test skipped due to missing prerequisites (e.g., no authentication)

## Security Notes
- Never commit real credentials to version control
- Use encrypted credential storage (`credentials.enc`)
- Test with paper/demo accounts first
- Monitor API usage to avoid rate limits

## Next Steps
After successful testing:
1. Run the main trading system: `python main.py --mode paper`
2. Test individual modules
3. Implement WebSocket functionality for live data
4. Add more comprehensive integration tests