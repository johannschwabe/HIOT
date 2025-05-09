# app/telegram_notifier.py
import os
import logging
from typing import Optional, Dict, Any, Union
from enum import Enum
import telegram
from telegram.ext import Updater
import asyncio

logger = logging.getLogger("telegram-notifier")


class AlertLevel(Enum):
    """Enum for different alert levels"""
    INFO = "ℹ️"
    WARNING = "⚠️"
    CRITICAL = "🚨"
    SUCCESS = "✅"


class TelegramNotifier:
    """
    A class to handle Telegram notifications with different alert levels
    and customizable message templates using the python-telegram-bot library.
    """

    def __init__(
            self,
            bot_token: Optional[str] = None,
            chat_id: Optional[str] = None,
            disable_notification: bool = False
    ):
        """
        Initialize the TelegramNotifier with credentials.

        Args:
            bot_token: Telegram Bot API token
            chat_id: Telegram chat ID to send messages to
            disable_notification: Whether to send notifications silently
        """
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.disable_notification = disable_notification
        self.bot = None

        # Validate credentials
        if not self.bot_token or not self.chat_id:
            logger.warning(
                "Telegram credentials not properly configured. "
                "Notifications will be logged but not sent."
            )
            self._enabled = False
        else:
            try:
                # Initialize the bot
                self.bot = telegram.Bot(token=self.bot_token)
                self._enabled = True
                logger.info("Telegram notifier initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Telegram bot: {e}")
                self._enabled = False

        # Templates for different alert types
        self._templates = {
            "humidity_alert": (
                "{level} *HUMIDITY ALERT* {level}\n\n"
                "Sensor: *{sensor_name}*\n"
                "Current humidity: *{humidity:.1f}%*\n"
                "Threshold: {threshold:.1f}%\n"
                "Last reading: {timestamp}\n\n"
                "Please check the sensor and environment conditions."
            ),
            "connection_alert": (
                "{level} *CONNECTION ALERT* {level}\n\n"
                "Sensor: *{sensor_name}*\n"
                "Last connection: *{last_connection}*\n"
                "Threshold: {threshold} minutes\n\n"
                "Sensor may be offline or experiencing connectivity issues."
            ),
            "system_alert": (
                "{level} *SYSTEM ALERT* {level}\n\n"
                "*{title}*\n\n"
                "{message}"
            ),
            "custom": "{level} {message}"
        }

    @property
    def is_enabled(self) -> bool:
        """Check if the notifier is properly configured and enabled"""
        return self._enabled

    async def _send_message_async(self, text: str) -> bool:
        """
        Internal method to send a message to Telegram asynchronously.

        Args:
            text: The formatted message text to send

        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        if not self._enabled or not self.bot:
            logger.info(f"Telegram notification would have been sent: {text}")
            return False

        try:
            await self.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=telegram.constants.ParseMode.MARKDOWN,
                disable_notification=self.disable_notification
            )

            logger.debug("Telegram notification sent successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to send Telegram notification: {e}")
            return False


    async def send_humidity_alert_async(
            self,
            sensor_name: str,
            humidity: float,
            threshold: float,
            timestamp: str,
            level: AlertLevel = AlertLevel.WARNING
    ) -> bool:
        """
        Send an alert about humidity level asynchronously.

        Args:
            sensor_name: Name of the sensor
            humidity: Current humidity reading
            threshold: Threshold value that was exceeded
            timestamp: Formatted timestamp of the reading
            level: Alert level (defaults to WARNING)

        Returns:
            bool: True if alert was sent successfully
        """
        message = self._templates["humidity_alert"].format(
            level=level.value,
            sensor_name=sensor_name,
            humidity=humidity,
            threshold=threshold,
            timestamp=timestamp
        )
        return await self._send_message_async(message)

    async def send_connection_alert_async(
            self,
            sensor_name: str,
            last_connection: str,
            threshold: int,
            level: AlertLevel = AlertLevel.WARNING
    ) -> bool:
        """
        Send an alert about sensor connection issues asynchronously.

        Args:
            sensor_name: Name of the sensor
            last_connection: Formatted timestamp of last connection
            threshold: Threshold in minutes that was exceeded
            level: Alert level (defaults to WARNING)

        Returns:
            bool: True if alert was sent successfully
        """
        message = self._templates["connection_alert"].format(
            level=level.value,
            sensor_name=sensor_name,
            last_connection=last_connection,
            threshold=threshold
        )
        return await self._send_message_async(message)


    async def send_system_alert_async(
            self,
            title: str,
            message: str,
            level: AlertLevel = AlertLevel.INFO
    ) -> bool:
        """
        Send a system-level alert asynchronously.

        Args:
            title: Alert title
            message: Alert message details
            level: Alert level (defaults to INFO)

        Returns:
            bool: True if alert was sent successfully
        """
        formatted = self._templates["system_alert"].format(
            level=level.value,
            title=title,
            message=message
        )
        return await self._send_message_async(formatted)


    async def send_custom_alert_async(
            self,
            message: str,
            level: AlertLevel = AlertLevel.INFO
    ) -> bool:
        """
        Send a custom alert message asynchronously.

        Args:
            message: Alert message
            level: Alert level (defaults to INFO)

        Returns:
            bool: True if alert was sent successfully
        """
        formatted = self._templates["custom"].format(
            level=level.value,
            message=message
        )
        return await self._send_message_async(formatted)

    def add_template(self, name: str, template: str) -> None:
        """
        Add a new message template or override an existing one.

        Args:
            name: Template name
            template: Template string with format placeholders
        """
        self._templates[name] = template

    async def send_with_template_async(
            self,
            template_name: str,
            level: AlertLevel = AlertLevel.INFO,
            **kwargs: Any
    ) -> bool:
        """
        Send a message using a named template with custom parameters asynchronously.

        Args:
            template_name: Name of the template to use
            level: Alert level
            **kwargs: Values to substitute in the template

        Returns:
            bool: True if alert was sent successfully

        Raises:
            KeyError: If template_name doesn't exist
        """
        if template_name not in self._templates:
            raise KeyError(f"Template '{template_name}' not found")

        # Add level to kwargs
        kwargs["level"] = level.value

        # Format the template with provided kwargs
        message = self._templates[template_name].format(**kwargs)
        return await self._send_message_async(message)