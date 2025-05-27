# telegram_handler.py
from io import BytesIO
from typing import List, Dict, Any, Optional
import asyncio
import logging

from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
import aiohttp

logger = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self, api_url: str, telegram_token: str) -> None:
        self.api_url: str = api_url
        self.application: Application = Application.builder().token(telegram_token).build()
        self.running = False

        # Register command handlers
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("menu", self.show_main_keyboard))
        self.application.add_handler(CommandHandler("status", self.cmd_status))
        self.application.add_handler(CommandHandler("HumiditySensors", self.cmd_sensors))
        self.application.add_handler(CommandHandler("HumiditySensorRename", self.cmd_rename_humidity))
        self.application.add_handler(CallbackQueryHandler(self.button_handler))
        # Register message handler for keyboard buttons
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_keyboard_input))

    def get_main_keyboard(self) -> ReplyKeyboardMarkup:
        """Create the main keyboard layout"""
        keyboard: List[List[str]] = [
            ['📊 Status', '🌡️ Sensors'],
            ['🌧️ Rename', '🌧️ Plot'],
            ['⚙️ Settings', '❓ Help']
        ]

        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,  # Makes buttons smaller
            one_time_keyboard=False  # Keep keyboard visible
        )

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command and show keyboard"""
        reply_markup: ReplyKeyboardMarkup = self.get_main_keyboard()
        await update.message.reply_text(
            'Welcome! Use the buttons below to interact with the system:',
            reply_markup=reply_markup
        )

    async def show_main_keyboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /menu command"""
        reply_markup: ReplyKeyboardMarkup = self.get_main_keyboard()
        await update.message.reply_text(
            'Use the buttons below:',
            reply_markup=reply_markup
        )

    async def handle_keyboard_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle button presses from the keyboard"""
        text: str = update.message.text

        if 'renaming_sensor_id' in context.user_data:
            await self.process_sensor_rename(update, context, text)
            return

        if text == '📊 Status':
            await self.cmd_status(update, context)
        elif text == '🌡️ Sensors':
            await self.cmd_sensors(update, context)
        elif text == '🌧️ Rename':
            await self.cmd_rename_humidity(update, context)
        elif text == '🌧️ Plot':
            await self.cmd_plot(update, context)
        elif text == '⚙️ Settings':
            await update.message.reply_text("Settings functionality not implemented yet.")
        elif text == '❓ Help':
            await self.show_help(update, context)
        else:
            await update.message.reply_text("Unknown command. Please use the buttons below.")

    async def process_sensor_rename(self, update: Update, context: ContextTypes.DEFAULT_TYPE, new_name: str) -> None:
        """Process sensor rename with new name"""
        try:
            sensor_id = context.user_data.get("renaming_sensor_id")
            if not sensor_id:
                await update.message.reply_text("❌ Error: No sensor selected for renaming.")
                return

            # Make API call to rename sensor
            async with aiohttp.ClientSession() as session:
                data = {"name": new_name}
                async with session.post(f"{self.api_url}/humiditySensors/rename", params=data) as response:
                    if response.status == 200:
                        await update.message.reply_text(f"✅ Sensor {sensor_id} renamed to '{new_name}'")
                    else:
                        error_text = await response.text()
                        await update.message.reply_text(f"❌ Failed to rename sensor: {error_text}")

            # Clear the renaming state
            del context.user_data["renaming_sensor_id"]

        except Exception as e:
            logger.error(f"Error renaming sensor: {e}")
            await update.message.reply_text(f"❌ Error renaming sensor: {str(e)}")
            # Clear the renaming state on error too
            context.user_data.pop("renaming_sensor_id", None)

    async def show_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show help information"""
        help_text: str = """
Available commands:
📊 Status - Check system status
🌡️ Sensors - Get sensor readings
🌧️ Rename - Rename humidity sensors
🌧️ Plot - Show humidity plot
⚙️ Settings - Bot settings (coming soon)

You can also use these commands directly:
/start - Show main menu
/menu - Show main menu
/status - Check system status
/HumiditySensors - Get sensor readings
        """
        await update.message.reply_text(help_text)

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /status command"""
        await update.message.reply_text("Checking system status...")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_url}/health") as response:
                    status: Dict[str, Any] = await response.json()
                    await update.message.reply_text(f"System status: {status['status']}")
        except Exception as e:
            logger.error(f"Error checking status: {e}")
            await update.message.reply_text(f"Error checking status: {str(e)}")

    async def cmd_sensors(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /Humidity Sensors command"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_url}/humidityOverview/") as response:
                    text: str = await response.text()
                    cleaned_text: str = text.replace('\\n', '\n').replace('"', '')
                    await update.message.reply_text(cleaned_text)
        except Exception as e:
            logger.error(f"Error getting sensor data: {e}")
            await update.message.reply_text(f"Error getting sensor data: {str(e)}")

    async def cmd_rename_humidity(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Rename humidity"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_url}/humiditySensors/") as response:
                    sensors: List[Dict[str, Any]] = await response.json()
                    id_name: List[InlineKeyboardButton] = [
                        InlineKeyboardButton(
                            f"{sensor['id']} - {sensor['name']}",
                            callback_data=f"Rename {sensor['id']}"
                        ) for sensor in sensors
                    ]
                    keyboard: InlineKeyboardMarkup = InlineKeyboardMarkup([id_name])
                    await update.message.reply_text(
                        'Which sensor do you want to rename?',
                        reply_markup=keyboard
                    )
        except Exception as e:
            logger.error(f"Error getting sensors for rename: {e}")
            await update.message.reply_text(f"Error renaming humidity: {str(e)}")

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle inline button callbacks"""
        query = update.callback_query
        await query.answer()

        if query.data.startswith("Rename"):
            sensor_id: str = query.data.split(" ")[1]
            context.user_data["renaming_sensor_id"] = sensor_id
            await query.edit_message_text(f"Type new name for sensor {sensor_id}:")
        else:
            await query.edit_message_text("Unknown command. Please use the buttons below.")

    async def cmd_plot(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /plot command - show humidity plot for all sensors"""
        await update.message.reply_text("📊 Generating plot...")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_url}/humiditySensors/plot") as response:
                    if response.status == 200:
                        # Read the image data
                        image_data = await response.read()

                        # Create BytesIO object for telegram
                        image_buffer = BytesIO(image_data)
                        image_buffer.name = "humidity_plot.png"

                        # Send the photo
                        await update.message.reply_photo(
                            photo=image_buffer,
                            caption="📊 Humidity measurements - All sensors (Last 7 days)"
                        )
                    else:
                        await update.message.reply_text(f"❌ Failed to generate plot. Status: {response.status}")

        except Exception as e:
            logger.error(f"Error getting plot: {e}")
            await update.message.reply_text(f"❌ Error getting plot data: {str(e)}")

    async def run_async(self) -> None:
        """Start the bot asynchronously"""
        try:
            self.running = True
            logger.info("Starting Telegram bot...")

            # Initialize the application
            await self.application.initialize()
            await self.application.start()

            # Start polling
            await self.application.updater.start_polling()

            logger.info("Telegram bot is running and polling for updates")

            # Keep running until stopped
            while self.running:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Error running bot: {e}")
            raise
        finally:
            logger.info("Bot run_async finished")

    async def stop_async(self) -> None:
        """Stop the bot gracefully"""
        try:
            logger.info("Stopping Telegram bot...")
            self.running = False

            # Stop polling
            if self.application.updater.running:
                await self.application.updater.stop()
                logger.info("Stopped polling")

            # Stop application
            await self.application.stop()
            logger.info("Stopped application")

            # Shutdown application
            await self.application.shutdown()
            logger.info("Application shutdown complete")

        except Exception as e:
            logger.error(f"Error stopping bot: {e}")

    def run(self) -> None:
        """Legacy synchronous run method for backward compatibility"""
        logger.warning("Using legacy run() method. Consider using run_async() instead.")
        asyncio.run(self.run_async())