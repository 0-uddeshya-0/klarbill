import os
from dotenv import load_dotenv

CONFIG_PATH = "./../.env"
DEFAULT_VARS = {
    "QR_BASE_URL": "http://127.0.0.1:5500/frontend/src/index.html"
}

def ensure_config():
    if not os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "w") as f:
            for key, value in DEFAULT_VARS.items():
                f.write(f"{key}={value}\n")
        print("✅ .env file created with default settings.")

    load_dotenv(CONFIG_PATH)