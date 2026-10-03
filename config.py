import json
import os
from pathlib import Path
import keyring

CONFIG_FILE = Path.home() / ".pymail_config.json"

DEFAULT_CONFIG = {
    "accounts": [],
    "ui": {
        "theme": "system",
        "font_size": 10
    }
}

def load_config():
    if not CONFIG_FILE.exists():
        return DEFAULT_CONFIG.copy()
        
    needs_migration = False
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            
        for account in config.get("accounts", []):
            email = account.get("email")
            if not email:
                continue
                
            # Auto-migrate plaintext password to keyring
            if "password" in account:
                keyring.set_password("PyMail", email, account["password"])
                del account["password"]
                needs_migration = True
            
            # Fetch password securely into memory
            stored_pass = keyring.get_password("PyMail", email)
            if stored_pass:
                account["password"] = stored_pass
                
        if needs_migration:
            save_config(config)
            
        return config
    except Exception as e:
        print(f"Error loading config: {e}")
        return DEFAULT_CONFIG.copy()

def save_config(config_data):
    try:
        # Clone config to avoid stripping the password from the active in-memory object
        config_to_save = json.loads(json.dumps(config_data))
        
        for account in config_to_save.get("accounts", []):
            email = account.get("email")
            if not email:
                continue
                
            if "password" in account:
                keyring.set_password("PyMail", email, account["password"])
                del account["password"]
                
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_to_save, f, indent=4)
    except Exception as e:
        print(f"Error saving config: {e}")
