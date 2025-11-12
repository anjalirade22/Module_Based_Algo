# encrypt_credentials.py
import json
import os
from pathlib import Path
from cryptography.fernet import Fernet

# Import logger for proper logging
from modules.logging_config import logger

# Paths
KEY_FILE = Path("fernet_key.json")
CREDENTIALS_FILE = Path("credentials.json")
ENCRYPTED_FILE = Path("credentials.enc")

def generate_and_store_key():
    """Generate a Fernet key and store it in fernet_key.json."""
    key = Fernet.generate_key().decode()
    KEY_FILE.write_text(json.dumps({"fernet_key": key}, indent=2))
    logger.info(f"✅ Fernet key generated and saved to {KEY_FILE}")

def get_key():
    """Read Fernet key from fernet_key.json."""
    if not KEY_FILE.exists():
        raise FileNotFoundError("❌ Key file not found. Run generate_and_store_key() first.")
    data = json.loads(KEY_FILE.read_text())
    if "fernet_key" not in data:
        raise KeyError("Invalid key file format — missing 'fernet_key' field.")
    return data["fernet_key"].encode()

def encrypt_credentials():
    """Encrypt credentials.json → credentials.enc."""
    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError(f"❌ {CREDENTIALS_FILE} not found.")
    
    key = get_key()
    fernet = Fernet(key)
    data = CREDENTIALS_FILE.read_bytes()
    encrypted = fernet.encrypt(data)
    ENCRYPTED_FILE.write_bytes(encrypted)
    logger.info(f"✅ Credentials encrypted -> {ENCRYPTED_FILE}")

    # Optional cleanup
    delete = input("Do you want to delete the original credentials.json? (y/n): ").strip().lower()
    if delete == "y":
        os.remove(CREDENTIALS_FILE)
        logger.info("🗑️  credentials.json deleted for safety.")

if __name__ == "__main__":
    # Create key if it doesn’t exist yet
    if not KEY_FILE.exists():
        generate_and_store_key()
    encrypt_credentials()
