import os
import requests
import discord
from pyairtable import Api
import config
from utils.logger import logger

class AirtableService:
    def __init__(self):
        self.api_key = config.AIRTABLE_API_KEY
        self.base_id = config.AIRTABLE_BASE_ID
        self.tables_map = {}
        self.creator_choices = []
        self.tables = {}
        self.api = None

        if self.api_key and self.base_id:
            self.api = Api(self.api_key)
            self.fetch_metadata()
            self.initialize_tables()
        else:
            logger.warning("⚠️ Airtable credentials missing. Airtable features will be disabled.")

    def generate_table_key(self, name: str) -> str:
        """Converts a table name to a simple lowercase key."""
        import re
        return re.sub(r'[^a-z0-9]', '', name.lower())

    def fetch_metadata(self):
        """Fetches table names from Airtable and creates mapping and command choices."""
        url = f"https://api.airtable.com/v0/meta/bases/{self.base_id}/tables"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        try:
            logger.info("🔄 Fetching Airtable metadata...")
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            self.tables_map = {}
            self.creator_choices = []
            
            for table in data.get('tables', []):
                table_name = table.get('name')
                if table_name:
                    table_key = self.generate_table_key(table_name)
                    self.tables_map[table_key] = table_name
                    self.creator_choices.append(discord.app_commands.Choice(name=table_name, value=table_key))
            
            logger.info(f"✅ Found {len(self.tables_map)} tables: {list(self.tables_map.values())}")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error fetching Airtable metadata: {e}")

    def initialize_tables(self):
        """Initializes pyairtable Table objects."""
        if self.api:
            self.tables = {
                table_key: self.api.table(self.base_id, table_name)
                for table_key, table_name in self.tables_map.items()
            }

    def get_table(self, creator_key: str):
        return self.tables.get(creator_key)

    def get_ready_records(self, creator_key: str):
        """Fetches all records with Status 'Ready to publish' for a creator."""
        table = self.get_table(creator_key)
        if not table:
            return []
        try:
            return table.all(formula="{Status}='Ready to publish'")
        except Exception as e:
            logger.error(f"Error fetching ready records: {e}")
            return []

# Global instance
airtable_service = AirtableService()
