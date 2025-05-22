from urllib.parse import urlencode

from telegram import ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters
import aiohttp


class TelegramBot:
    def __init__(self, api_url, telegram_token):
        self.api_url = api_url
        self.application = Application.builder().token(telegram_token).build()

        # Register command handlers
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("menu", self.show_main_keyboard))
        self.application.add_handler(CommandHandler("status", self.cmd_status))
        self.application.add_handler(CommandHandler("HumiditySensors", self.cmd_sensors))

        # Register message handler for keyboard buttons
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_keyboard_input))

    def get_main_keyboard(self):
        """Create the main keyboard layout"""
        keyboard = [
            ['📊 Status', '🌡️ Sensors'],
            ['📝 Add Item', '📋 List Items'],
            ['⚙️ Settings', '❓ Help']
        ]

        return ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,  # Makes buttons smaller
            one_time_keyboard=False  # Keep keyboard visible
        )

    async def cmd_start(self, update, context):
        """Handle /start command and show keyboard"""
        reply_markup = self.get_main_keyboard()
        await update.message.reply_text(
            'Welcome! Use the buttons below to interact with the system:',
            reply_markup=reply_markup
        )

    async def show_main_keyboard(self, update, context):
        """Handle /menu command"""
        reply_markup = self.get_main_keyboard()
        await update.message.reply_text(
            'Use the buttons below:',
            reply_markup=reply_markup
        )

    async def handle_keyboard_input(self, update, context):
        """Handle button presses from the keyboard"""
        text = update.message.text

        if text == '📊 Status':
            await self.cmd_status(update, context)
        elif text == '🌡️ Sensors':
            await self.cmd_sensors(update, context)
        elif text == '📝 Add Item':
            await update.message.reply_text("Add Item functionality not implemented yet.")
        elif text == '📋 List Items':
            await update.message.reply_text("List Items functionality not implemented yet.")
        elif text == '⚙️ Settings':
            await update.message.reply_text("Settings functionality not implemented yet.")
        elif text == '❓ Help':
            await self.show_help(update, context)
        else:
            await update.message.reply_text("Unknown command. Please use the buttons below.")

    async def show_help(self, update, context):
        """Show help information"""
        help_text = """
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
/Humidity Sensors - Get sensor readings
        """
        await update.message.reply_text(help_text)

    async def cmd_status(self, update, context):
        """Handle /status command"""
        await update.message.reply_text("Checking system status...")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_url}/health") as response:
                    status = await response.json()
                    await update.message.reply_text(f"System status: {status['status']}")
        except Exception as e:
            await update.message.reply_text(f"Error checking status: {str(e)}")

    async def cmd_sensors(self, update, context):
        """Handle /Humidity Sensors command"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_url}/humidityOverview/") as response:
                    text = await response.text()
                    cleaned_text = text.replace('\\n', '\n').replace('"', '')
                    await update.message.reply_text(cleaned_text)
        except Exception as e:
            await update.message.reply_text(f"Error getting sensor data: {str(e)}")

    async def cmd_rename_humidity(self, update, context):
        """Rename humidity"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.api_url}/humiditySensors/") as response:
                    sensors = await response.json()
                    id_name = [f"{sensor['id']} - {sensor['name']}" for sensor in sensors]
                    keyboard = ReplyKeyboardMarkup(id_name, one_time_keyboard=True)
                    await update.message.reply_text(
                        'Which sensor do you want to rename?',
                        reply_markup=keyboard
                    )
        except Exception as e:
            await update.message.reply_text(f"Error renaming humidity: {str(e)}")

    def run(self):
        """Start the bot"""
        self.application.run_polling()