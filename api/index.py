from fastapi import FastAPI, Request, Response
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiogram.fsm.storage.memory import MemoryStorage
import os
import asyncio
from dotenv import load_dotenv
from api.bot import dp, bot, soundcloud_handler, start_handler, help_handler, text_handler

load_dotenv()

# Initialize FastAPI app
app = FastAPI()

# Webhook settings
VERCEL_URL = os.getenv("VERCEL_URL", "your-vercel-url.vercel.app")
WEBHOOK_PATH = f"/webhook/{os.getenv('BOT_TOKEN')}"
WEBHOOK_URL = f"https://{VERCEL_URL}{WEBHOOK_PATH}"

# For local development, we'll use polling
IS_PRODUCTION = os.getenv("VERCEL", False)

@app.on_event("startup")
async def on_startup():
    """Set webhook on startup in production, start polling in development."""
    if IS_PRODUCTION:
        webhook_info = await bot.get_webhook_info()
        if webhook_info.url != WEBHOOK_URL:
            await bot.set_webhook(url=WEBHOOK_URL)
    else:
        # Delete any existing webhook before starting polling
        print("🗑 Removing existing webhook...")
        await bot.delete_webhook(drop_pending_updates=True)
        # Start polling in a background task
        asyncio.create_task(start_polling())

async def start_polling():
    """Start the bot in polling mode for local development."""
    try:
        print("🤖 Starting bot in polling mode...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    except Exception as e:
        print(f"Error starting polling: {e}")

@app.on_event("shutdown")
async def on_shutdown():
    """Cleanup on shutdown."""
    if not IS_PRODUCTION:
        await bot.session.close()

@app.post(WEBHOOK_PATH)
async def bot_webhook(request: Request):
    """Handle webhook requests from Telegram."""
    update = types.Update.model_validate(await request.json())
    await dp.feed_update(bot=bot, update=update)
    return Response(status_code=200)

@app.get("/")
async def root():
    """Health check endpoint."""
    bot_info = await bot.get_me()
    return {
        "status": "ok",
        "message": "Bot is running",
        "bot_username": bot_info.username,
        "mode": "webhook" if IS_PRODUCTION else "polling"
    } 