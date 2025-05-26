import asyncio
import aiohttp
import schedule
import time
from telegram import Bot
import logging

logger = logging.getLogger("State-checker")


class Monitor:
    def __init__(self, api_url, telegram_token, chat_ids):
        self.api_url = api_url
        self.bot = Bot(token=telegram_token)
        self.chat_ids = chat_ids
        self.last_alert = None
        self.last_alert_time = None
        self.min_alert_interval = 60 * 60 * 4  # Minimum interval between alerts in seconds

    async def check_constraints(self):
        """Check database constraints via the API"""
        async with aiohttp.ClientSession() as session:
            # Get data from your API
            async with session.get(f"{self.api_url}/humidity/check") as response:
                alert = await response.text()
                cleaned_text: str = alert.replace('\\n', '\n').replace('"', '')

                if len(alert) > 0:
                   await self._send_alert(cleaned_text)

    async def _send_alert(self, message):
        """Send alert to all configured chat IDs"""
        if self.last_alert == message and self.last_alert_time and (time.time() - self.last_alert_time) < self.min_alert_interval:
            return
        for chat_id in self.chat_ids:
            logger.warning(f"Sending alert for chat ID {chat_id}")
            await self.bot.send_message(chat_id=chat_id, text=message)

    def start_scheduled_checks(self, interval_minutes=5):
        """Start scheduled checks using schedule library"""
        schedule.every(interval_minutes).minutes.do(
            lambda: asyncio.run(self.check_constraints())
        )

        while True:
            schedule.run_pending()
            time.sleep(60)  # Check for pending tasks every minute