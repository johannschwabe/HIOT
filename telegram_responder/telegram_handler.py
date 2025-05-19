from telegram.ext import Application, CommandHandler
import aiohttp


class TelegramBot:
    def __init__(self, api_url, telegram_token):
        self.api_url = api_url
        self.application = Application.builder().token(telegram_token).build()

        # Register command handlers
        self.application.add_handler(CommandHandler("status", self.cmd_status))
        self.application.add_handler(CommandHandler("sensors", self.cmd_sensors))

    async def cmd_status(self, update, context):
        """Handle /status command"""
        await update.message.reply_text("Checking system status...")

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.api_url}/health") as response:
                status = await response.json()
                await update.message.reply_text(f"System status: {status['status']}")

    async def cmd_sensors(self, update, context):
        """Handle /sensors command"""
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.api_url}/humiditySensors/") as response:
                sensors = await response.json()

                if not sensors:
                    await update.message.reply_text("No sensors found.")
                    return

                msg = "📊 Sensors:\n\n"
                for sensor in sensors:
                    async with session.get(f"{self.api_url}/humidityMeasurements/sensor/{sensor['id']}/") as lastMeasuremt:
                        res = await lastMeasuremt.json()
                        print(res)
                        msg += f"ID: {sensor['id']} - {sensor['name']} - {res['humidity']}\n"

                await update.message.reply_text(msg)

    def run(self):
        """Start the bot"""
        self.application.run_polling()