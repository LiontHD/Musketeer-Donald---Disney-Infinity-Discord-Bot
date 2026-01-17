import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
TOKEN = os.getenv('BOT_TOKEN')

# Airtable Configuration
AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')
AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID')

# Gemini Configuration
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# File Paths
KNOWLEDGE_BASE_FILE = "knowledge_base.json"
TOYBOX_DATA_FILE = "toybox_data.json"
BLACKLIST_FILE = "blacklisted_threads.json"
RATINGS_FILE = "ratings.json"
CHROMA_DB_PATH = "chroma_db"

# Channel IDs
TARGET_PURGE_CHANNEL_ID = 1378062939566637066
FORUM_CHANNEL_ID = 1253093395920851054

# Constants
VALID_TAGS = ["Disney", "Marvel", "Star Wars", "Other"]
GEMINI_MODEL_NAME = 'gemini-2.5-flash'
EMBEDDING_MODEL_NAME = 'models/embedding-001'
