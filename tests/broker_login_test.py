#!/usr/bin/env python3
"""
Simple Broker Login Test

This script tests the broker authentication functionality.
Run this to verify your credentials and API connection work.

Usage: python broker_login_test.py
"""

import sys
import os

# Add the parent directory to Python path so we can import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import config
from modules.logging_config import logger
from modules.api_module import authenticate, is_authenticated, get_api_client


def test_broker_login():
    """Test broker login functionality."""
    print("Testing Broker Login")
    print("=" * 50)

    # Check credentials
    print("Checking credentials...")
    required_creds = ['API_KEY', 'USERNAME', 'PIN', 'TOTP_TOKEN']
    missing_creds = []

    for cred in required_creds:
        if not hasattr(config, cred) or not getattr(config, cred):
            missing_creds.append(cred)

    if missing_creds:
        print(f"Missing credentials: {missing_creds}")
        print("Please configure your credentials in config/credentials.py")
        return False

    print("All required credentials are present")

    # Test authentication
    print("\nAttempting broker authentication...")
    try:
        auth_result = authenticate()

        if auth_result:
            print("Authentication successful!")

            # Get client for additional info
            client = get_api_client()

            print(f"JWT Token: {'Received' if client.jwt_token else 'Missing'}")
            print(f"Feed Token: {'Received' if client.feed_token else 'Missing'}")
            print(f"Session expires: {client.session_expiry}")

            # Test if authenticated
            if is_authenticated():
                print("Session is active and authenticated")
            else:
                print("Warning: Authentication returned True but is_authenticated() returns False")

            return True

        else:
            print("Authentication failed")
            print("Possible reasons:")
            print("   - Invalid credentials")
            print("   - Network connectivity issues")
            print("   - Broker API service down")
            print("   - TOTP token expired or incorrect")
            return False

    except Exception as e:
        print(f"Authentication error: {str(e)}")
        print("Check your credentials and network connection")
        return False


def main():
    """Main function."""
    print("Broker Login Test Starting...")
    print("This will make a real API call to the broker")
    print()

    success = test_broker_login()

    print("\n" + "=" * 50)
    if success:
        print("LOGIN TEST PASSED - Your API integration is working!")
        print("Ready to proceed with trading system")
    else:
        print("LOGIN TEST FAILED - Check your setup")
        print("Review the error messages above")

    print("=" * 50)


if __name__ == "__main__":
    main()