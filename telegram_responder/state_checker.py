import asyncio
import aiohttp
import schedule
import time
from telegram import Bot


class Monitor:
    def __init__(self, api_url, telegram_token, chat_ids):
        self.api_url = api_url
        self.bot = Bot(token=telegram_token)
        self.chat_ids = chat_ids

    async def check_constraints(self):
        """Check database constraints via the API"""
        async with aiohttp.ClientSession() as session:
            # Get data from your API
            async with session.get(f"{self.api_url}/humiditySensors/") as response:
                sensors = await response.json()

            # Fetch recent measurements
            for sensor in sensors:
                async with session.get(
                        f"{self.api_url}/humidityMeasurements/sensor/{sensor['id']}?limit=1"
                ) as response:
                    measurements = await response.json()

                # Apply your constraint checks
                if measurements and self._check_humidity_constraints(measurements[0]):
                    await self._send_alert(
                        f"⚠️ Sensor {sensor['name']}: Humidity {measurements[0]['humidity']}% out of range!"
                    )

    def _check_humidity_constraints(self, measurement):
        """Check if measurement violates constraints"""
        humidity = measurement['humidity']
        return humidity < 30.0 or humidity > 70.0

    async def _send_alert(self, message):
        """Send alert to all configured chat IDs"""
        for chat_id in self.chat_ids:
            await self.bot.send_message(chat_id=chat_id, text=message)

    def start_scheduled_checks(self, interval_minutes=5):
        """Start scheduled checks using schedule library"""
        schedule.every(interval_minutes).minutes.do(
            lambda: asyncio.run(self.check_constraints())
        )

        while True:
            schedule.run_pending()
            time.sleep(60)  # Check for pending tasks every minute