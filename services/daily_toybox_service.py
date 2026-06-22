import sqlite3
import os
import datetime
import asyncio
from utils.logger import logger

DB_PATH = "daily_toybox.db"

class DailyToyboxService:
    def __init__(self):
        self._lock = asyncio.Lock()
        self.setup_db()

    def setup_db(self):
        try:
            with sqlite3.connect(DB_PATH) as db:
                # Track when users click "I Played This"
                db.execute("""
                    CREATE TABLE IF NOT EXISTS daily_plays (
                        toybox_id INTEGER,
                        user_id TEXT,
                        timestamp TEXT,
                        PRIMARY KEY (toybox_id, user_id)
                    )
                """)
                
                # Track user reviews and their moderation state
                db.execute("""
                    CREATE TABLE IF NOT EXISTS daily_reviews (
                        review_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        toybox_id INTEGER,
                        user_id TEXT,
                        review_text TEXT,
                        status TEXT DEFAULT 'pending',
                        timestamp TEXT
                    )
                """)
                
                # Track cooldowns to prevent repeat daily toyboxes
                db.execute("""
                    CREATE TABLE IF NOT EXISTS daily_history (
                        toybox_id INTEGER PRIMARY KEY,
                        timestamp TEXT
                    )
                """)
                db.commit()
            logger.info("✅ daily_toybox.db initialized successfully.")
        except Exception as e:
            logger.error(f"❌ Failed to initialize daily_toybox.db: {e}")

    # --- Plays / "I Played This" Logic ---
    
    async def toggle_play(self, toybox_id: int, user_id: int) -> bool:
        """Toggles the played status for a user. Returns True if marked as played, False if unmarked."""
        user_id_str = str(user_id)
        async with self._lock:
            with sqlite3.connect(DB_PATH) as db:
                cursor = db.execute("SELECT 1 FROM daily_plays WHERE toybox_id = ? AND user_id = ?", (toybox_id, user_id_str))
                exists = cursor.fetchone() is not None
                
                if exists:
                    db.execute("DELETE FROM daily_plays WHERE toybox_id = ? AND user_id = ?", (toybox_id, user_id_str))
                    db.commit()
                    return False
                else:
                    db.execute(
                        "INSERT INTO daily_plays (toybox_id, user_id, timestamp) VALUES (?, ?, ?)",
                        (toybox_id, user_id_str, datetime.datetime.utcnow().isoformat())
                    )
                    db.commit()
                    return True

    def get_play_count(self, toybox_id: int) -> int:
        with sqlite3.connect(DB_PATH) as db:
            cursor = db.execute("SELECT COUNT(*) FROM daily_plays WHERE toybox_id = ?", (toybox_id,))
            return cursor.fetchone()[0]

    def get_toybox_of_the_week(self):
        """Returns the toybox_id with the most plays in the last 7 days, or None."""
        seven_days_ago = (datetime.datetime.utcnow() - datetime.timedelta(days=7)).isoformat()
        with sqlite3.connect(DB_PATH) as db:
            cursor = db.execute("""
                SELECT toybox_id, COUNT(*) as play_count 
                FROM daily_plays 
                WHERE timestamp >= ?
                GROUP BY toybox_id 
                ORDER BY play_count DESC 
                LIMIT 1
            """, (seven_days_ago,))
            row = cursor.fetchone()
            if row:
                return {"toybox_id": row[0], "play_count": row[1]}
            return None

    # --- Review & Moderation Logic ---

    async def submit_review(self, toybox_id: int, user_id: int, review_text: str) -> int:
        """Submits a review as 'pending'. Returns review_id. Raises ValueError if already reviewed."""
        user_id_str = str(user_id)
        async with self._lock:
            with sqlite3.connect(DB_PATH) as db:
                # Check if user already reviewed
                cursor = db.execute("SELECT 1 FROM daily_reviews WHERE toybox_id = ? AND user_id = ?", (toybox_id, user_id_str))
                if cursor.fetchone():
                    raise ValueError("You have already submitted a review for this Toybox.")
                
                cursor = db.execute(
                    "INSERT INTO daily_reviews (toybox_id, user_id, review_text, status, timestamp) VALUES (?, ?, ?, 'pending', ?)",
                    (toybox_id, user_id_str, review_text, datetime.datetime.utcnow().isoformat())
                )
                db.commit()
                return cursor.lastrowid

    async def update_review_status(self, review_id: int, status: str):
        """Updates review status to 'approved' or 'rejected'."""
        async with self._lock:
            with sqlite3.connect(DB_PATH) as db:
                db.execute("UPDATE daily_reviews SET status = ? WHERE review_id = ?", (status, review_id))
                db.commit()

    def get_review(self, review_id: int):
        with sqlite3.connect(DB_PATH) as db:
            db.row_factory = sqlite3.Row
            cursor = db.execute("SELECT * FROM daily_reviews WHERE review_id = ?", (review_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    # --- Cooldown / History Logic ---

    def add_to_history(self, toybox_id: int):
        with sqlite3.connect(DB_PATH) as db:
            db.execute(
                "INSERT OR REPLACE INTO daily_history (toybox_id, timestamp) VALUES (?, ?)",
                (toybox_id, datetime.datetime.utcnow().isoformat())
            )
            db.commit()

    def is_on_cooldown(self, toybox_id: int, days: int = 90) -> bool:
        """Returns True if the toybox was posted within the last `days` days."""
        cutoff_date = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).isoformat()
        with sqlite3.connect(DB_PATH) as db:
            cursor = db.execute("SELECT 1 FROM daily_history WHERE toybox_id = ? AND timestamp >= ?", (toybox_id, cutoff_date))
            return cursor.fetchone() is not None

    def get_toybox_url(self, toybox_id: int) -> str:
        """Looks up the jump URL for a given toybox ID from the toybox_data.json file."""
        import json
        import config
        if not os.path.exists(config.TOYBOX_DATA_FILE):
            return ""
        try:
            with open(config.TOYBOX_DATA_FILE, 'r', encoding='utf-8') as f:
                toyboxes = json.load(f)
                for tb in toyboxes:
                    if tb.get('id') == toybox_id:
                        return tb.get('url', '')
        except Exception as e:
            logger.error(f"Error reading toybox URL for ID {toybox_id}: {e}")
        return ""

daily_toybox_service = DailyToyboxService()
