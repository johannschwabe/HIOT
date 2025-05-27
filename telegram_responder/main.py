# main.py
import os
import asyncio
import logging
import signal
import sys

from telegram_handler import TelegramBot
from state_checker import Monitor
from ENV import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

api_url = "http://api:8000"


class AsyncApplication:
    """Main application class that manages both bot and monitor"""

    def __init__(self):
        self.admin_chat_ids = TELEGRAM_CHAT_IDS.split(",")
        self.bot = TelegramBot(TELEGRAM_BOT_TOKEN)
        self.monitor = None
        self.bot = None
        self.monitor_task = None
        self.bot_task = None
        self.shutdown_event = asyncio.Event()

    async def initialize(self):
        """Initialize both services"""
        logger.info("Initializing application...")

        # Initialize monitor
        self.monitor = Monitor(api_url, TELEGRAM_BOT_TOKEN, self.admin_chat_ids)

        # Initialize bot
        self.bot = TelegramBot(api_url, TELEGRAM_BOT_TOKEN)

        logger.info("Services initialized successfully")

    async def start_services(self):
        """Start both monitor and bot services"""
        logger.info("Starting services...")

        # Start monitor
        self.monitor_task = await self.monitor.start_async(interval_minutes=5)
        logger.info("Monitor service started")

        # Start bot
        self.bot_task = asyncio.create_task(self.bot.run_async())
        logger.info("Telegram bot started")

        logger.info("All services started successfully!")

    async def shutdown(self):
        """Gracefully shutdown all services"""
        logger.info("Shutting down application...")

        # Signal shutdown to all components
        self.shutdown_event.set()

        # Stop monitor
        if self.monitor:
            try:
                await self.monitor.stop_async()
                logger.info("Monitor stopped")
            except Exception as e:
                logger.error(f"Error stopping monitor: {e}")

        # Stop bot
        if self.bot:
            try:
                await self.bot.stop_async()
                logger.info("Telegram bot stopped")
            except Exception as e:
                logger.error(f"Error stopping bot: {e}")

        # Cancel remaining tasks
        tasks_to_cancel = []
        if self.monitor_task and not self.monitor_task.done():
            tasks_to_cancel.append(self.monitor_task)
        if self.bot_task and not self.bot_task.done():
            tasks_to_cancel.append(self.bot_task)

        if tasks_to_cancel:
            logger.info(f"Cancelling {len(tasks_to_cancel)} remaining tasks...")
            for task in tasks_to_cancel:
                task.cancel()

            # Wait for tasks to finish cancelling
            try:
                await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
            except Exception as e:
                logger.error(f"Error during task cancellation: {e}")

        logger.info("Application shutdown complete")

    async def run(self):
        """Main application run method"""
        try:
            # Initialize services
            await self.initialize()

            # Start services
            await self.start_services()

            # Wait for shutdown signal
            await self.shutdown_event.wait()

        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"Application error: {e}")
            raise
        finally:
            await self.shutdown()


async def main():
    """Main entry point"""
    app = AsyncApplication()

    # Setup signal handlers for graceful shutdown
    def signal_handler():
        logger.info("Received shutdown signal")
        app.shutdown_event.set()

    # Register signal handlers
    if sys.platform != "win32":
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, signal_handler)

    try:
        await app.run()
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application failed: {e}")
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Application terminated")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)