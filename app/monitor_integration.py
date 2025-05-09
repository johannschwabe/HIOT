# app/monitor_integration.py
import asyncio
import logging
from contextlib import asynccontextmanager

from app.scheduler import HumidityMonitor
from app.telegram_notifier import TelegramNotifier, AlertLevel

logger = logging.getLogger("humidity-app")

# Global monitor instance
humidity_monitor = None


@asynccontextmanager
async def lifespan(app):
    """
    FastAPI lifespan context manager to start and stop the monitor
    alongside the main application.
    """
    # Initialize components
    global humidity_monitor
    notifier = TelegramNotifier()
    humidity_monitor = HumidityMonitor(
        # Settings can also come from environment variables
        check_interval=300,  # 5 minutes
        humidity_threshold_high=70.0,
        humidity_threshold_low=30.0,
        connection_threshold_minutes=30,
        telegram_notifier=notifier
    )

    # Start monitor
    await humidity_monitor.start()
    logger.info("Humidity monitor started")

    yield

    # Shutdown monitor
    await humidity_monitor.stop()
    logger.info("Humidity monitor stopped")