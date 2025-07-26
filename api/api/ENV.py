import os

from dotenv import load_dotenv

load_dotenv('../.env')


def read_secret_file(file_path: str) -> str:
    """Read content from a secret file."""
    try:
        with open(file_path, 'r') as f:
            return f.read().strip()
    except:
        return ""


# Database connection
DB_USER = os.getenv("DB_USER", "postgres")
DB_HOST = os.getenv("DB_HOST", "db")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "iot_db")

# Read password from secret file
DB_PASSWORD = read_secret_file("/run/secrets/hiot_db_password")
print(DB_PASSWORD)
# Read bot token from secret file
TELEGRAM_BOT_TOKEN = read_secret_file("/run/secrets/hiot_telegram_bot_token")
TELEGRAM_CHAT_IDS = os.getenv("TELEGRAM_CHAT_IDS")