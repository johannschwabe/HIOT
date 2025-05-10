# app/telegram_notifier.py
import os
import logging
from typing import Optional, Dict, Any, Union, List, Callable
from enum import Enum
import asyncio
import telegram
from sqlalchemy.orm import Session
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters, CallbackContext
from dotenv import load_dotenv

from app.ENV import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from app.schemas import HumiditySensor
from app.session import SessionLocal

load_dotenv()
logger = logging.getLogger("telegram-notifier")


class AlertLevel(Enum):
    """Enum for different alert levels"""
    INFO = "ℹ️"
    WARNING = "⚠️"
    CRITICAL = "🚨"
    SUCCESS = "✅"


class TelegramNotifier:
    """
    A class to handle Telegram notifications with different alert levels,
    customizable message templates, and command handling capabilities
    using the python-telegram-bot library.
    """

    def __init__(
            self,
            disable_notification: bool = False,
            handle_commands: bool = False
    ):
        """
        Initialize the TelegramNotifier with credentials.

        Args:
            disable_notification: Whether to send notifications silently
            handle_commands: Whether to start a command listener
        """
        self.bot_token = TELEGRAM_BOT_TOKEN
        self.chat_id = TELEGRAM_CHAT_ID
        self.disable_notification = disable_notification
        self.bot = None
        self.application = None
        self._command_handlers = {}

        # Validate credentials
        if not self.bot_token or not self.chat_id:
            logger.warning(
                "Telegram credentials not properly configured. "
                "Notifications will be logged but not sent!"
            )
            self._enabled = False
        else:
            try:
                # Initialize the bot
                self.bot = telegram.Bot(token=self.bot_token)
                self._enabled = True
                logger.info("Telegram notifier initialized successfully")

                # Initialize the application for command handling if requested
                if handle_commands:
                    self._initialize_command_handler()
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
        self.register_command("rename", self._rename_humidity_sensor, "Rename humidity sensor")
        self.register_command("help", self._help_command, "Show this help message")

    def _initialize_command_handler(self):
        """Initialize the application for handling commands"""
        try:
            self.application = Application.builder().token(self.bot_token).build()

            # Register built-in commands
            self.application.add_handler(CommandHandler("start", self._start_command))
            self.application.add_handler(CommandHandler("help", self._help_command))
            self.application.add_handler(CommandHandler("status", self._status_command))

            # Handler for unknown commands
            self.application.add_handler(MessageHandler(
                filters.COMMAND, self._unknown_command
            ))

            logger.info("Command handler initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize command handler: {e}")
            self.application = None

    @property
    def is_enabled(self) -> bool:
        """Check if the notifier is properly configured and enabled"""
        return self._enabled

    @property
    def is_command_handler_enabled(self) -> bool:
        """Check if the command handler is properly configured and enabled"""
        return self._enabled and self.application is not None

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

    async def _rename_humidity_sensor(self, update: Update, context: CallbackContext):
        db = SessionLocal()
        old, new = update.message.text.split(" ", maxsplit=1)
        count = db.query(HumiditySensor).filter({HumiditySensor.id == old}).update({"name": new})
        if count:
            await update.message.reply_text(f"Updated ID {old} to name {new}")
        else:
            await update.message.reply_text(f"No humidity sensor found")

    # Built-in command handlers
    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /start command"""
        await update.message.reply_text(
            "👋 Hello! I'm your monitoring system bot.\n\n"
            "I can provide updates about your sensors and system status.\n"
            "Type /help to see available commands."
        )

    async def _help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /help command"""
        commands = [
            "/start - Start the bot",
            "/help - Show this help message",
            "/status - Get current system status"
        ]

        # Add custom commands to the help text
        for cmd, details in self._command_handlers.items():
            if "description" in details:
                commands.append(f"/{cmd} - {details['description']}")

        help_text = "Available commands:\n\n" + "\n".join(commands)
        await update.message.reply_text(help_text)

    async def _status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle the /status command"""
        # This is a placeholder - you'll want to implement your own status logic
        await update.message.reply_text(
            "✅ *System Status*\n\n"
            "All systems operational.\n"
            "Monitoring: Active\n"
            "Last check: Just now",
            parse_mode=telegram.constants.ParseMode.MARKDOWN
        )

    async def _unknown_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle unknown commands"""
        command = update.message.text.split()[0]
        await update.message.reply_text(
            f"Sorry, I don't understand the command '{command}'.\n"
            "Type /help to see available commands."
        )

    # Custom command registration
    def register_command(
            self,
            command: str,
            handler: Callable[[Update, ContextTypes.DEFAULT_TYPE], Any],
            description: str = None
    ) -> bool:
        """
        Register a custom command handler.

        Args:
            command: Command name (without the slash)
            handler: Async function to handle the command
            description: Optional description for help text

        Returns:
            bool: True if registered successfully
        """
        if not self.is_command_handler_enabled:
            logger.warning("Command handler not initialized. Can't register commands.")
            return False

        try:
            self.application.add_handler(CommandHandler(command, handler))
            self._command_handlers[command] = {
                "handler": handler,
                "description": description
            }
            logger.info(f"Registered command /{command}")
            return True
        except Exception as e:
            logger.error(f"Failed to register command /{command}: {e}")
            return False

    async def start_polling(self) -> bool:
        """
        Start polling for commands asynchronously.

        Returns:
            bool: True if polling started successfully
        """
        if not self.is_command_handler_enabled:
            logger.warning("Command handler not initialized. Can't start polling.")
            return False

        try:
            await self.application.initialize()
            await self.application.start_polling()
            logger.info("Started polling for commands")
            return True
        except Exception as e:
            logger.error(f"Failed to start polling: {e}")
            return False

    async def stop_polling(self) -> bool:
        """
        Stop polling for commands asynchronously.

        Returns:
            bool: True if polling stopped successfully
        """
        if not self.is_command_handler_enabled or not self.application:
            return False

        try:
            await self.application.stop()
            logger.info("Stopped polling for commands")
            return True
        except Exception as e:
            logger.error(f"Failed to stop polling: {e}")
            return False

    # Original notification methods
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