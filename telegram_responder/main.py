# main.py
import os
import asyncio
import threading

from telegram_handler import TelegramBot
from state_checker import Monitor
from ENV import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
api_url = "http://api:8000"

def main():
    admin_chat_ids = [TELEGRAM_CHAT_ID]

    # Start monitor in a separate thread
    monitor = Monitor(api_url, TELEGRAM_BOT_TOKEN, admin_chat_ids)
    monitor_thread = threading.Thread(
        target=monitor.start_scheduled_checks,
        args=(5,),  # Check every 5 minutes
        daemon=True
    )
    monitor_thread.start()

    # Start bot in main thread
    bot = TelegramBot(api_url, TELEGRAM_BOT_TOKEN)
    bot.run()


if __name__ == "__main__":
    main()