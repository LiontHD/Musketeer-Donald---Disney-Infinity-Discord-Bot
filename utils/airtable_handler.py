import discord
import requests
import re
from pyairtable import Api
import os

def generate_table_key(name: str) -> str:
    """Converts a table name into a simple, lowercase key."""
    return re.sub(r'[^a-z0-9]', '', name.lower())

def fetch_airtable_metadata(api_key: str, base_id: str):
    """Fetches table names from Airtable and creates a map and command choices."""
    tables_map = {}
    choices_list = []
    url = f"https://api.airtable.com/v0/meta/bases/{base_id}/tables"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    try:
        print("🔄 Fetching Airtable metadata...")
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        for table in data.get('tables', []):
            table_name = table.get('name')
            if table_name:
                table_key = generate_table_key(table_name)
                tables_map[table_key] = table_name
                choices_list.append(discord.app_commands.Choice(name=table_name, value=table_key))
        
        print(f"✅ Found {len(tables_map)} tables: {list(tables_map.values())}")
        return tables_map, choices_list
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching Airtable metadata: {e}")
        return {}, []

# Fetch metadata once
AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')
AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID')
AIRTABLE_TABLES, CREATOR_CHOICES = fetch_airtable_metadata(AIRTABLE_API_KEY, AIRTABLE_BASE_ID)

# Initialize Airtable connection
airtable = Api(AIRTABLE_API_KEY)
tables = {
    table_key: airtable.table(AIRTABLE_BASE_ID, table_name)
    for table_key, table_name in AIRTABLE_TABLES.items()
}