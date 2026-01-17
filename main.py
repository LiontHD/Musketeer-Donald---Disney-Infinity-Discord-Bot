import discord
from discord.ext import commands
import os
import asyncio
import logging
import google.generativeai as genai

# Import configuration and logger
import config
from utils.logger import logger

# Import Views
from views.ask_toybox_view import AskToyboxPanelView
from views.counting_views import CountingView
from views.download_views import BrownbatDownloadView
from views.persistent_view import PersistentView
from views.rating_view import RatingView
from views.toybox_search_view import ToyboxView, ResultView
from views.play_view import PlayView

# Import Services
from services.counters import ToyboxCounter, SlotCounter
from services.rating_service import rating_service
from services.rag_service import rag_service

# --- Initialization ---
logger.info("Starting Donald Bot...")

# Discord Setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="/", intents=intents)

# Gemini Setup
bot.gemini_model = None
if config.GEMINI_API_KEY:
    try:
        genai.configure(api_key=config.GEMINI_API_KEY)
        bot.gemini_model = genai.GenerativeModel(config.GEMINI_MODEL_NAME)
        logger.info("✅ Google Gemini Initialized.")
    except Exception as e:
        logger.error(f"⚠️ Error initializing Google Gemini: {e}. AI features will be disabled.")
else:
    logger.warning("⚠️ Warning: GEMINI_API_KEY not found. AI features will be disabled.")

# Global Counter Instance
bot.counter = ToyboxCounter()

# --- RAG Helper Functions (Wrappers) ---
async def retrieve_toyboxes_from_vector_db(query: str, max_results: int = 15) -> list[dict]:
    """Finds relevant toyboxes using fast vector search."""
    return await rag_service.retrieve_toyboxes(query, max_results)

async def search_toyboxes(category: str):
    return await rag_service.search_by_category(category)

# --- Bot Events ---
@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user} (ID: {bot.user.id})')
    
    # Load Cogs
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'cogs.{filename[:-3]}')
                logger.info(f"✅ Loaded extension: {filename}")
            except Exception as e:
                logger.error(f"❌ Failed to load extension {filename}: {e}")

    try:
        synced = await bot.tree.sync()
        logger.info(f"✅ Synced {len(synced)} command(s).")
    except Exception as e:
        logger.error(f"❌ Failed to sync commands: {e}")

    # Add persistent views
    bot.add_view(AskToyboxPanelView())

    bot.add_view(BrownbatDownloadView())
    bot.add_view(ToyboxView(search_toyboxes))
    bot.add_view(PlayView())

    # Register RatingView for all messages with ratings
    for message_id in rating_service.message_ratings.keys():
        bot.add_view(RatingView(message_id))
    
    logger.info("✅ Persistent views added.")

    # Update toybox database
    if bot.guilds:
        from services.toybox_service import toybox_service
        await toybox_service.update_toybox_database(bot.guilds[0])
    else:
        logger.warning("⚠️ No guilds found for toybox database update!")

# --- Main Entry Point ---
if __name__ == "__main__":
    if config.TOKEN:
        bot.run(config.TOKEN)
    else:
        logger.critical("❌ BOT_TOKEN not found in environment variables.")