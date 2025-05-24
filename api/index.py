from fastapi import FastAPI, Request, Response
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
import os
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import bot handlers
from api.bot import dp, bot

# Initialize FastAPI app
app = FastAPI()

# Webhook settings
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_PATH = f"/api/webhook"

@app.get("/")
async def root():
    """Health check endpoint."""
    try:
        bot_info = await bot.get_me()
        return {
            "status": "ok",
            "message": "SoundCloud Bot is running",
            "bot_username": bot_info.username,
            "mode": "webhook"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Bot initialization failed: {str(e)}"
        }

@app.post("/api/webhook")
async def webhook_handler(request: Request):
    """Handle webhook requests from Telegram."""
    try:
        # Get the raw request body
        body = await request.body()
        
        # Parse JSON
        update_data = json.loads(body)
        
        # Create Update object
        update = types.Update.model_validate(update_data)
        
        # Process the update
        await dp.feed_update(bot=bot, update=update)
        
        return Response(status_code=200)
        
    except Exception as e:
        print(f"Webhook error: {e}")
        return Response(status_code=500)

@app.get("/api/set-webhook")
async def set_webhook():
    """Manually set webhook URL for the bot."""
    try:
        # Get Vercel URL from environment or construct it
        vercel_url = os.getenv("VERCEL_URL")
        if not vercel_url:
            return {"error": "VERCEL_URL environment variable not set"}
        
        webhook_url = f"https://{vercel_url}/api/webhook"
        
        # Set webhook
        await bot.set_webhook(url=webhook_url)
        
        return {
            "status": "success", 
            "webhook_url": webhook_url,
            "message": "Webhook set successfully"
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to set webhook: {str(e)}"
        }

@app.get("/api/webhook-info")
async def webhook_info():
    """Get current webhook information."""
    try:
        info = await bot.get_webhook_info()
        return {
            "url": info.url,
            "has_custom_certificate": info.has_custom_certificate,
            "pending_update_count": info.pending_update_count,
            "last_error_date": info.last_error_date,
            "last_error_message": info.last_error_message,
            "max_connections": info.max_connections,
            "allowed_updates": info.allowed_updates
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get webhook info: {str(e)}"
        }

# Export the app for Vercel
def handler(request, context):
    return app