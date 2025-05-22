from io import BytesIO
from typing import List, Dict, Any, Optional
from urllib.parse import urlencode

from telegram import ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
import aiohttp


class TelegramBot:
    def __init__(self, api_url: str, telegram_token: str) -> None:
        self.api_url: str = api_url
        self.application: Application = Application.builder().token(telegram_token).build()

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

    async def show_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show help information"""
        help_text: str = """
Available commands:
📊 Status - Check system status
🌡️ Humidity Sensors - Get sensor readings
📝 Add Item - Add new item (coming soon)
📋 List Items - List all items (coming soon)
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
            await update.message.reply_text(f"Error renaming humidity: {str(e)}")

    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()

        if query.data.startswith("Rename"):
            sensor_id: str = query.data.split(" ")[1]
            context.user_data["renaming_sensor_id"] = sensor_id
            await query.edit_message_text(f"Type new name for {sensor_id}!")
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
            await update.message.reply_text(f"❌ Error getting plot data: {str(e)}")

    def run(self) -> None:
        """Start the bot"""
        self.application.run_polling()