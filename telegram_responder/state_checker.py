# state_checker.py
import asyncio
import aiohttp
import time
from telegram import Bot
from telegram.error import NetworkError, TelegramError
import logging

logger = logging.getLogger("State-checker")


class Monitor:
    def __init__(self, api_url, telegram_token, chat_ids):
        self.api_url = api_url
        self.telegram_token = telegram_token
        self.chat_ids = chat_ids
        self.last_alert = None
        self.last_alert_time = None
        self.min_alert_interval = 60 * 60 * 4  # 4 hours
        self.bot = None
        self.task = None
        self.running = False

    async def check_constraints(self):
        """Check database constraints via the API"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                        f"{self.api_url}/humidity/check",
                        timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status == 200:
                        alert = await response.text()
                        cleaned_text = alert.replace('\\n', '\n').replace('"', '')

                        if len(cleaned_text.strip()) > 0:
                            await self._send_alert(cleaned_text)
                    else:
                        logger.warning(f"API returned status {response.status}")

        except asyncio.TimeoutError:
            logger.error("Timeout checking constraints")
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error checking constraints: {e}")
        except Exception as e:
            logger.error(f"Unexpected error checking constraints: {e}")

    async def _send_alert(self, message):
        """Send alert to all configured chat IDs"""
        # Check if we should rate limit
        if (self.last_alert_time and
                (time.time() - self.last_alert_time) < self.min_alert_interval):
            logger.debug("Skipping alert due to rate limiting")
            return

        # Initialize bot if needed
        if self.bot is None:
            self.bot = Bot(token=self.telegram_token)

        # Send to all chat IDs
        successful_sends = 0
        for chat_id in self.chat_ids:
            try:
                logger.info(f"Sending alert to chat ID {chat_id}")
                await self.bot.send_message(chat_id=chat_id, text=message)
                successful_sends += 1

            except NetworkError as e:
                logger.error(f"Network error sending to chat {chat_id}: {e}")
            except TelegramError as e:
                logger.error(f"Telegram error sending to chat {chat_id}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error sending alert to chat {chat_id}: {e}")

        # Update last alert info only if at least one send was successful
        if successful_sends > 0:
            self.last_alert = message
            self.last_alert_time = time.time()
            logger.info(f"Alert sent successfully to {successful_sends}/{len(self.chat_ids)} chats")

    async def run_periodic_checks(self, interval_minutes=5):
        """Run periodic checks"""
        interval_seconds = interval_minutes * 60
        logger.info(f"Starting periodic checks every {interval_minutes} minutes")

        self.running = True

        while self.running:
            try:
                await self.check_constraints()

                # Sleep in smaller chunks to allow for faster cancellation
                for _ in range(interval_seconds):
                    if not self.running:
                        break
                    await asyncio.sleep(1)

            except asyncio.CancelledError:
                logger.info("Periodic checks cancelled")
                break
            except Exception as e:
                logger.error(f"Error in periodic check: {e}")
                # Wait a bit before retrying, but still check for cancellation
                for _ in range(60):  # Wait 60 seconds
                    if not self.running:
                        break
                    await asyncio.sleep(1)

        logger.info("Periodic checks stopped")

    async def start_async(self, interval_minutes=5):
        """Start monitoring asynchronously"""
        if self.task and not self.task.done():
            logger.warning("Monitor already running")
            return self.task

        logger.info("Starting async monitor")
        self.task = asyncio.create_task(
            self.run_periodic_checks(interval_minutes)
        )
        return self.task

    async def stop_async(self):
        """Stop monitoring"""
        logger.info("Stopping monitor...")

        # Signal stop
        self.running = False

        # Cancel task if running
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                logger.info("Monitor task cancelled successfully")
            except Exception as e:
                logger.error(f"Error during monitor task cancellation: {e}")

        # Clean up bot resources
        if self.bot and hasattr(self.bot, '_request') and self.bot._request:
            try:
                await self.bot._request.shutdown()
                logger.info("Bot HTTP client shutdown")
            except Exception as e:
                logger.error(f"Error during bot cleanup: {e}")

        logger.info("Monitor stopped")

    # Legacy method for backward compatibility
    def start_scheduled_checks(self, interval_minutes=5):
        """Legacy synchronous method - use start_async() instead"""
        logger.warning("Using legacy start_scheduled_checks(). Use start_async() instead.")
        try:
            asyncio.run(self.run_periodic_checks(interval_minutes))
        except KeyboardInterrupt:
            logger.info("Monitor stopped by user")
        except Exception as e:
            logger.error(f"Error in scheduled checks: {e}")
            raise