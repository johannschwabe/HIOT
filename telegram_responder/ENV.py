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


TELEGRAM_BOT_TOKEN = read_secret_file("/run/secrets/hiot_telegram_bot_token")
TELEGRAM_CHAT_IDS = os.getenv("TELEGRAM_CHAT_IDS")