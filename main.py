import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import Button, View
import random
import json
import os
from dotenv import load_dotenv
import aiofiles
import zipfile
import io
import re
import math
import zlib
import tempfile
from difflib import SequenceMatcher
import networkx as nx
from discord import ForumChannel
from typing import List, Dict
from collections import defaultdict
import aiohttp
import tempfile
import shutil
from pyairtable import Api
from typing import Optional
import requests
import asyncio 
import subprocess
from typing import Union
import logging
import google.generativeai as genai
from thefuzz import fuzz, process
from typing import Union
import traceback


# Discord Bot Token
load_dotenv()  # lädt die Variablen aus der .env Datei
TOKEN = os.getenv('BOT_TOKEN')
AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')
AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
knowledge_base_file = "knowledge_base.json"
toybox_data_file = "toybox_data.json"
TARGET_PURGE_CHANNEL_ID = 1361838497740095558
BLACKLIST_FILE = "blacklisted_threads.json"


gemini_model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest')
        print("✅ Google Gemini Initialized.")
    except Exception as e:
        print(f"⚠️ Error initializing Google Gemini: {e}. AI features will be disabled.")
else:
    print("⚠️ Warning: GEMINI_API_KEY not found in .env file. AI features will be disabled.")

# Bot-Einstellungen
intents = discord.Intents.default()
intents.message_content = True  # Stelle sicher, dass diese Intention gesetzt ist


# Airtable Test

AIRTABLE_TABLES = {
    "modeltrainman": "Modeltrainman",
    "bowtieguy": "The Bow-Tie Guy",
    "allnightgaming": "Allnightgaming",
    "thatbrownbat": "ThatBrownBat",
    "72pringle": "72Pringle",
    "jk": "JK",
    "misc": "Misc"
}
FORUM_CHANNEL_ID = 1253093395920851054 

# Initialize Airtable connection
airtable = Api(AIRTABLE_API_KEY)
tables = {
    table_key: airtable.table(AIRTABLE_BASE_ID, table_name)
    for table_key, table_name in AIRTABLE_TABLES.items()
}

post_id = "recaMjlETRnfUdFus"  # Setze hier eine gültige Record-ID aus deiner Airtable-Tabelle

url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Allnightgaming/{post_id}"
headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}"}
response = requests.get(url, headers=headers)

print(response.json())  # Gibt zurück, was Airtable tatsächlich liefert


VALID_TAGS = ["Disney", "Marvel", "Star Wars", "Other"]

class AskToyboxPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Start chat", style=discord.ButtonStyle.primary, custom_id="ask_toybox_start_chat")
    async def start_chat_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
            if not isinstance(interaction.channel, (discord.TextChannel, discord.ForumChannel)):
                await interaction.followup.send("Sorry, I can only start chats in regular text channels or forum channels.", ephemeral=True)
                return
            thread_name = f"Toybox Chat with {interaction.user.display_name[:50]}"
            bot_member = interaction.guild.me
            channel_perms = interaction.channel.permissions_for(bot_member)
            if not channel_perms.create_private_threads:
                await interaction.followup.send("I don't have permission to create private threads in this channel.", ephemeral=True)
                return
            if not channel_perms.send_messages_in_threads:
                await interaction.followup.send("I don't have permission to send messages in threads here.", ephemeral=True)
                return
            new_thread = await interaction.channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.private_thread,
                auto_archive_duration=1440,
                reason=f"Toybox AI chat initiated by {interaction.user.name}"
            )
            await new_thread.add_user(interaction.user)
            welcome_embed = discord.Embed(
                title="🦆 Find a Toybox with AI 🦆",
                description=(
                    f"Hi {interaction.user.mention}! I'm Donald Duck, ready to help you find the perfect Toybox adventure! 🎮\n\n"
                    f"**Tell me what you're looking for today:**\n"
                    f"• A specific character (like Iron Man or Stitch)\n"
                    f"• A type of game (racing, platformer, combat)\n"
                    f"• A franchise (Star Wars, Marvel Avengers)\n"
                    f"• Or any other ideas you have!"
                ),
                color=discord.Color.from_rgb(59, 136, 195)
            )
            await new_thread.send(embed=welcome_embed)
            await interaction.followup.send(f"I've started a private chat for you here: {new_thread.mention}", ephemeral=True)
        except Exception as e:
            print(f"Error in start_chat_button callback: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("Sorry, something went wrong while trying to start the chat.", ephemeral=True)
                else:
                    await interaction.followup.send("Sorry, something went wrong while trying to start the chat.", ephemeral=True)
            except Exception as final_e:
                print(f"Error sending final error message in start_chat_button: {final_e}")


class ToyboxCounter:
    def __init__(self):
        self.counting_sessions = {}
        self.progress_messages = {}  # Store progress message IDs
        
    def count_srr_files(self, zip_data: bytes, filename: str) -> int:
        count = 0
        with zipfile.ZipFile(io.BytesIO(zip_data)) as zip_ref:
            file_list = zip_ref.namelist()
            for file in file_list:
                base_name = os.path.basename(file)
                if re.match(r'^SRR\d+[A-Z]', base_name):
                    count += 1
        return count
    



class slotCounter:
    def __init__(self):
        self.pattern = re.compile(r"SHRR(\d+)([A-J]?)")

    async def download_and_extract_zip(self, url):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"Failed to download file: {response.status}")
                zip_data = await response.read()
        
        temp_dir = tempfile.mkdtemp()
        try:
            with zipfile.ZipFile(io.BytesIO(zip_data)) as zip_ref:
                # Get all file paths in the zip
                file_list = zip_ref.namelist()
                # Filter for SHRR files
                shrr_files = [f for f in file_list if "SHRR" in f.upper()]
                # Extract only SHRR files
                for file in shrr_files:
                    zip_ref.extract(file, temp_dir)
            
            # Walk through all subdirectories to find the SHRR files
            shrr_paths = []
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    if "SHRR" in file.upper():
                        shrr_paths.append(os.path.join(root, file))
            
            if not shrr_paths:
                raise Exception("No SHRR files found in the zip file")
                
            # Use the directory containing the SHRR files
            base_path = os.path.dirname(shrr_paths[0])
            return base_path, temp_dir
        except Exception as e:
            shutil.rmtree(temp_dir)
            raise Exception(f"Failed to process zip file: {str(e)}")

    def count_unique_scrr_files(self, folder_path):
        counts = defaultdict(set)
        
        # Walk through all subdirectories
        for root, _, files in os.walk(folder_path):
            for filename in files:
                if "SHRR" in filename.upper():  # Only process SHRR files
                    match = self.pattern.match(filename)
                    if match:
                        number, letter = match.groups()
                        counts[number].add(letter if letter else '')
        
        total_count = sum(len(letters) for letters in counts.values())
        
        # Format results
        results = []
        for number, letters in sorted(counts.items(), key=lambda x: int(x[0])):
            letters_str = ', '.join(sorted(letter for letter in letters if letter))
            base = f"SHRR{number}"
            if letters_str:
                results.append(f"{base}: {letters_str}")
            else:
                results.append(base)
            
        return total_count, results

    def find_missing_numbers(self, folder_path, min_num=0, max_num=300):
        all_numbers = set(range(min_num, max_num + 1))
        found_numbers = set()
        
        # Walk through all subdirectories
        for root, _, files in os.walk(folder_path):
            for filename in files:
                if "SHRR" in filename.upper():  # Only process SHRR files
                    match = re.findall(r'SHRR(\d+)', filename.upper())
                    if match:
                        found_numbers.update(map(int, match))
        
        missing_numbers = all_numbers - found_numbers
        return sorted(missing_numbers)
    



    

class EndCountingButton(Button):
    def __init__(self, counter: ToyboxCounter, user_id: int, progress_message: discord.Message):
        super().__init__(label="End Counting", style=discord.ButtonStyle.danger)
        self.counter = counter
        self.user_id = user_id
        self.progress_message = progress_message  # Store the progress message reference

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You cannot end this session.", ephemeral=True)
            return
        
        session_data = self.counter.counting_sessions.pop(self.user_id, [])
        if not session_data:
            await interaction.response.send_message("No counting session found.", ephemeral=True)
            return

        total = sum(count for _, count in session_data)

        # Create a more structured embed
        embed = discord.Embed(
            title="📊 Toybox Counting Results",
            description="Summary of counted toyboxes in submitted files",
            color=0x4ecca5
        )
        
        # Add a divider field
        embed.add_field(
            name="━━ File Details ━━",
            value="",
            inline=False
        )

        # Add individual file results
        for filename, count in session_data:
            formatted_filename = filename.replace('_', ' ').replace('.zip', '')
            embed.add_field(
                name=f"📦 {formatted_filename}",
                value=f"> Found `{count}` Toybox{'es' if count != 1 else ''}",
                inline=False
            )

        # Add a divider before total
        embed.add_field(
            name="━━ Summary ━━",
            value="",
            inline=False
        )

        # Add total with more emphasis
        embed.add_field(
            name="📈 Total Count",
            value=f"```\n{total} Toybox{'es' if total != 1 else ''}\n```",
            inline=False
        )

        # Add timestamp
        embed.timestamp = discord.utils.utcnow()
        
        # Enhanced footer
        embed.set_footer(
            text="Toybox Count Bot | Session Complete ✨",
            icon_url="https://cdn.discordapp.com/emojis/1039238467898613851.webp?size=96&quality=lossless"
        )

        await interaction.response.send_message(embed=embed)
        
        # Delete the progress message
        try:
            await self.progress_message.delete()
        except discord.HTTPException:
            pass  # Ignore any errors if message is already deleted
            
        self.view.stop()

class CountingView(View):
    def __init__(self, counter: ToyboxCounter, user_id: int, progress_message: discord.Message):
        super().__init__()
        self.add_item(EndCountingButton(counter, user_id, progress_message))

class PersistentView(View):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.persistent = True

    async def on_timeout(self):
        return  # Prevents the view from timing out



# Create separate view classes for each mod type
class BreezeDownloadView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Button won't timeout
        
    @discord.ui.button(
        label="Download",
        style=discord.ButtonStyle.primary,
        custom_id="breeze_download_button"  # Persistent custom_id
    )
    async def breeze_download_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        download_value = "https://drive.google.com/drive/folders/13-h3yzTR9Y4kj9JZqRvINJDPs__R8VE4"
        await interaction.response.send_message(
            f"Here's your download link: {download_value}",
            ephemeral=True
        )

class BrownbatDownloadView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Button won't timeout
        
    @discord.ui.button(
        label="Download",
        style=discord.ButtonStyle.primary,
        custom_id="brownbat_download_button"  # Persistent custom_id
    )
    async def brownbat_download_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        download_url = "https://drive.usercontent.google.com/download?id=1oJnfDwdiOE2xACPMVaMUQzRDXsaBVT0m&export=download&authuser=0"
        await interaction.response.send_message(
            f"Here's your download link: {download_url}",
            ephemeral=True
        )

# Add both views to the bot
async def setup_views():
    bot.add_view(BreezeDownloadView())
    bot.add_view(BrownbatDownloadView())

bot = commands.Bot(command_prefix="/", intents=intents)

# Globale Variablen für nachrichten-spezifische Bewertungen
message_ratings = {}  # Ein Dictionary, um die Bewertungen pro Nachricht zu speichern
channel_titles = {}  # Speichert die Titel der Kanäle für den /play-Befehl
counter = ToyboxCounter()

# Funktion zum Laden und Speichern von Bewertungen
# Funktion zum Laden und Speichern von Bewertungen
def load_ratings():
    global message_ratings, channel_titles
    if os.path.exists('ratings.json'):
        with open('ratings.json', 'r') as f:
            data = json.load(f)
            # Stelle sicher, dass alle IDs als Integer geladen werden
            message_ratings = {
                msg_id: {
                    'ratings': {int(user_id): rating for user_id, rating in info['ratings'].items()},
                    'average': info['average'],
                    'num_ratings': info['num_ratings']
                }
                for msg_id, info in data.get('ratings', {}).items()
            }
            channel_titles = data.get('titles', {})

async def update_toybox_database():
    # Prüfe, ob die Datei existiert, erstelle sie ansonsten mit einer leeren Liste
    if not os.path.exists(toybox_data_file):
        with open(toybox_data_file, "w") as f:
            json.dump([], f)


def save_ratings():
    with open('ratings.json', 'w') as f:
        # Konvertiere alle IDs zurück zu Strings für die Speicherung
        json.dump({
            'ratings': {
                msg_id: {
                    'ratings': {str(user_id): rating for user_id, rating in info['ratings'].items()},
                    'average': info['average'],
                    'num_ratings': info['num_ratings']
                }
                for msg_id, info in message_ratings.items()
            },
            'titles': channel_titles
        }, f)

class RatingView(discord.ui.View):
    def __init__(self, message_id):
        super().__init__(timeout=None)  # Make view persistent
        self.message_id = message_id

    @discord.ui.button(label="⭐️", style=discord.ButtonStyle.primary, custom_id="rate_1")
    async def rate_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_rating(interaction, 1)

    @discord.ui.button(label="⭐️⭐️", style=discord.ButtonStyle.primary, custom_id="rate_2")
    async def rate_2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_rating(interaction, 2)

    @discord.ui.button(label="⭐️⭐️⭐️", style=discord.ButtonStyle.primary, custom_id="rate_3")
    async def rate_3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_rating(interaction, 3)

    @discord.ui.button(label="⭐️⭐️⭐️⭐️", style=discord.ButtonStyle.primary, custom_id="rate_4")
    async def rate_4(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_rating(interaction, 4)

    @discord.ui.button(label="⭐️⭐️⭐️⭐️⭐️", style=discord.ButtonStyle.primary, custom_id="rate_5")
    async def rate_5(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_rating(interaction, 5)

    async def handle_rating(self, interaction: discord.Interaction, rating: int):
        user_id = interaction.user.id
        message_id = self.message_id

        # Sicherstellen, dass die Nachricht existiert
        if message_id not in message_ratings:
            message_ratings[message_id] = {'ratings': {}, 'average': 0, 'num_ratings': 0}

        # Überprüfen, ob der Nutzer bereits bewertet hat
        already_voted = user_id in message_ratings[message_id]['ratings']

        # Benutzerbewertung aktualisieren oder hinzufügen
        if already_voted:
            old_rating = message_ratings[message_id]['ratings'][user_id]
            message_ratings[message_id]['ratings'][user_id] = rating
            await interaction.response.send_message(
                f"You changed your rating from {old_rating} ⭐️ to {rating} ⭐️!", ephemeral=True
            )
        else:
            message_ratings[message_id]['ratings'][user_id] = rating
            await interaction.response.send_message(
                f'You gave {rating} ⭐️ for this toybox!', ephemeral=True
            )
            message_ratings[message_id]['num_ratings'] += 1

        # Aktualisiere und speichere den durchschnittlichen Rating-Wert
        self.update_average_rating(message_id)
        save_ratings()

        # Aktualisiere das Embed mit den neuen Bewertungen
        await update_rating_embed(interaction.message, message_id)

    def update_average_rating(self, message_id):
        ratings = message_ratings[message_id]['ratings'].values()
        if ratings:
            average = sum(ratings) / len(ratings)
            message_ratings[message_id]['average'] = average




# --- RAG Helper Function ---
# *** Angepasste Gewichtung und möglicherweise andere Name-Matching-Methode ***
def find_relevant_toyboxes(query: str, toybox_data: List[Dict], expansion_keywords: set, max_results: int = 20) -> List[Dict]:
    """Finds relevant toyboxes using fuzzy matching and direct keyword checks with adjusted weights."""
    if not toybox_data:
        return []
    query_lower = query.lower()
    scores = []
    print(f"--- Starting find_relevant_toyboxes ---")
    print(f"Searching for query (len {len(query_lower.split())}): '{query_lower[:150]}...'")
    print(f"Using expansion keywords: {expansion_keywords}")

    processed_count = 0
    for toybox in toybox_data:
        processed_count += 1
        toybox_name = toybox.get("name", "N/A")
        toybox_name_lower = toybox_name.lower()
        toybox_desc = toybox.get("description", "")
        toybox_desc_lower = toybox_desc.lower()

        # === Name Match Score ===
        # Behalte token_set_ratio, da es gut ist, aber gib ihm mehr Gewicht.
        name_match_score_raw = fuzz.token_set_ratio(query_lower, toybox_name_lower)
        # ALTERNATIVE (Testen!): partial_ratio könnte besser sein, um zu prüfen, ob der KURZE Name im LANGEN Query enthalten ist.
        # name_match_score_raw = fuzz.partial_ratio(toybox_name_lower, query_lower) # Reihenfolge wichtig!

        # === Tag Match Score ===
        tag_match_points = 0
        query_words = set(query_lower.split())
        tags_lower = [tag.lower() for tag in toybox.get("tags", [])]
        # Prüfe NUR noch, ob explizite Tags der Toybox mit Query-Wörtern übereinstimmen.
        # Entferne die Prüfung 'tag in query_lower', da dies zu viele unspezifische Treffer gibt.
        # Gib Punkte nur für spezifische Übereinstimmungen.
        tag_hits = 0
        matched_tags = []
        if any(q_word in tag for tag in tags_lower for q_word in query_words):
             tag_hits = 1 # Es gibt einen Treffer
             # Optional: zähle, wie viele Keywords in den Tags vorkommen? Kann komplex werden.
             # matched_tags = [tag for tag in tags_lower if any(qw in tag for qw in query_words)]


        # === Description Match Score ===
        desc_match_score_raw = fuzz.partial_ratio(query_lower, toybox_desc_lower)

        # === Direkter Keyword-Boost (wenn Query Expansion stattfand) ===
        direct_keyword_boost = 0
        keyword_hits_in_name = 0
        keyword_hits_in_desc = 0
        matched_keywords_in_name = []
        if expansion_keywords:
            name_hit = False
            desc_hit = False
            for kw in expansion_keywords:
                # *** Verwende partial_ratio für Keyword im Namen/Beschreibung ***
                # Das ist robuster gegen leichte Variationen als 'in'. Score > 90 ist quasi ein Treffer.
                if fuzz.partial_ratio(kw, toybox_name_lower) > 90:
                    keyword_hits_in_name += 1
                    matched_keywords_in_name.append(kw)
                    name_hit = True
                if fuzz.partial_ratio(kw, toybox_desc_lower) > 90:
                    keyword_hits_in_desc += 1
                    desc_hit = True

            # Boost-Logik (behalte bei +40 / +15)
            if name_hit:
                direct_keyword_boost += 40
            elif desc_hit:
                direct_keyword_boost += 15

        # === Combine Scores (ANGEPASSTE GEWICHTE) ===
        # - Name: Höheres Gewicht, da der Titel wichtiger ist.
        # - Tag: Geringeres Gewicht für den ALLGEMEINEN Tag-Match (Treffer Ja/Nein).
        # - Desc: Mittleres Gewicht.
        # - KW Boost: Additiv, stark, wenn vorhanden.
        name_weight = 0.8  # Starkes Gewicht für Namensähnlichkeit
        tag_weight = 0.3   # Reduziertes Gewicht für bloße Tag-Übereinstimmung
        desc_weight = 0.5  # Mittleres Gewicht für Beschreibung
        tag_max_points = 60 # Maximalpunkte für Tag-Übereinstimmung (statt 85)

        name_weighted = name_match_score_raw * name_weight
        # Berechne Tag-Score anders: Wenn es einen Hit gab, gib tag_max_points * tag_weight Punkte.
        tag_weighted = (tag_max_points * tag_weight) if tag_hits > 0 else 0
        # Optional komplexer: Gewichte die Anzahl der Tag-Hits? z.B. min(tag_hits, 3) * (tag_max_points/3 * tag_weight)
        desc_weighted = desc_match_score_raw * desc_weight

        combined_score = name_weighted + tag_weighted + desc_weighted + direct_keyword_boost

        relevance_threshold = 65
        # *** DETAILLIERTER DEBUG OUTPUT ***
        if combined_score > 50 or "guardians" in toybox_name_lower or "galaxy" in toybox_name_lower or "dagobah" in toybox_name_lower :
             print(f"\n-- Toybox: '{toybox_name}' (ID: {toybox.get('id')}) --")
             print(f"   Name Match: {name_match_score_raw:.1f} -> Weighted: {name_weighted:.1f} (Weight: {name_weight})")
             print(f"   Tag Match: {tag_hits} hit(s) -> Weighted: {tag_weighted:.1f} (Weight: {tag_weight}, MaxPts: {tag_max_points}) (Tags: {toybox.get('tags')})")
             print(f"   Desc Match: {desc_match_score_raw:.1f} -> Weighted: {desc_weighted:.1f} (Weight: {desc_weight})")
             if expansion_keywords:
                 print(f"   KW Boost: {direct_keyword_boost:.1f} (Name Hits: {keyword_hits_in_name} {matched_keywords_in_name}, Desc Hits: {keyword_hits_in_desc})")
             else:
                  print(f"   KW Boost: N/A")
             print(f"   ===> TOTAL SCORE: {combined_score:.1f} (Threshold: {relevance_threshold})")

        if combined_score >= relevance_threshold:
            scores.append((combined_score, toybox))

    print(f"--- Finished find_relevant_toyboxes ({processed_count} items processed) ---")
    scores.sort(key=lambda item: item[0], reverse=True)

    print(f"--- Top Scores (up to 30) ---")
    for i, (score, tb) in enumerate(scores[:30]):
        print(f"   {i+1}. {score:.1f} - '{tb.get('name')}' (ID: {tb.get('id')})")
    print(f"--------------------------")

    top_results = [toybox for score, toybox in scores[:max_results]] # Verwende ursprüngliches max_results hier
    print(f"Found {len(scores)} toyboxes passing threshold {relevance_threshold} (returning top {max_results}).") # Logge alle gefundenen
    return top_results



class ToyboxView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Make view persistent
        
    @discord.ui.button(label="🏰 Disney", style=discord.ButtonStyle.primary, custom_id="toybox_disney")
    async def disney_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.category_callback(interaction, "Disney")
        
    @discord.ui.button(label="🦸 Marvel", style=discord.ButtonStyle.primary, custom_id="toybox_marvel")
    async def marvel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.category_callback(interaction, "Marvel")
        
    @discord.ui.button(label="✨ Star Wars", style=discord.ButtonStyle.primary, custom_id="toybox_starwars")
    async def starwars_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.category_callback(interaction, "Star Wars")
        
    @discord.ui.button(label="🎯 Other", style=discord.ButtonStyle.primary, custom_id="toybox_other")
    async def other_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.category_callback(interaction, "Other")

    async def category_callback(self, interaction: discord.Interaction, category: str):
        # Defer the response to prevent interaction timeout
        await interaction.response.defer(ephemeral=True)
        
        results = await search_toyboxes(category)
        
        if not results:
            embed = discord.Embed(
                title=f"🎮 {category} Toyboxes",
                description=f"No Toyboxes found in the **{category}** category.",
                color=discord.Color.blue()
            )
            view = ResultView([], category)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            return
            
        results.sort(key=lambda toybox: toybox['name'].lower())
        view = ResultView(results, category)
        await interaction.followup.send(embed=view.create_embed(), view=view, ephemeral=True)

class ResultView(discord.ui.View):
    def __init__(self, results, category):
        super().__init__(timeout=None)
        self.results = results
        self.category = category
        self.page = 0
        self.items_per_page = 5
        self.total_pages = max(1, (len(results) + self.items_per_page - 1) // self.items_per_page)
        
        # Add pagination components
        self.update_buttons()
        if self.total_pages > 1:
            self.add_page_select()

    def update_buttons(self):
        # Update button states based on current page
        self.prev_button.disabled = self.page == 0
        self.next_button.disabled = self.page == self.total_pages - 1

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary, custom_id="toybox_prev")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            self.update_buttons()
            if hasattr(self, 'page_select'):
                self.update_page_select()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.defer()
            
    @discord.ui.button(label="Back to Categories", style=discord.ButtonStyle.secondary, custom_id="toybox_back")
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.delete_original_response()

        
    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary, custom_id="toybox_next")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.total_pages - 1:
            self.page += 1
            self.update_buttons()
            if hasattr(self, 'page_select'):
                self.update_page_select()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.defer()

    def add_page_select(self):
        if self.total_pages <= 25:
            # Single dropdown for pages
            options = [
                discord.SelectOption(
                    label=f"Page {i + 1}",
                    value=str(i),
                    default=(i == self.page)
                )
                for i in range(self.total_pages)
            ]
            
            select = discord.ui.Select(
                placeholder=f"Page {self.page + 1}",
                options=options,
                custom_id="toybox_page_select"
            )
            
            async def page_select_callback(interaction: discord.Interaction):
                self.page = int(select.values[0])
                self.update_buttons()
                select.placeholder = f"Page {self.page + 1}"
                await interaction.response.edit_message(embed=self.create_embed(), view=self)
            
            select.callback = page_select_callback
            self.page_select = select
            self.add_item(select)
        else:
            # Group selection for many pages
            group_count = (self.total_pages + 24) // 25
            current_group = self.page // 25
            
            # Group selector
            group_options = [
                discord.SelectOption(
                    label=f"Pages {i * 25 + 1}-{min((i + 1) * 25, self.total_pages)}",
                    value=str(i),
                    default=(i == current_group)
                )
                for i in range(group_count)
            ]
            
            group_select = discord.ui.Select(
                placeholder=f"Pages {current_group * 25 + 1}-{min((current_group + 1) * 25, self.total_pages)}",
                options=group_options,
                custom_id="toybox_group_select"
            )
            
            # Page selector within group
            page_options = [
                discord.SelectOption(
                    label=f"Page {i + 1}",
                    value=str(i),
                    default=(i == self.page)
                )
                for i in range(current_group * 25, min((current_group + 1) * 25, self.total_pages))
            ]
            
            page_select = discord.ui.Select(
                placeholder=f"Page {self.page + 1}",
                options=page_options,
                custom_id="toybox_page_select"
            )
            
            async def group_select_callback(interaction: discord.Interaction):
                group_index = int(group_select.values[0])
                self.page = group_index * 25
                self.update_buttons()
                self.update_page_select()
                await interaction.response.edit_message(embed=self.create_embed(), view=self)
            
            async def page_select_callback(interaction: discord.Interaction):
                self.page = int(page_select.values[0])
                self.update_buttons()
                page_select.placeholder = f"Page {self.page + 1}"
                await interaction.response.edit_message(embed=self.create_embed(), view=self)
            
            group_select.callback = group_select_callback
            page_select.callback = page_select_callback
            
            self.group_select = group_select
            self.page_select = page_select
            self.add_item(group_select)
            self.add_item(page_select)

    def update_page_select(self):
        if hasattr(self, 'page_select'):
            if hasattr(self, 'group_select'):
                # Update group select
                current_group = self.page // 25
                self.group_select.placeholder = f"Pages {current_group * 25 + 1}-{min((current_group + 1) * 25, self.total_pages)}"
                
                # Update page select options within current group
                start_page = current_group * 25
                end_page = min((current_group + 1) * 25, self.total_pages)
                self.page_select.options = [
                    discord.SelectOption(
                        label=f"Page {i + 1}",
                        value=str(i),
                        default=(i == self.page)
                    )
                    for i in range(start_page, end_page)
                ]
            else:
                # Single page select
                self.page_select.placeholder = f"Page {self.page + 1}"
                for option in self.page_select.options:
                    option.default = (int(option.value) == self.page)

    def create_embed(self):
        embed = discord.Embed(
            title=f"🎮 {self.category} Toyboxes (Page {self.page + 1} of {self.total_pages})",
            color=discord.Color.blue()
        )
        embed.description = f"Found **{len(self.results)}** {self.category} Toyboxes"
        
        start_index = self.page * self.items_per_page
        end_index = min(start_index + self.items_per_page, len(self.results))
        
        for toybox in self.results[start_index:end_index]:
            embed.add_field(
                name=toybox["name"],
                value=f"🔗 [Link]({toybox['url']})\n📌 {', '.join(toybox['tags'])}",
                inline=False
            )
        return embed

async def search_toyboxes(category: str):
    # This is a placeholder function - replace with your actual database query
    # Example return format:
    return [
        {
            "name": f"Example Toybox {i}",
            "url": f"https://example.com/toybox{i}",
            "tags": ["tag1", "tag2"],
            "category": category
        }
        for i in range(1, 6)
    ]


# Funktion, um Sterne basierend auf einer durchschnittlichen Bewertung anzuzeigen (abgerundet)
def get_star_rating(avg_rating):
    full_stars = int(avg_rating)
    round_up = (avg_rating - full_stars) >= 0.6
    return "⭐️" * (full_stars + (1 if round_up else 0))

# Funktion zum Erstellen oder Aktualisieren des Embeds für eine bestimmte Nachricht
async def update_rating_embed(message, message_id):
    if message_id in message_ratings and message_ratings[message_id]['ratings']:
        # Berechne die durchschnittliche Bewertung für diese Nachricht
        avg_rating = message_ratings[message_id]['average']

        # Berechne die Farbe basierend auf der Bewertung
        if avg_rating < 3:
            embed_color = discord.Color.green()
        elif 3 <= avg_rating < 4:
            embed_color = discord.Color.blue()
        elif 4 <= avg_rating < 4.8:
            embed_color = discord.Color.purple()
        else:
            embed_color = discord.Color.gold()

        # Dynamische Sterne für das Toybox Rating (abgerundet)
        toybox_stars = get_star_rating(avg_rating)

        embed = discord.Embed(
            title=f"Toybox rating: {toybox_stars}",  # Dynamische Sterne im Titel
            description="What do you think about this toybox? Please, vote after you played it.",
            color=embed_color
        )
        embed.add_field(name="Average rating:", value=f"{avg_rating:.2f} ⭐️", inline=False)
        embed.add_field(name="Number of ratings:", value=f"{message_ratings[message_id]['num_ratings']} ratings.", inline=False)
    else:
        embed = discord.Embed(
            title="Toybox rating: ⭐️⭐️⭐️⭐️⭐️",
            description="What do you think about this toybox? Please, vote after you played it.",
            color=discord.Color.blue()
        )
        embed.add_field(name="Average rating:", value="No ratings yet.", inline=False)
        embed.add_field(name="Number of ratings:", value="0 ratings.", inline=False)

    await message.edit(embed=embed, view=RatingView(message_id))


toybox_data_file = "toybox_data.json"

class SimpleTagAnalyzer:
    def __init__(self):
        # Disney keywords including characters and movies
        self.disney_keywords = {
            # General Disney terms
            "disney", "princess", "walt", "disneyland", "disney land", "disneyworld", "disney world",
            
            
            
            # Original list entries
            "alice in wonderland", "alice", "mad hatter", "time",
            "inside out", "joy", "sadness", "anger", "fear", "disgust", "inside-out",
            "mulan", "fa mulan",
            "aladdin", "jasmine", 
            "nightmare before christmas", "jack skellington",
            "pirates of the caribbean", "jack sparrow", "barbossa", "davy jones", "pirates",
            "zootopia", "judy hopps", "nick wilde", "judy", "nick", "zoomania",
            "wreck it ralph", "ralph", "vanellope", "wreck-it ralph", "fix-it felix", "hero's duty",
            "big hero 6", "baymax", "hiro", 
            "tron", "quorra", "sam flynn", "flynn", "grid",
            "tinker bell", "peter pan", "neverland", "tinkerbell",
            "maleficent", "sleeping beauty",
            "incredibles", "mr incredible", "elastigirl", "dash", "violet", "syndrome",
            "phineas and ferb", "phineas", "perry", "agent p", "ferb",
            "lilo & stitch", "lilo and stitch", "stitch", "lilo",
            "tangled", "rapunzel",
            "jungle book", "baloo", "mowgli", "jungle", 
            "lone ranger", "tonto",

            # New additions
            "frozen", "elsa", "anna", "olaf", "sven", "arendelle", "let it go",
            "moana", "maui", "pua", "heihei", "te fiti", "wayfinding",
            "lion king", "simba", "mufasa", "scar", "timon", "pumbaa", "hakuna matata",
            "cinderella", "fairy godmother", "prince charming", "glass slipper",
            "beauty and the beast", "belle", "beast", "gaston", "lumiere", "cogsworth",
            "hercules", "hades", "megara", "pegasus", "phil", "mount olympus",
            "snow white", "seven dwarfs", "evil queen", "poison apple",
            "little mermaid", "ariel", "ursula", "flounder", "sebastian", "under the sea",
            "encanto", "mirabel", "bruno", "casita", "we don't talk about bruno",
            "coco", "miguel", "hector", "dante", "land of the dead", "remember me",
            "toy story", "woody", "buzz lightyear", "andy", "sid", "to infinity and beyond", "jessie", "toystory", "toy-story",
            "finding nemo", "nemo", "marlin", "dory", "finding dory",
            "up", "carl", "ellie", "russell", "dug", "paradise falls",
            "brave", "merida",
            "princess and the frog", "tiana", "naveen", "mama odie", "dr. facilier",
            "raya and the last dragon", "sisu", "kumandra", "trust",
            "pocahontas", "john smith", "grandmother willow", "colors of the wind",
            "hunchback of notre dame", "quasimodo", "esmeralda", "clopin",
            "tarzan", "jane", "kerchak", "terk", "trashin' the camp",
            "winnie the pooh", "piglet", "eeyore", "tigger", "hundred acre wood",
            "101 dalmatians", "cruella de vil", "pongo", "perdita", "dalmatians",
            "aristocats", "duchess", "thomas o'malley", "edgar", "everybody wants to be a cat",
            "lady and the tramp", "spaghetti kiss", "trusty", "jock",
            "robin hood", "little john", "prince john", "robin hood and maid marian",
            "sword in the stone", "merlin", "archimedes", "wart", "excalibur",
            "atlantis: the lost empire", "milo thatch", "kida", "shepherd's journal",
            "treasure planet", "jim hawkins", "long john silver", "morph",
            "chicken little", "buck cluck", "abby mallard", "the sky is falling",
            "bolt", "mittens", "rhino", "white fang", "super bark",
            "emperor's new groove", "kuzco", "kronk", "yzma", "pull the lever",
            "meet the robinsons", "keep moving forward", "bowler hat guy", "doris",
            "rescuers", "bernard", "bianca", "madame medusa", "devil's bayou",
            "oliver & company", "dodger", "georgette", "why should i worry",
            "fantasia", "sorcerer's apprentice", "chernabog", "dance of the hours",
            "dumbo", "timothy q. mouse", "pink elephants", "baby mine",
            "bambi", "thumper", "flower", "man is in the forest",
            "pinocchio", "geppetto", "figaro", "when you wish upon a star",
            "peter pan", "wendy", "captain hook", "tick tock croc", "second star to the right",
            "mary poppins", "supercalifragilisticexpialidocious", "jolly holiday", "chim chim cheree",
            "three caballeros", "donald duck", "jose carioca", "panchito", "ay caramba",
            "chip 'n' dale", "rescue rangers", "gadget hackwrench", "monterey jack",
            "ducktales", "huey", "dewey", "louie", "scrooge mcduck", "woo-oo",
            "darkwing duck", "let's get dangerous", "launchpad mcquack", "st. canard",
            "gravity falls", "dipper", "mabel", "grunkle stan", "mystery shack",
            "the owl house", "luz", "eda", "king", "boiling isles",
            "amphibia", "anne boonchuy", "sprig", "hop pop", "wally",
            "star vs. the forces of evil", "star butterfly", "marco", "wand", "mewni",
            "kim possible", "ron stoppable", "rufus", "naked mole rat", "what's the sitch",
            "gargoyles", "goliath", "demona", "xanatos", "stone sleep",
            "sofia the first", "enchancia", "princess test", "amulet of avalor",
            "elena of avalor", "scepter of light", "jaquin", "zuzo",
            "mickey mouse", "minnie mouse", "pluto", "goofy", "hot dog dance", "mickey mouse", "mickey", "minnie mouse", "minnie", "donald duck", "donald",
            "kingdom hearts", "keyblade", "sora", "riku", "kairi", "heartless"
            "a bug’s life", "flik", "princess atta", "hopper", "dot", "tuck and roll", "anthill", "colony", "grasshoppers", "inventions",
            "monsters, inc.", "sulley", "mike wazowski", "boo", "randall", "roz", "scream energy", "doors", "monstropolis", "scarers", "university", "monsters u",
            "cars", "lightning mcqueen", "mcqueen", "mc queen", "mater", "sally", "doc hudson", "radiator springs", "francesco", "radiator springs", "holley shiftwell", "cars 2", "cars 3", "piston cup", "ka-chow", "rust-eze", "tow mater",
            "ratatouille", "remy", "linguini", "colette", "chef gusteau", "ego", "anyone can cook", "la ratatouille", "little chef", "critic",
            "monsters university", "young sulley", "young mike", "dean hardscrabble", "ok", "fear tech", "scare games", "fraternity scream", "jump scare",
            "the good dinosaur", "arlo", "spot", "butch", "nash", "ramsey", "river adventure", "family journey", "survival", "claw marks"
        }

        # Marvel keywords including characters and movies
        self.marvel_keywords = {
            # General Marvel terms
            "marvel", "avengers", "shield", "xmen", "x-men",
            
            # Major characters
            
            "iron man", "tony stark", "iron-man",
            "captain america", "steve rogers",
            "thor",
            "hulk", "bruce banner", "the incredible hulk",
            "black widow", "natasha romanoff",
            "hawkeye", "clint barton",
            "spider man", "spiderman", "peter parker",
            "black panther", "tchalla", "t'challa", "vibranium",
            "ant man", "scott lang", "ant-man",
            "vision", "wandavision",
            "doctor strange",
            "iron fist",
            "rocket",
            "star lord",
            "nick fury",
            "thanos",
            "falcon",
            "loki",
            "asgard",
            "wakanda",
            "sokovia",
            "gamora",
            "venom",
            "yondu",
            "ronan",
            "hulkbuster",
            "captain marvel",
            "nova",
            "wanda",
            "ultron",
            "drax",
            "groot",
            "green goblin", "norman osborn",
            "winter soldier"
            
            # Movies
            "infinity war",
            "endgame",
            "civil war",
            "age of ultron",
            "guardians of the galaxy", "gotg",
        }

        # Star Wars keywords including characters and movies
        self.star_wars_keywords = {
            # General Star Wars terms
            "star wars", "starwars", "jedi", "sith", "force", "lightsaber", "rebel", "droid", "resistance", "millennium falcon", "wookie", "wookies",
            "ewoks", "high republic", "republic",

            
            # Original characters
            "luke skywalker", "luke",
            "darth vader", "vader", "anakin skywalker", "anakin",
            "princess leia", "leia",
            "han solo", "solo",
            "chewbacca", "chewie",
            "yoda","mace windu",
            "obi wan", "obi-wan", "kenobi",
            "boba fett", "boba", "mando",
            "darth maul", "maul",
            "jabba", "r2d2", "c3po", "grogu", "palpatine", "clones", "general grievous",
            
            # planets/locations
            "tatooine", "tatooine planet",
            "coruscant", "coruscant planet",
            "naboo", "naboo planet",
            "hoth", "hoth planet",
            "dagobah", "dagobah planet",
            "bespin", "bespin planet",
            "endor", "endor planet", "forest moon of endor",
            "alderaan", "alderaan planet",
            "mustafar", "mustafar planet",
            "kashyyyk", "kashyyyk planet",
            "kamino", "kamino planet",
            "geonosis", "geonosis planet",
            "utapau", "utapau planet",
            "felucia", "felucia planet",
            "mygeeto", "mygeeto planet",
            "cato neimoidia", "cato neimoidia planet",
            "sullust", "sullust planet",
            "jakku", "jakku planet",
            "ahch-to", "ahch-to planet",
            "crait", "crait planet",
            "exegol", "exegol planet"
            "death star",


            # star wars rebels
            "ezra bridger", "ezra",
            "kanan jarrus", "kanan", "caleb dume",
            "hera syndulla", "hera",
            "sabine wren", "sabine",
            "zeb orrelios", "zeb", "garazeb",
            "chopper", "c1-10p",
            "agent kallus", "alexsandr kallus", "kallus",
            "grand admiral thrawn", "thrawn", "mitth'raw'nuruodo",
            "darth vader", "vader", "anakin skywalker",
            "ahsoka tano", "ahsoka", "fulcrum",

            # Sequels characters
            "rey",
            "finn",
            "kylo ren", "ben solo", "first order",
            "tfa",
            "poe", "poe dameron", 

            # Movies and shows
            "episode", "prequels", "originals", "sequels",
            "phantom menace",
            "attack of the clones",
            "revenge of the sith",
            "new hope",
            "empire strikes back",
            "return of the jedi",
            "force awakens", "the force awakens",
            "last jedi",
            "rise of skywalker",
            "mandalorian", "the mandalorian",
            "clone wars", "tcw", "the clone wars",
            "rogue one",
            "rebels"
        }

    def analyze_text(self, text: str) -> list[str]:
        """
        Analyzes text and returns matching franchise tags.
        Returns "Other" if no franchise tags are found.
        Now includes character names and movie titles for more accurate matching.
        """
        text = text.lower()
        tags = []
        
        # Check for each franchise using keywords
        if any(keyword in text for keyword in self.disney_keywords):
            tags.append("Disney")
            
        if any(keyword in text for keyword in self.marvel_keywords):
            tags.append("Marvel")
            
        if any(keyword in text for keyword in self.star_wars_keywords):
            tags.append("Star Wars")
            
        # If no tags were found, add "Other"
        if not tags:
            tags.append("Other")
            
        return tags

class Bot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="/", intents=intents)
        
    async def setup_hook(self):
        print("Bot is setting up...")

bot = Bot()

async def update_toybox_database(guild: discord.Guild):
    forum_channel = guild.get_channel(forum_channel_id)
    if not forum_channel or not isinstance(forum_channel, ForumChannel):
        print("⚠️ Forum channel not found!")
        return

    # Load existing data
    existing_toyboxes = {}
    try:
        with open(toybox_data_file, "r", encoding='utf-8') as f:
            existing_data = json.load(f)
            # Create a lookup dictionary using thread ID
            existing_toyboxes = {str(item['id']): item for item in existing_data}
    except FileNotFoundError:
        print("📝 No existing toybox data found, creating new database...")

    analyzer = SimpleTagAnalyzer()
    toybox_list = []
    
    # Gather all threads
    threads = list(forum_channel.threads)
    async for archived_thread in forum_channel.archived_threads(limit=None):
        threads.append(archived_thread)
    
    print(f"🔄 Updating Toybox database with {len(threads)} threads...")
    
    for thread in threads:
        thread_id = str(thread.id)
        print(f"📝 Processing Thread: {thread.name}")

        # If thread exists and already has tags, preserve them
        if thread_id in existing_toyboxes:
            toybox_entry = existing_toyboxes[thread_id]
            print(f"✓ Preserving existing tags for '{thread.name}': {', '.join(toybox_entry['tags'])}")
        else:
            # Only analyze new threads or threads without tags
            first_message = None
            async for msg in thread.history(oldest_first=True, limit=1):
                first_message = msg
                break

            if not first_message:
                print(f"⚠️ No messages in thread: {thread.name}")
                continue

            analysis_text = f"{thread.name} {first_message.content}"
            tags = analyzer.analyze_text(analysis_text)

            toybox_entry = {
                "id": thread.id,
                "name": thread.name,
                "url": thread.jump_url,
                "tags": tags
            }
            print(f"✅ Added new tags to '{thread.name}': {', '.join(tags)}")

        toybox_list.append(toybox_entry)

    # Save updated database
    with open(toybox_data_file, "w", encoding='utf-8') as f:
        json.dump(toybox_list, f, indent=4, ensure_ascii=False)
    
    print("✅ Toybox database updated!")


async def download_file(url: str) -> io.BytesIO:
    if not url:
        return None

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                return io.BytesIO(await response.read())
    return None

@bot.tree.command(name="create_ask_panel", description="ADMIN: Creates the panel to start an AI Toybox chat.")
@app_commands.checks.has_permissions(administrator=True)
async def create_ask_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🦆 Disney Infinity Toybox AI-Chat",
        description=(
            "### Hey there, I'm Donald Duck! 🦆\n"
            "I can help you discover the perfect Toybox from our community collection!\n"
            "\n**🔍 What can I help you find?** \n"
            "Disney, Marvel, Star Wars, Character based or other toyboxes! \n"
        ),
        color=discord.Color.from_rgb(59, 136, 195)
    )
    view = AskToyboxPanelView()
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="clean_threads", description=f"ADMIN: Deletes all threads in the musketeer-donald channel (ID: {TARGET_PURGE_CHANNEL_ID}).")
@app_commands.checks.has_permissions(administrator=True)
async def purge_target_channel_threads(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    if not interaction.guild:
        await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
        return

    target_channel = interaction.guild.get_channel(TARGET_PURGE_CHANNEL_ID)

    if not target_channel:
        await interaction.followup.send(
            f"Error: The predefined target channel (ID: {TARGET_PURGE_CHANNEL_ID}) was not found in this server.",
            ephemeral=True
        )
        return

    if not isinstance(target_channel, (discord.TextChannel, discord.ForumChannel)):
        await interaction.followup.send(
            f"Error: The predefined target channel (ID: {TARGET_PURGE_CHANNEL_ID}) is not a text or forum channel.",
            ephemeral=True
        )
        return

    # Check if the bot has guild-level manage_threads permission
    if not interaction.guild.me.guild_permissions.manage_threads:
        await interaction.followup.send(
            "Error: I don't have the 'Manage Threads' permission at the server level to perform this action.",
            ephemeral=True
        )
        return
    
    # Check bot's permissions in the specific channel
    bot_channel_permissions = target_channel.permissions_for(interaction.guild.me)
    if not bot_channel_permissions.manage_threads:
        await interaction.followup.send(
            f"Error: I don't have the 'Manage Threads' permission in the channel {target_channel.mention} to perform this action.",
            ephemeral=True
        )
        return

    all_threads_map = {}

    # Active threads
    try:
        for thread_obj in target_channel.threads:
            all_threads_map[thread_obj.id] = thread_obj
    except discord.Forbidden:
        await interaction.followup.send(f"Error: I don't have permission to list active threads in {target_channel.mention}.", ephemeral=True)
        return
    except Exception as e:
        await interaction.followup.send(f"An unexpected error occurred while listing active threads: {e}", ephemeral=True)
        return

    # Archived threads
    try:
        async for thread_obj in target_channel.archived_threads(limit=None):
            all_threads_map[thread_obj.id] = thread_obj
    except discord.Forbidden:
        print(f"Permission error: Could not fetch general archived threads for {target_channel.name} ({target_channel.id}).")
    except Exception as e:
        print(f"Error fetching general archived threads for {target_channel.name} ({target_channel.id}): {e}")

    if isinstance(target_channel, discord.TextChannel):
        try:
            async for thread_obj in target_channel.archived_threads(private=True, limit=None):
                 all_threads_map[thread_obj.id] = thread_obj
        except discord.Forbidden:
            print(f"Permission error: Could not fetch private archived threads for TextChannel {target_channel.name} ({target_channel.id}).")
        except Exception as e:
            print(f"Error fetching private archived threads for TextChannel {target_channel.name} ({target_channel.id}): {e}")

    all_threads_list = list(all_threads_map.values())

    if not all_threads_list:
        await interaction.followup.send(f"No threads found in {target_channel.mention} that I can see or manage.", ephemeral=True)
        return

    deleted_count = 0
    failed_count = 0
    
    await interaction.edit_original_response(content=f"Found {len(all_threads_list)} threads in {target_channel.mention}. Starting deletion process... This may take a while.")

    for thread_obj_to_delete in all_threads_list:
        try:
            await thread_obj_to_delete.delete()
            deleted_count += 1
            await asyncio.sleep(0.5) 
        except discord.Forbidden:
            failed_count += 1
            print(f"Permission error: Could not delete thread '{thread_obj_to_delete.name}' ({thread_obj_to_delete.id}).")
        except discord.HTTPException as e:
            failed_count += 1
            print(f"HTTP error: Failed to delete thread '{thread_obj_to_delete.name}' ({thread_obj_to_delete.id}): {e.status} - {e.text}")
        except Exception as e:
            failed_count +=1
            print(f"Generic error: Failed to delete thread '{thread_obj_to_delete.name}' ({thread_obj_to_delete.id}): {type(e).__name__} - {e}")

    result_message = f"Operation complete for {target_channel.mention}:\n"
    result_message += f"Successfully deleted: {deleted_count} threads.\n"
    if failed_count > 0:
        result_message += f"Failed to delete: {failed_count} threads. Check console logs for details."
    
    if len(result_message) > 2000:
        result_message = result_message[:1990] + "... (truncated)"
        
    await interaction.edit_original_response(content=result_message)


@bot.tree.command(name="update_toyboxes", description="ADMIN: Manually update the toybox search database.")
@app_commands.checks.has_permissions(administrator=True)
async def update_toyboxes_cmd(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    # Your update_toybox_database logic here
    # After updating, reload bot.toybox_data
    try:
        with open(toybox_data_file, "r", encoding='utf-8') as f:
            bot.toybox_data = json.load(f)
        await interaction.followup.send(f"✅ Toybox database update complete. ({len(bot.toybox_data)} entries loaded).", ephemeral=True)
    except Exception as e:
        await interaction.followup.send("❌ Toybox database update failed. Check bot logs for details.", ephemeral=True)

@bot.tree.command(name="post", description="Create a forum post from Airtable data")
@discord.app_commands.choices(
    creator=[
        discord.app_commands.Choice(name="Modeltrainman", value="modeltrainman"),
        discord.app_commands.Choice(name="The Bow-Tie Guy", value="bowtieguy"),
        discord.app_commands.Choice(name="Allnightgaming", value="allnightgaming"),
        discord.app_commands.Choice(name="ThatBrownBat", value="thatbrownbat"),
        discord.app_commands.Choice(name="72Pringle", value="72pringle"),
        discord.app_commands.Choice(name="Misc", value="misc"),
        discord.app_commands.Choice(name="JK", value="jk")
    ]
)
async def post(interaction: discord.Interaction, post_id: str, creator: str):
    print(f"Post ID: {post_id}, Creator: {creator}")  # Debugging
    
    await interaction.response.defer()
    
    try:
        # Create initial progress embed
        progress_embed = discord.Embed(
            title="📝 Creating Forum Post",
            description=f"Fetching data for ID: {post_id} from {AIRTABLE_TABLES[creator]} table",
            color=0xec4e4e
        )
        progress_embed.add_field(
            name="Status",
            value="Retrieving data from Airtable...",
            inline=False
        )
        await interaction.followup.send(embed=progress_embed)
        
        # Fetch record from appropriate table
        record = tables[creator].get(post_id)
        if not record:
            error_embed = discord.Embed(
                title="❌ Error",
                description=f"No record found with ID: {post_id} in {AIRTABLE_TABLES[creator]} table",
                color=0xff0000
            )
            await interaction.followup.send(embed=error_embed)
            return

        # Extract fields with default values
        fields = record.get('fields', {})
        title = fields.get('title', 'Untitled Post')
        description = fields.get('description', 'No description provided')
        creator_name = fields.get('creator', 'Unknown')  # Get creator from Airtable
        video_link = fields.get('videolink', '')  # Get videolink from Airtable
        
        # Format the description with creator info and video link from Airtable
        formatted_description = (
            f"{description}\n"
            "-------------------------------------\n"
            f"**:art:⎮Creator: {creator_name}**\n"
            f"**:film_frames:⎮Playthrough video:** {video_link}"
        )

        # Handle file with proper type checking
        file_url = None
        if 'file' in fields and fields['file']:
            files_data = fields['file']
            if isinstance(files_data, list) and files_data and isinstance(files_data[0], dict):
                file_url = files_data[0].get('url')

        # Handle images with proper type checking
        image_files = []
        if 'images' in fields and fields['images']:
            images_data = fields['images']
            if isinstance(images_data, list):
                progress_embed.set_field_at(
                    0,
                    name="Status",
                    value="Downloading images...",
                    inline=False
                )
                await interaction.edit_original_response(embed=progress_embed)
                
                for idx, image in enumerate(images_data):
                    if isinstance(image, dict) and image.get('url'):
                        try:
                            image_url = image['url']
                            image_data = await download_file(image_url)
                            if image_data:
                                filename = image.get('filename', f"image_{idx}.jpg")
                                file = discord.File(image_data, filename=filename)
                                image_files.append(file)
                            else:
                                print(f"Could not download image {idx + 1}: No data received")
                        except Exception as e:
                            print(f"Error downloading image {idx + 1}: {str(e)}")
                            continue

        # Get the forum channel
        forum_channel = bot.get_channel(FORUM_CHANNEL_ID)
        if not forum_channel:
            error_embed = discord.Embed(
                title="❌ Error",
                description="Could not find the forum channel!",
                color=0xff0000
            )
            await interaction.followup.send(embed=error_embed)
            return
        
        # Update progress
        progress_embed.set_field_at(
            0,
            name="Status",
            value="Creating thread with images...",
            inline=False
        )
        await interaction.edit_original_response(embed=progress_embed)
        
        # Create thread with attached images using formatted description
        thread_with_message = await forum_channel.create_thread(
            name=title,
            content=formatted_description,
            files=image_files if image_files else None,
            reason=f"Post created via command by {interaction.user.name}"
        )
        
        if not thread_with_message:
            raise Exception("Failed to create thread")

        # Get the thread and starter message
        thread = thread_with_message.thread
        starter_message = thread_with_message.message
        
        # Post file if any
        if file_url:
            progress_embed.set_field_at(
                0,
                name="Status",
                value="Uploading attachment...",
                inline=False
            )
            await interaction.edit_original_response(embed=progress_embed)
            
            try:
                file_data = await download_file(file_url)
                if file_data:
                    filename = fields['file'][0].get('filename', 'attachment.file')
                    file = discord.File(file_data, filename=filename)
                    rating_message = await thread.send(
                        content="**:arrow_down: ⎮DOWNLOAD:**",
                        file=file
                    )

                    # Create rating message
                    if rating_message:
                        message = await thread.send("<:EmojiName:741403450314850465>")
                        if message:
                            message_id = message.id

                            # Initialize rating for this message
                            message_ratings[message_id] = {
                                'ratings': {},
                                'average': 0,
                                'num_ratings': 0,
                                'channel_id': thread.id
                            }

                            # Create and send rating embed
                            embed = discord.Embed(
                                title="Toybox rating: ⭐️⭐️⭐️⭐️⭐️",
                                description="What do you think about this toybox?",
                                color=discord.Color.blue()
                            )
                            embed.add_field(name="Average rating", value="No ratings yet.", inline=False)
                            embed.add_field(name="Number of ratings", value="0 ratings yet.", inline=False)

                            await message.edit(embed=embed, view=RatingView(message_id))
                            
                            # Save the channel title for the rating system
                            channel_titles[message_id] = thread.name
                            save_ratings()
            except Exception as e:
                print(f"Error uploading file: {str(e)}")
                await thread.send("⚠️ Failed to upload attachment file")

        # Update the Airtable record's Status to 'Published'
        try:
            tables[creator].update(post_id, {'Status': 'Published'})
            status_updated = True
        except Exception as e:
            print(f"Error updating Airtable status: {str(e)}")
            status_updated = False

        # Create success embed
        success_embed = discord.Embed(
            title="✅ Toybox published",
            description=f"Successfully published the toybox {post_id} from {AIRTABLE_TABLES[creator]}",
            color=0x00ff00
        )
        success_embed.add_field(
            name="Post",
            value=f"[Click to view]({starter_message.jump_url})",
            inline=False
        )
        success_embed.add_field(
            name="Images Uploaded",
            value=f"{len(image_files)} image(s) successfully uploaded.",
            inline=False
        )
        success_embed.add_field(
            name="Status Updated",
            value="Status set to **Published** in Airtable." if status_updated else "Failed to update status in Airtable",
            inline=False
        )

        await interaction.edit_original_response(embed=success_embed)
        
    except Exception as e:
        print(f"Error details: {str(e)}")  # Add detailed error logging
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"An error occurred: {str(e)}",
            color=0xff0000
        )
        await interaction.followup.send(embed=error_embed)

@bot.tree.command(name="brownbat_mod", description="Get download link for ThatBrownBat's Mod")
@discord.app_commands.describe(version="The version number (e.g., 1.0, 1.1)")
async def brownbat(interaction: discord.Interaction, version: str):
    embed = discord.Embed(
        title="Brown Bat Mod Download",
        description="Welcome to Brown Bat Mod!\nDownload the expansion mod now! 🥳",
        color=0x8C142E
    )
    
    embed.set_footer(text=f"Made by That Brown Bat (v{version})")
    
    await interaction.response.send_message(
        embed=embed,
        view=BrownbatDownloadView()
    )


@bot.tree.command(name="change_metadata", description="Modifies metadata files by uploading a ZIP file")
async def change_metadata(interaction: discord.Interaction, file: discord.Attachment):
    # 1. Defer interaction to allow time for processing
    await interaction.response.defer(ephemeral=False) # ephemeral=False, so the message is visible to everyone

    # 2. Create initial embed
    embed = discord.Embed(
        title="🔄 Modifying Metadata",
        description=f"Processing your ZIP file: `{file.filename}`...",
        color=discord.Color.blue() # A neutral color to start
    )
    embed.add_field(name="Progress", value="Initializing...", inline=False)
    
    # Send the initial embed and store the message for later edits
    progress_message = await interaction.followup.send(embed=embed)

    # Helper function to update the embed
    async def update_embed(status_text: str, title: str = None, description: str = None, color: discord.Color = None, attachment_to_send: discord.File = None, clear_fields: bool = False):
        if title:
            embed.title = title
        if description is not None: # Allow empty descriptions to clear them
            embed.description = description
        if color:
            embed.color = color
        
        if clear_fields:
            embed.clear_fields()
            # If fields were cleared but a new status is present, re-add the progress field
            if status_text:
                 embed.add_field(name="Progress", value=status_text, inline=False)
        elif embed.fields: # Only update if fields exist
            embed.set_field_at(0, name="Progress", value=status_text, inline=False)
        else: # If no fields exist (e.g., after clear_fields without new status_text)
            embed.add_field(name="Progress", value=status_text, inline=False)
            
        attachments_list = [attachment_to_send] if attachment_to_send else discord.utils.MISSING
        await progress_message.edit(embed=embed, attachments=attachments_list)

    # 3. File validation
    if not file or not file.filename.endswith('.zip'):
        await update_embed(
            status_text="Upload Error.",
            title="❌ Error",
            description="Please ensure you are uploading a `.zip` file.",
            color=discord.Color.red()
        )
        return

    try:
        # 4. Create temporary directory for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            zip_path = os.path.join(temp_dir, file.filename)
            
            await update_embed(status_text=f"📥 Downloading `{file.filename}`...")
            await file.save(zip_path)
            
            extract_dir = os.path.join(temp_dir, "extracted_files")
            os.makedirs(extract_dir, exist_ok=True)
            await update_embed(status_text=f"🗂️ Extracting `{file.filename}`...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            # Find metadata files
            target_folder = None
            metadata_files = []
            # Regex pattern for metadata filenames
            pattern = re.compile(r'^(EHRR|ERR|SCRR|SHRR|SRR)\d+[a-zA-Z]*$')
            
            await update_embed(status_text="🔎 Searching for metadata files...")
            for root, dirs, files_in_root in os.walk(extract_dir):
                found_files = [f for f in files_in_root if pattern.match(f)]
                if found_files:
                    metadata_files = found_files
                    target_folder = root # The folder where the files were found
                    break # Stop as soon as the first folder with matching files is found
            
            if not target_folder:
                await update_embed(
                    status_text="No folder containing metadata files found.",
                    title="❌ Error",
                    description="Could not find a folder containing metadata files (EHRR, ERR, etc.).",
                    color=discord.Color.red()
                )
                return
                
            if not metadata_files:
                await update_embed(
                    status_text="No metadata files found.",
                    title="❌ Error",
                    description="No metadata files (EHRR, ERR, SCRR, SHRR, SRR) found in the ZIP file.",
                    color=discord.Color.red()
                )
                return
            
            # Select EHRR file or the first found file
            ehrr_files = [f for f in metadata_files if f.startswith("EHRR")]
            target_file_name = ehrr_files[0] if ehrr_files else metadata_files[0]
            
            await update_embed(
                status_text=f"🎯 Target file: `{target_file_name}`.\nFound files: `{', '.join(metadata_files)}`"
            )
            
            input_file_path = os.path.join(target_folder, target_file_name)
            decoded_output_file_name = f"{target_file_name}.dec"
            decoded_output_file_path = os.path.join(target_folder, decoded_output_file_name)
            
            # Path to the inflate.py script (assuming it's in the same directory as the bot script)
            script_dir = os.path.dirname(os.path.abspath(__file__))
            inflate_script_path = os.path.join(script_dir, "inflate.py")

            if not os.path.exists(inflate_script_path):
                await update_embed("Internal error.", title="❌ Script Not Found", description=f"The script `inflate.py` was not found at: `{inflate_script_path}`", color=discord.Color.red())
                return

            # Decompress file with inflate.py
            await update_embed(status_text=f"⚙️ Decompressing `{target_file_name}`...")
            decompress_process = subprocess.run(
                ["python3", inflate_script_path, "-d", input_file_path, decoded_output_file_path],
                capture_output=True, text=True, check=False # check=False to handle errors manually
            )

            if decompress_process.returncode != 0:
                await update_embed("Decompression error.", title="❌ Processing Error", description=f"Error executing inflate.py (decompress):\n```\n{decompress_process.stderr or decompress_process.stdout}\n```", color=discord.Color.red())
                return
            
            # Send the decompressed file to the user in a NEW message
            # The embed cannot directly attach a file for an intermediate step and then be further edited.
            await update_embed(
                status_text=f"📤 `{decoded_output_file_name}` sent.",
                description=(
                    f"The file `{target_file_name}` has been decompressed to `{decoded_output_file_name}`.\n"
                    "**Please edit the `.dec` file and then upload it here in this channel.**"
                )
            )
            dec_file_message = await interaction.channel.send(
                content=f"Here is the decompressed file (`{decoded_output_file_name}`) for editing:",
                file=discord.File(decoded_output_file_path)
            )
            
            # Wait for the user to upload the edited file
            def check_modified_file(message_from_user: discord.Message):
                return (message_from_user.author == interaction.user and 
                        message_from_user.channel == interaction.channel and
                        message_from_user.attachments and 
                        message_from_user.attachments[0].filename.endswith('.dec')) # Ensure it's a .dec file

            try:
                await update_embed(
                    status_text=f"⏳ Waiting for upload of the edited `{decoded_output_file_name}` (Timeout: 10 minutes)...",
                    description= ( # Repeat the instruction in case the user scrolls up
                        f"Please upload the edited version of `{decoded_output_file_name}` now."
                    )
                )
                modified_message = await bot.wait_for('message', check=check_modified_file, timeout=600.0) # 10 minute timeout
                modified_attachment = modified_message.attachments[0]
                modified_file_temp_path = os.path.join(temp_dir, modified_attachment.filename) # Secure temporary path
                await modified_attachment.save(modified_file_temp_path)
                
                await update_embed(status_text=f"📥 Edited file `{modified_attachment.filename}` received.")

                # Optional: Clean up old messages
                try:
                    await dec_file_message.delete()
                    await modified_message.delete()
                except discord.HTTPException:
                    pass # Ignore errors if messages are already gone or permissions are missing

            except asyncio.TimeoutError:
                await update_embed(
                    status_text="Time expired.",
                    title="⏰ Timeout",
                    description="The time for uploading the edited file has expired.",
                    color=discord.Color.orange()
                )
                return
            
            # Remove the old (uncompressed) .dec file and the original compressed file
            if os.path.exists(decoded_output_file_path):
                 os.remove(decoded_output_file_path)
            if os.path.exists(input_file_path):
                os.remove(input_file_path)
            
            # Compress the modified file back to the original target file location
            # The name of the compressed file should be `target_file_name` again
            compressed_output_path = os.path.join(target_folder, target_file_name)
            await update_embed(status_text=f"⚙️ Compressing `{modified_attachment.filename}` to `{target_file_name}`...")
            compress_process = subprocess.run(
                ["python3", inflate_script_path, "-c", modified_file_temp_path, compressed_output_path],
                capture_output=True, text=True, check=False
            )

            if compress_process.returncode != 0:
                await update_embed("Compression error.", title="❌ Processing Error", description=f"Error executing inflate.py (compress):\n```\n{compress_process.stderr or compress_process.stdout}\n```", color=discord.Color.red())
                return
            
            # Create a new ZIP file with the modified contents
            modified_zip_filename = f"modified_{file.filename}"
            modified_zip_path = os.path.join(temp_dir, modified_zip_filename)
            
            await update_embed(status_text=f"🤐 Creating new ZIP file `{modified_zip_filename}`...")
            with zipfile.ZipFile(modified_zip_path, 'w', zipfile.ZIP_DEFLATED) as new_zip:
                # Traverse `extract_dir` (not `target_folder`) to maintain the original structure
                for root, dirs, files_in_root in os.walk(extract_dir):
                    for item_name in files_in_root:
                        # Skip temporary .dec files that were not part of the original ZIP
                        if item_name.endswith('.dec') and item_name != decoded_output_file_name : # Don't keep the .dec file just processed
                             if item_name == os.path.basename(modified_file_temp_path): # Also not the uploaded .dec
                                 continue
                        
                        item_path = os.path.join(root, item_name)
                        # arcname is the path inside the ZIP file
                        arcname = os.path.relpath(item_path, extract_dir)
                        new_zip.write(item_path, arcname)
            
            # Send the modified ZIP file back
            final_zip_file = discord.File(modified_zip_path, filename=modified_zip_filename)
            await update_embed(
                status_text="Completed!",
                title="✅ Done!",
                description=f"Here is your modified ZIP file `{modified_zip_filename}`.",
                color=discord.Color.green(),
                attachment_to_send=final_zip_file,
                clear_fields=True # Removes the "Progress" field for the final message
            )

    except subprocess.CalledProcessError as e:
        error_details = f"Exit Code: {e.returncode}\nStdout: {e.stdout}\nStderr: {e.stderr}"
        await update_embed("Error during external script execution.", title="❌ System Error", description=f"Error processing with an external script:\n```\n{error_details}\n```", color=discord.Color.red())
    except FileNotFoundError as e: # Catches e.g., if python3 is not found
        await update_embed("File or program not found.", title="❌ System Error", description=f"A required program or file was not found: {e}", color=discord.Color.red())
    except Exception as e:
        import traceback
        trace_str = traceback.format_exc()
        print(f"An unexpected error occurred in the 'change_metadata' command:\n{trace_str}")
        await update_embed(
            status_text="An unexpected error occurred.",
            title="❌ Unexpected Error",
            description=f"An internal error occurred. The bot administrator has been notified.\nError type: `{type(e).__name__}`",
            color=discord.Color.dark_red()
        )
    finally:
        # Temp directory is automatically deleted by the 'with' statement
        pass











@bot.tree.command(name="breeze", description="Get download links for Breeze")
@discord.app_commands.describe(version="The version number (e.g., 1.0, 1.1)")
async def breeze(interaction: discord.Interaction, version: str):
    embed = discord.Embed(
        title="Breeze Download",
        description="Welcome to Breeze!\nDownload the expansion mod now! 🥳",
        color=0x148C6A
    )
    
    embed.set_footer(text=f"Made by Cassinni (v{version})")
    
    await interaction.response.send_message(
        embed=embed,
        view=BreezeDownloadView()
    )

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("360_to_pc_converter")

@bot.tree.command(name="360_to_pc", description="Convert Xbox 360 format files to PC format")
@app_commands.describe(file="Upload a zip file containing Xbox 360 format files to convert")
async def convert_360_to_pc(interaction: discord.Interaction, file: discord.Attachment):
    """
    Command to convert Xbox 360 format files to PC format.
    Accepts a zip file upload, processes files using 360toPC.py, and returns converted files as a zip.
    """
    # Defer the response since this might take some time
    await interaction.response.defer()

    # Check if file is provided
    if not file:
        return await interaction.followup.send("Please attach a zip file to convert.")

    # Check file extension
    if not file.filename.lower().endswith('.zip'):
        return await interaction.followup.send("Please upload a .zip file.")

    # Check file size (10MB limit)
    if file.size > 10 * 1024 * 1024:
        return await interaction.followup.send("File too large. Please upload a zip file smaller than 10MB.")
        
    original_filename = file.filename  # Store the original filename for later use

    # Create a temporary working directory
    with tempfile.TemporaryDirectory() as temp_dir:
        # Define paths
        input_zip_path = os.path.join(temp_dir, "input.zip")
        extract_dir = os.path.join(temp_dir, "extracted")
        output_zip_path = os.path.join(temp_dir, "converted.zip")
        
        os.makedirs(extract_dir, exist_ok=True)
        
        # Download the zip file
        try:
            zip_content = await file.read()
            with open(input_zip_path, 'wb') as f:
                f.write(zip_content)
            logger.info(f"Downloaded file: {file.filename}, size: {file.size} bytes")
            await interaction.followup.send(f"Processing file: {file.filename}", ephemeral=True)
        except Exception as e:
            logger.error(f"Error downloading the file: {str(e)}")
            return await interaction.followup.send(f"Error downloading the file: {str(e)}")
        
        # Extract the zip file
        try:
            with zipfile.ZipFile(input_zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
        except Exception as e:
            return await interaction.followup.send(f"Error extracting the zip file: {str(e)}")
        
        # Look for files matching the pattern in the extracted directory
        rr_files_exist = False
        for root, _, files in os.walk(extract_dir):
            for file in files:
                if "RR" in file:
                    rr_files_exist = True
                    break
            if rr_files_exist:
                break
        
        if not rr_files_exist:
            return await interaction.followup.send("No matching files found in the zip. Looking for files containing 'RR' in the name.")
        
        # Find the actual directory containing the files
        # This handles the case where zip contains a folder containing the files
        original_dir = os.getcwd()
        target_dir = extract_dir
        
        # Check if there's a single directory in the extracted content
        contents = os.listdir(extract_dir)
        if len(contents) == 1 and os.path.isdir(os.path.join(extract_dir, contents[0])):
            target_dir = os.path.join(extract_dir, contents[0])
            await interaction.followup.send(f"Found nested folder: {contents[0]}", ephemeral=True)
        
        try:
            # Copy the script to the target directory
            script_path = os.path.join(original_dir, "360toPC.py")
            target_script_path = os.path.join(target_dir, "360toPC.py")
            shutil.copy2(script_path, target_script_path)
            
            # Change to the target directory and run the script
            os.chdir(target_dir)
            
            # List files before conversion
            files_before = os.listdir(target_dir)
            matching_files = [f for f in files_before if "RR" in f]
            
            if not matching_files:
                os.chdir(original_dir)
                return await interaction.followup.send(f"No matching *RR* files found in the directory. Found these files instead: {', '.join(files_before[:10])}")
                
            # Run the conversion script
            await interaction.followup.send(f"Found {len(matching_files)} files to convert. Processing...", ephemeral=True)
            
            process = await asyncio.create_subprocess_exec(
                "python3", target_script_path, "*RR*", "*RR*",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                os.chdir(original_dir)
                return await interaction.followup.send(f"Error running the conversion script: {stderr.decode()}")
                
            # Change back to original directory
            os.chdir(original_dir)
            
            # Check if the converted_files directory was created
            # It will be in the target directory, not necessarily directly in extract_dir
            converted_dir = os.path.join(target_dir, "converted_files")
            if not os.path.exists(converted_dir) or not os.listdir(converted_dir):
                return await interaction.followup.send("Conversion process didn't produce any files. Please check if the uploaded files match the expected format.")
            
            # Create a new zip file with the converted files
            with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_out:
                for root, _, files in os.walk(converted_dir):
                    for file_name in files:
                        file_path = os.path.join(root, file_name)
                        arcname = os.path.relpath(file_path, converted_dir)
                        zip_out.write(file_path, arcname)
            
            # Count converted files
            converted_file_count = sum(len(files) for _, _, files in os.walk(converted_dir))
            
            # Send the zip file back to the user
            with open(output_zip_path, 'rb') as f:
                output_file = discord.File(fp=io.BytesIO(f.read()), filename=f"converted_{original_filename}")
                await interaction.followup.send(
                    content=f"✅ Files converted successfully! Converted {converted_file_count} files. Here's your converted zip file:",
                    file=output_file
                )
                
            logger.info(f"Successfully converted {converted_file_count} files for {interaction.user.name}")
                
        except Exception as e:
            if os.getcwd() != original_dir:
                os.chdir(original_dir)
            await interaction.followup.send(f"An error occurred during conversion: {str(e)}")


# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wiiu_to_pc_converter")

@bot.tree.command(name="wiiu_to_pc_converter", description="Convert wii u format files to PC format")
@app_commands.describe(file="Upload a zip file containing wii u format files to convert")
async def convert_360_to_pc(interaction: discord.Interaction, file: discord.Attachment):
    """
    Command to convert wii u format files to PC format.
    Accepts a zip file upload, processes files using 360toPC.py, and returns converted files as a zip.
    """
    # Defer the response since this might take some time
    await interaction.response.defer()

    # Check if file is provided
    if not file:
        return await interaction.followup.send("Please attach a zip file to convert.")

    # Check file extension
    if not file.filename.lower().endswith('.zip'):
        return await interaction.followup.send("Please upload a .zip file.")

    # Check file size (10MB limit)
    if file.size > 10 * 1024 * 1024:
        return await interaction.followup.send("File too large. Please upload a zip file smaller than 10MB.")
        
    original_filename = file.filename  # Store the original filename for later use

    # Create a temporary working directory
    with tempfile.TemporaryDirectory() as temp_dir:
        # Define paths
        input_zip_path = os.path.join(temp_dir, "input.zip")
        extract_dir = os.path.join(temp_dir, "extracted")
        output_zip_path = os.path.join(temp_dir, "converted.zip")
        
        os.makedirs(extract_dir, exist_ok=True)
        
        # Download the zip file
        try:
            zip_content = await file.read()
            with open(input_zip_path, 'wb') as f:
                f.write(zip_content)
            logger.info(f"Downloaded file: {file.filename}, size: {file.size} bytes")
            await interaction.followup.send(f"Processing file: {file.filename}", ephemeral=True)
        except Exception as e:
            logger.error(f"Error downloading the file: {str(e)}")
            return await interaction.followup.send(f"Error downloading the file: {str(e)}")
        
        # Extract the zip file
        try:
            with zipfile.ZipFile(input_zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
        except Exception as e:
            return await interaction.followup.send(f"Error extracting the zip file: {str(e)}")
        
        # Look for files matching the pattern in the extracted directory
        rr_files_exist = False
        for root, _, files in os.walk(extract_dir):
            for file in files:
                if "RR" in file:
                    rr_files_exist = True
                    break
            if rr_files_exist:
                break
        
        if not rr_files_exist:
            return await interaction.followup.send("No matching files found in the zip. Looking for files containing 'RR' in the name.")
        
        # Find the actual directory containing the files
        # This handles the case where zip contains a folder containing the files
        original_dir = os.getcwd()
        target_dir = extract_dir
        
        # Check if there's a single directory in the extracted content
        contents = os.listdir(extract_dir)
        if len(contents) == 1 and os.path.isdir(os.path.join(extract_dir, contents[0])):
            target_dir = os.path.join(extract_dir, contents[0])
            await interaction.followup.send(f"Found nested folder: {contents[0]}", ephemeral=True)
        
        try:
            # Copy the script to the target directory
            script_path = os.path.join(original_dir, "360toPC.py")
            target_script_path = os.path.join(target_dir, "360toPC.py")
            shutil.copy2(script_path, target_script_path)
            
            # Change to the target directory and run the script
            os.chdir(target_dir)
            
            # List files before conversion
            files_before = os.listdir(target_dir)
            matching_files = [f for f in files_before if "RR" in f]
            
            if not matching_files:
                os.chdir(original_dir)
                return await interaction.followup.send(f"No matching *RR* files found in the directory. Found these files instead: {', '.join(files_before[:10])}")
                
            # Run the conversion script
            await interaction.followup.send(f"Found {len(matching_files)} files to convert. Processing...", ephemeral=True)
            
            process = await asyncio.create_subprocess_exec(
                "python3", target_script_path, "*RR*", "*RR*",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                os.chdir(original_dir)
                return await interaction.followup.send(f"Error running the conversion script: {stderr.decode()}")
                
            # Change back to original directory
            os.chdir(original_dir)
            
            # Check if the converted_files directory was created
            # It will be in the target directory, not necessarily directly in extract_dir
            converted_dir = os.path.join(target_dir, "converted_files")
            if not os.path.exists(converted_dir) or not os.listdir(converted_dir):
                return await interaction.followup.send("Conversion process didn't produce any files. Please check if the uploaded files match the expected format.")
            
            # Create a new zip file with the converted files
            with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_out:
                for root, _, files in os.walk(converted_dir):
                    for file_name in files:
                        file_path = os.path.join(root, file_name)
                        arcname = os.path.relpath(file_path, converted_dir)
                        zip_out.write(file_path, arcname)
            
            # Count converted files
            converted_file_count = sum(len(files) for _, _, files in os.walk(converted_dir))
            
            # Send the zip file back to the user
            with open(output_zip_path, 'rb') as f:
                output_file = discord.File(fp=io.BytesIO(f.read()), filename=f"converted_{original_filename}")
                await interaction.followup.send(
                    content=f"✅ Files converted successfully! Converted {converted_file_count} files. Here's your converted zip file:",
                    file=output_file
                )
                
            logger.info(f"Successfully converted {converted_file_count} files for {interaction.user.name}")
                
        except Exception as e:
            if os.getcwd() != original_dir:
                os.chdir(original_dir)
            await interaction.followup.send(f"An error occurred during conversion: {str(e)}")


@bot.tree.command(name="breeze_video", description="Posts a Breeze video link")
@app_commands.choices(video_type=[
    app_commands.Choice(name="Guide Tutorial", value="guide"),
    app_commands.Choice(name="Error Help", value="error")
])
async def breeze_video(interaction: discord.Interaction, video_type: app_commands.Choice[str]):
    # Set video details based on the selected option
    if video_type.value == "guide":
        video_link = "https://youtu.be/xlXahV_enMo?si=4rngyfHSy4tPLyfx"
        title = "Breeze Guide Video"
    else:  # error video
        video_link = "https://www.youtube.com/watch?v=uU__wdl3HVg"
        title = "Breeze Help Video"
    
    # Creating a cleaner, simpler embed
    embed = discord.Embed(
        title=title,
        url=video_link,  # Makes the title itself clickable
        color=0x148C6A
    )
    
    # Add a footer with a hint
    embed.set_footer(text="Click the title to watch the video")
    
    await interaction.response.send_message(embed=embed)





@bot.tree.command(name="playstation_links", description="Zeigt Download-Links für PlayStation Savefiles an.")
async def playstation_links(interaction: discord.Interaction):
    # Erstelle ein Embed für eine schönere und übersichtlichere Darstellung
    embed = discord.Embed(
        title="LiontHD PlayStation Savefiles",
        description=(
            "Hier sind die nützlichen Links für die PlayStation Savefiles von LiontHD:\n\n"
            "**LiontHD (EU) - Savefile (0% Progress):**\n"
            "[Hier klicken zum Herunterladen](https://drive.google.com/drive/folders/1bqeV_Bz_Ybsu3wMH4KsyqNqtFcM4n4Ta?usp=sharing)\n\n"
            "**LiontHD (EU) - Savefile (100% Progress):**\n"
            "[Hier klicken zum Herunterladen](https://drive.google.com/drive/folders/1vptZ4pkA9FqWE9tzcE4TQSHE2j2GwfGs?usp=sharing)\n\n"
            "**LiontHD (EU) - Entschlüsseltes Savefile (savedata0 Ordner):**\n"
            "[Hier klicken zum Herunterladen](https://drive.google.com/drive/folders/1GwH8zwBTx_37kaJsADPy2wqRG_U7famw?usp=sharing)"
        ),
        color=discord.Color.blue() # Ein passendes Blau für PlayStation
    )
    embed.set_footer(text="Diese Links sind für die EU-Version der PlayStation.")

    # Sende das Embed als Antwort. 'ephemeral=True' sorgt dafür, dass die Nachricht nur für den Nutzer sichtbar ist, der den Befehl ausgeführt hat.
    await interaction.response.send_message(embed=embed, ephemeral=True)





@bot.tree.command(
    name="count_publish",
    description="Start counting toyboxes from ZIP files"
)
async def count_publish(interaction: discord.Interaction):
    user_id = interaction.user.id
    counter.counting_sessions[user_id] = []
    
    # Create initial progress embed
    progress_embed = discord.Embed(
        title="📊 Toybox Counting Session",
        description="Upload ZIP files to count toyboxes.\nCurrent progress will be shown here.",
        color=0xec4e4e
    )
    progress_embed.add_field(
        name="Status",
        value="Waiting for files...",
        inline=False
    )
    
    # Send initial message and store its reference
    await interaction.response.send_message(embed=progress_embed, view=CountingView(counter, user_id, None))
    original_message = await interaction.original_response()
    counter.progress_messages[user_id] = original_message

@bot.tree.command(
    name="json", 
    description="Send the specified JSON file(s)"
)
@app_commands.choices(file_type=[
    app_commands.Choice(name="All Files", value="all"),
    app_commands.Choice(name="Ratings", value="ratings"),
    app_commands.Choice(name="Toybox Data", value="toybox"),
    app_commands.Choice(name="Blacklisted Threads", value="blacklist")
])
async def send_json(interaction: discord.Interaction, file_type: app_commands.Choice[str]):
    # Define file paths
    files = {
        "ratings": "ratings.json",
        "toybox": "toybox_data.json",
        "blacklist": "blacklisted_threads.json"
    }
    
    try:
        if file_type.value == "all":
            # Create list to store existing files
            file_attachments = []
            missing_files = []
            
            # Check each file
            for file_path in files.values():
                if os.path.exists(file_path):
                    file_attachments.append(discord.File(file_path))
                else:
                    missing_files.append(file_path)
            
            if file_attachments:
                # Send existing files
                message = "Here are the current JSON files:"
                if missing_files:
                    message += f"\n⚠️ Note: Could not find: {', '.join(missing_files)}"
                await interaction.response.send_message(message, files=file_attachments)
            else:
                await interaction.response.send_message("❌ No JSON files found.", ephemeral=True)
                
        else:
            # Handle single file request
            file_path = files[file_type.value]
            
            if os.path.exists(file_path):
                await interaction.response.send_message(
                    f"Here is the current `{file_path}` file:",
                    file=discord.File(file_path)
                )
            else:
                await interaction.response.send_message(
                    f"❌ The `{file_path}` file does not exist.",
                    ephemeral=True
                )
                
    except Exception as e:
        await interaction.response.send_message(
            f"❌ An error occurred: {str(e)}",
            ephemeral=True
        )

# Fügt den Befehl /user hinzu, um Bewertungen für eine bestimmte Nachricht anzuzeigen
@bot.tree.command(name="user", description="List all user ratings for a specific message.")
async def user_ratings(interaction: discord.Interaction, message_id: str):
    # Überprüfe, ob die Nachricht existiert und Bewertungen hat
    if message_id not in message_ratings or not message_ratings[message_id]['ratings']:
        await interaction.response.send_message(f"No ratings available for message ID {message_id}.", ephemeral=True)
        return

    # Lade die Bewertungen für die Nachricht
    user_ratings_list = message_ratings[message_id]['ratings']
    
    # Erstelle eine Liste von Nutzern und ihren Bewertungen
    rating_output = []
    for user_id, rating in user_ratings_list.items():
        # Erstelle eine Erwähnung für den Benutzer (Ping)
        user_mention = f"<@{user_id}>"  # Ping den Benutzer mit seiner ID
        rating_output.append(f"{user_mention}: {rating} ⭐️")
    
    # Formatiere die Ausgabe
    ratings_message = "\n".join(rating_output)
    
    # Sende die Nachricht mit den Bewertungen, nur für den Benutzer sichtbar
    await interaction.response.send_message(f"Ratings for message ID {message_id}:\n{ratings_message}", ephemeral=True)
    

# Befehl edit
@bot.tree.command(name="edit", description="Edit ratings for a specific message.")
async def edit_ratings(interaction: discord.Interaction, message_id: str, user_to_remove: str):
    # Überprüfe, ob die Nachricht existiert und Bewertungen hat
    if message_id not in message_ratings or not message_ratings[message_id]['ratings']:
        await interaction.response.send_message(f"No ratings available for message ID {message_id}.", ephemeral=True)
        return

    # Konvertiere die User-ID, die entfernt werden soll, in einen Integer
    try:
        user_to_remove = int(user_to_remove)
    except ValueError:
        await interaction.response.send_message(f"Invalid user ID: {user_to_remove}", ephemeral=True)
        return

    # Liste der Benutzerbewertungen für die Nachricht abrufen
    user_ratings_list = message_ratings[message_id]['ratings']

    # Debugging: Ausgabe aller Benutzer, die abgestimmt haben
    print(f"Existing user ratings (user IDs as keys): {list(user_ratings_list.keys())}")
    print(f"User ID type: {type(user_to_remove)}")
    print(f"Trying to remove user: {user_to_remove}")

    # Überprüfe, ob der Nutzer in den Bewertungen existiert
    if user_to_remove in user_ratings_list:
        # Benutzer aus der Bewertungsliste entfernen
        del message_ratings[message_id]['ratings'][user_to_remove]
        message_ratings[message_id]['num_ratings'] -= 1

        # Durchschnittliche Bewertung aktualisieren
        ratings = list(message_ratings[message_id]['ratings'].values())
        if ratings:
            new_average = sum(ratings) / len(ratings)
        else:
            new_average = 0  # Setze die durchschnittliche Bewertung auf 0, wenn keine Bewertungen mehr vorhanden sind
        message_ratings[message_id]['average'] = new_average

        # Bewertungen speichern
        save_ratings()

        # Bestätigung der Entfernung und ping den Benutzer
        await interaction.response.send_message(f"Removed user <@{user_to_remove}> from the ratings.", ephemeral=True)

        # Nachricht mit aktualisierten Bewertungen abrufen und das Panel aktualisieren
        try:
            message = await interaction.channel.fetch_message(message_id)
            await update_rating_embed(message, message_id)
        except discord.NotFound:
            await interaction.response.send_message(f"Message ID {message_id} not found.", ephemeral=True)
    else:
        # Zusätzliche Debug-Informationen bei einem Fehler
        print(f"User {user_to_remove} not found in ratings.")
        print(f"Available user IDs in ratings: {list(user_ratings_list.keys())}")

        # Wenn der Benutzer nicht in der Liste ist, sende eine Fehlermeldung
        await interaction.response.send_message(f"User ID <@{user_to_remove}> has not voted on this message.", ephemeral=True)

def calculate_wilson_score(avg_rating, num_ratings, confidence=1.96):
    if num_ratings == 0:
        return 0
    z = confidence
    phat = (avg_rating - 1) / 4  # Umwandlung von Bewertung auf eine Skala von 0 bis 1
    return (phat + z**2 / (2 * num_ratings) - z * math.sqrt((phat * (1 - phat) + z**2 / (4 * num_ratings)) / num_ratings)) / (1 + z**2 / num_ratings)

# Befehl zum Top rated
@bot.tree.command(name="list", description="Show the top 100 toyboxes based on ratings.")
async def list_top_toyboxes(interaction: discord.Interaction):
    if not message_ratings:
        await interaction.response.send_message("No toyboxes have been rated yet.")
        return

    top_100 = []
    for msg_id, data in message_ratings.items():
        if 'ratings' in data and data['ratings']:
            avg_rating = data['average']
            num_ratings = data['num_ratings']
            title = channel_titles.get(msg_id, "Unknown Toybox")
            score = calculate_wilson_score(avg_rating, num_ratings)
            top_100.append((msg_id, score, avg_rating, num_ratings, title))

    # Sortiere basierend auf dem Wilson-Score und beschränke auf die Top 100
    top_100 = sorted(top_100, key=lambda x: x[1], reverse=True)[:100]

    # Emojis für die Rangnummerierung
    number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟",
                     "1️⃣1️⃣", "1️⃣2️⃣", "1️⃣3️⃣", "1️⃣4️⃣", "1️⃣5️⃣", "1️⃣6️⃣", "1️⃣7️⃣", "1️⃣8️⃣", "1️⃣9️⃣", "2️⃣0️⃣",
                     "2️⃣1️⃣", "2️⃣2️⃣", "2️⃣3️⃣", "2️⃣4️⃣", "2️⃣5️⃣", "2️⃣6️⃣", "2️⃣7️⃣", "2️⃣8️⃣", "2️⃣9️⃣", "3️⃣0️⃣",
                     "3️⃣1️⃣", "3️⃣2️⃣", "3️⃣3️⃣", "3️⃣4️⃣", "3️⃣5️⃣", "3️⃣6️⃣", "3️⃣7️⃣", "3️⃣8️⃣", "3️⃣9️⃣", "4️⃣0️⃣",
                     "4️⃣1️⃣", "4️⃣2️⃣", "4️⃣3️⃣", "4️⃣4️⃣", "4️⃣5️⃣", "4️⃣6️⃣", "4️⃣7️⃣", "4️⃣8️⃣", "4️⃣9️⃣", "5️⃣0️⃣",
                     "5️⃣1️⃣", "5️⃣2️⃣", "5️⃣3️⃣", "5️⃣4️⃣", "5️⃣5️⃣", "5️⃣6️⃣", "5️⃣7️⃣", "5️⃣8️⃣", "5️⃣9️⃣", "6️⃣0️⃣",
                     "6️⃣1️⃣", "6️⃣2️⃣", "6️⃣3️⃣", "6️⃣4️⃣", "6️⃣5️⃣", "6️⃣6️⃣", "6️⃣7️⃣", "6️⃣8️⃣", "6️⃣9️⃣", "7️⃣0️⃣",
                     "7️⃣1️⃣", "7️⃣2️⃣", "7️⃣3️⃣", "7️⃣4️⃣", "7️⃣5️⃣", "7️⃣6️⃣", "7️⃣7️⃣", "7️⃣8️⃣", "7️⃣9️⃣", "8️⃣0️⃣",
                     "8️⃣1️⃣", "8️⃣2️⃣", "8️⃣3️⃣", "8️⃣4️⃣", "8️⃣5️⃣", "8️⃣6️⃣", "8️⃣7️⃣", "8️⃣8️⃣", "8️⃣9️⃣", "9️⃣0️⃣",
                     "9️⃣1️⃣", "9️⃣2️⃣", "9️⃣3️⃣", "9️⃣4️⃣", "9️⃣5️⃣", "9️⃣6️⃣", "9️⃣7️⃣", "9️⃣8️⃣", "9️⃣9️⃣", "💯"]

    # Aufteilen in mehrere Embeds, falls mehr als 25 Einträge
    embeds = []
    for chunk_start in range(0, len(top_100), 25):
        embed = discord.Embed(title="⭐️ TOP 100 TOYBOXES ⭐️", color=discord.Color.gold())
        for i, (msg_id, score, avg_rating, num_ratings, title) in enumerate(top_100[chunk_start:chunk_start + 25], start=chunk_start):
            ranking_text = f"{avg_rating:.2f} ⭐️ ({num_ratings} ratings)"
            embed.add_field(name=f"{number_emojis[i]} {title}", value=ranking_text, inline=False)
        embeds.append(embed)

    # Sende alle Embeds
    for embed in embeds:
        await interaction.response.send_message(embed=embed) if embed == embeds[0] else await interaction.followup.send(embed=embed)

@bot.tree.command(
    name="toybox_to_toybox_game",
    description="Convert toybox files in a ZIP and optionally change their number"
)
async def toybox_to_toybox_game(
    interaction: discord.Interaction,
    zip_file: discord.Attachment,
    new_number: int = None
):
    # Validate the optional number input
    if new_number is not None and not (1 <= new_number <= 100):
        await interaction.response.send_message(
            "The number must be between 1 and 100!",
            ephemeral=True
        )
        return

    # Check if the uploaded file is a ZIP
    if not zip_file.filename.endswith('.zip'):
        await interaction.response.send_message(
            "Please upload a ZIP file!",
            ephemeral=True
        )
        return

    try:
        # Download the ZIP file
        zip_content = await zip_file.read()
        input_zip = zipfile.ZipFile(io.BytesIO(zip_content))
        
        # Create a new ZIP file in memory
        output_zip_buffer = io.BytesIO()
        output_zip = zipfile.ZipFile(output_zip_buffer, 'w', zipfile.ZIP_DEFLATED)
        
        # Get the folder name from the ZIP (assuming single folder)
        folder_name = None
        for name in input_zip.namelist():
            if name.endswith('/'):
                folder_name = name
                break
        
        if not folder_name:
            await interaction.response.send_message(
                "The ZIP file must contain a folder!",
                ephemeral=True
            )
            return

        # Process each file
        for file_name in input_zip.namelist():
            if file_name.endswith('/'):  # Skip directories
                continue
                
            # Read the file content
            content = input_zip.read(file_name)
            
            # Get just the filename without path
            base_name = os.path.basename(file_name)
            
            # Convert filename by changing only the last R to A in each pattern
            new_name = base_name
            if 'EHRR' in new_name:
                new_name = new_name.replace('EHRR', 'EHRA', 1)
            elif 'ERR' in new_name:
                new_name = new_name.replace('ERR', 'ERA', 1)
            elif 'SCRR' in new_name:
                new_name = new_name.replace('SCRR', 'SCRA', 1)
            elif 'SHRR' in new_name:
                new_name = new_name.replace('SHRR', 'SHRA', 1)
            elif 'SRR' in new_name:
                new_name = new_name.replace('SRR', 'SRA', 1)
            
            # If a new number was provided, replace the existing number
            if new_number is not None:
                # Use regex to replace any number before the file extension
                new_name = re.sub(r'\d+(?=A?$)', str(new_number), new_name)
            
            # Write to new ZIP with the same folder structure
            output_zip.writestr(os.path.join(folder_name, new_name), content)
        
        # Close the ZIPs
        input_zip.close()
        output_zip.close()
        
        # Prepare the output ZIP for sending
        output_zip_buffer.seek(0)
        
        # Send the modified ZIP file
        file = discord.File(
            fp=output_zip_buffer,
            filename=os.path.basename(folder_name.rstrip('/')) + '.zip'
        )
        
        await interaction.response.send_message(
            "Toybox converted to Toybox Game:",
            file=file
        )
        
    except Exception as e:
        await interaction.response.send_message(
            f"An error occurred: {str(e)}",
            ephemeral=True
        )
        return

@bot.tree.command(
    name="toybox_game_to_toybox",
    description="Convert a toybox game ZIP back to a regular toybox format"
)
async def toybox_game_to_toybox(
    interaction: discord.Interaction,
    zip_file: discord.Attachment,
    new_number: int = None
):
    # Validate the optional number input
    if new_number is not None and not (1 <= new_number <= 300):
        await interaction.response.send_message(
            "The number must be between 1 and 300!",
            ephemeral=True
        )
        return

    # Check if the uploaded file is a ZIP
    if not zip_file.filename.endswith('.zip'):
        await interaction.response.send_message(
            "Please upload a ZIP file!",
            ephemeral=True
        )
        return

    try:
        # Download the ZIP file
        zip_content = await zip_file.read()
        input_zip = zipfile.ZipFile(io.BytesIO(zip_content))
        
        # Create a new ZIP file in memory
        output_zip_buffer = io.BytesIO()
        output_zip = zipfile.ZipFile(output_zip_buffer, 'w', zipfile.ZIP_DEFLATED)
        
        # Get the folder name from the ZIP (assuming single folder)
        folder_name = None
        for name in input_zip.namelist():
            if name.endswith('/'):
                folder_name = name
                break
        
        if not folder_name:
            await interaction.response.send_message(
                "The ZIP file must contain a folder!",
                ephemeral=True
            )
            return

        # Mapping of old prefixes to new prefixes
        replacements = {
            'EHRA': 'EHRR',
            'ERA': 'ERR',
            'SCRA': 'SCRR',
            'SHRA': 'SHRR',
            'SRA': 'SRR'
        }

        # Process each file
        for file_name in input_zip.namelist():
            if file_name.endswith('/'):  # Skip directories
                continue
                
            # Read the file content
            content = input_zip.read(file_name)
            
            # Get just the filename without path
            base_name = os.path.basename(file_name)

            # Replace prefixes
            new_name = base_name
            for old, new in replacements.items():
                if base_name.startswith(old):
                    new_name = base_name.replace(old, new, 1)
                    break  # Stop after first match

            # If a new number was provided, replace the existing number
            if new_number is not None:
                # Use regex to replace the existing number before "A" (if present)
                new_name = re.sub(r'\d+(?=A?$)', str(new_number), new_name)
            
            # Write to new ZIP with the same folder structure
            output_zip.writestr(os.path.join(folder_name, new_name), content)
        
        # Close the ZIPs
        input_zip.close()
        output_zip.close()
        
        # Prepare the output ZIP for sending
        output_zip_buffer.seek(0)
        
        # Send the modified ZIP file
        file = discord.File(
            fp=output_zip_buffer,
            filename=os.path.basename(folder_name.rstrip('/')) + '.zip'
        )
        
        await interaction.response.send_message(
            "Toybox Game converted back to Toybox:",
            file=file
        )
        
    except Exception as e:
        await interaction.response.send_message(
            f"An error occurred: {str(e)}",
            ephemeral=True
        )
        return

@bot.tree.command(
    name="change_number",
    description="Change the number in toybox or toybox game files inside a ZIP"
)
async def change_number(
    interaction: discord.Interaction,
    zip_file: discord.Attachment,
    new_number: int
):
    # Validate number input (1-300)
    if not (1 <= new_number <= 300):
        await interaction.response.send_message(
            "The number must be between 1 and 300!",
            ephemeral=True
        )
        return

    # Check if the uploaded file is a ZIP
    if not zip_file.filename.endswith('.zip'):
        await interaction.response.send_message(
            "Please upload a ZIP file!",
            ephemeral=True
        )
        return

    try:
        # Download the ZIP file
        zip_content = await zip_file.read()
        input_zip = zipfile.ZipFile(io.BytesIO(zip_content))
        
        # Create a new ZIP file in memory
        output_zip_buffer = io.BytesIO()
        output_zip = zipfile.ZipFile(output_zip_buffer, 'w', zipfile.ZIP_DEFLATED)
        
        # Get the folder name from the ZIP (assuming single folder)
        folder_name = None
        for name in input_zip.namelist():
            if name.endswith('/'):
                folder_name = name
                break
        
        if not folder_name:
            await interaction.response.send_message(
                "The ZIP file must contain a folder!",
                ephemeral=True
            )
            return

        # Variable to store the first detected old number
        old_number = None

        # Process each file
        for file_name in input_zip.namelist():
            if file_name.endswith('/'):  # Skip directories
                continue
                
            # Read the file content
            content = input_zip.read(file_name)
            
            # Get just the filename without path
            base_name = os.path.basename(file_name)

            # Extract the old number using regex
            match = re.search(r'(\d+)([A-Z]?)$', base_name)
            if match and old_number is None:  # Save only the first found number
                old_number = match.group(1)

            # Replace the number while keeping the suffix
            new_name = re.sub(r'\d+([A-Z]?)$', f"{new_number}\\1", base_name)

            # Write to new ZIP with the same folder structure
            output_zip.writestr(os.path.join(folder_name, new_name), content)

        # Close the ZIPs
        input_zip.close()
        output_zip.close()
        
        # Prepare the output ZIP for sending
        output_zip_buffer.seek(0)
        
        # Create the final message
        final_message = (
            f"File number changed from {old_number} to {new_number}."
            if old_number else f"File number changed to {new_number}."
        )

        file = discord.File(
            fp=output_zip_buffer,
            filename=os.path.basename(folder_name.rstrip('/')) + '.zip'
        )
        
        await interaction.response.send_message(final_message, file=file)
        
    except Exception as e:
        await interaction.response.send_message(
            f"An error occurred: {str(e)}",
            ephemeral=True
        )
        return

AUTHOREDNAME_PATTERN = r'AUTHOREDNAME\s*=\s*"([^"]+)"'
AUTHOREDDESC_PATTERN = r'AUTHOREDDESC\s*=\s*"([^"]+)"'
DATESTRING_PATTERN = r'DATESTRING\s*=\s*"([^"]+)"'
CONTENT_OFFSET = 84  # Offset für die Metadaten

@bot.tree.command(
    name="meta",
    description="Extracts metadata from ZIP, EHRR or EHRA file."
)
async def meta(interaction: discord.Interaction, ehr_file: discord.Attachment):
    try:
        # Temporären Speicherort für Datei erstellen
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = f"{temp_dir}/{ehr_file.filename}"
            
            # Datei herunterladen und speichern
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(await ehr_file.read())
            
            extracted_file_path = None
            
            # Prüfen, ob eine ZIP-Datei hochgeladen wurde
            if ehr_file.filename.endswith(".zip"):
                with zipfile.ZipFile(file_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
                    
                    # Nach EHRR oder EHRA Datei suchen
                    for root, _, files in os.walk(temp_dir):
                        for file in files:
                            if file.startswith("EHRR") or file.startswith("EHRA"):
                                extracted_file_path = os.path.join(root, file)
                                break
                        if extracted_file_path:
                            break
            else:
                extracted_file_path = file_path
            
            # Falls keine passende Datei gefunden wurde
            if not extracted_file_path:
                await interaction.response.send_message("No valid EHRR or EHRA file found in the ZIP!", ephemeral=True)
                return
            
            # Datei auslesen
            async with aiofiles.open(extracted_file_path, 'rb') as f:
                file_bytes = await f.read()
                
            # Daten ab Offset lesen und dekomprimieren
            decompressed_data = zlib.decompress(file_bytes[CONTENT_OFFSET:]).decode('utf-8').rstrip('\x00')
            
            # Metadaten extrahieren
            auth_name_match = re.search(AUTHOREDNAME_PATTERN, decompressed_data)
            auth_desc_match = re.search(AUTHOREDDESC_PATTERN, decompressed_data)
            date_string_match = re.search(DATESTRING_PATTERN, decompressed_data)
            
            # Nachricht erstellen
            metadata_text = "**Metadata Extracted:**\n"
            if auth_name_match:
                metadata_text += f"**Name:** {auth_name_match.group(1)}\n"
            if auth_desc_match:
                metadata_text += f"**Description:** {auth_desc_match.group(1)}\n"
            if date_string_match:
                metadata_text += f"**Date:** {date_string_match.group(1)}\n"
            
            # Falls keine Metadaten gefunden wurden
            if not (auth_name_match or auth_desc_match or date_string_match):
                metadata_text = "No metadata found in the file."
            
            await interaction.response.send_message(metadata_text)
    
    except zipfile.BadZipFile:
        await interaction.response.send_message("Error: Invalid ZIP file!", ephemeral=True)
    except zlib.error:
        await interaction.response.send_message("Error: Could not decompress the file!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

# Admin-Befehl zum Starten der Bewertung in einem Kanal




# Slash-Befehl registrieren, um die Bewertung in einem Kanal zu starten
@bot.tree.command(name="rate", description="Create a Toybox rating with stars.")
async def rate(interaction: discord.Interaction):
    channel_id = interaction.channel_id
    
    # First create a basic message that we'll edit
    message = await interaction.channel.send("Creating rating...")
    message_id = message.id

    # Initialize the ratings for this message
    if message_id not in message_ratings:
        message_ratings[message_id] = {'ratings': {}, 'average': 0, 'num_ratings': 0, 'channel_id': channel_id}

    embed = discord.Embed(
        title="Toybox rating: ⭐️⭐️⭐️⭐️⭐️",
        description="What do you think about this toybox?",
        color=discord.Color.blue()
    )
    embed.add_field(name="Average rating", value="No ratings yet.", inline=False)
    embed.add_field(name="Number of ratings", value="0 ratings yet.", inline=False)

    # Create the view with the buttons
    view = RatingView(message_id)
    
    # Edit the message with the embed and view
    await message.edit(content=None, embed=embed, view=view)
    await interaction.response.send_message("Rating created!", ephemeral=True)
    
    # Speichere den Titel des Kanals für den /play-Befehl
    channel_titles[message_id] = interaction.channel.name
    save_ratings()  # Speichere nach dem Hinzufügen des neuen Kanals

# Forum-Kanal-ID hier eintragen
forum_channel_id = 1253093395920851054  # Ersetze dies mit der tatsächlichen ID deines Forum-Kanals

@bot.tree.command(
    name="play",
    description="Bot suggests a random toybox"
)
@app_commands.describe(count="Number of Toyboxes to select (1-20)")
async def random_thread(interaction: discord.Interaction, count: int = 1):
    # Begrenzung der Anzahl auf 1 bis 20
    if count < 1 or count > 20:
        await interaction.response.send_message("Please enter a number between 1 and 20.", ephemeral=True)
        return

    # Forum-Kanal abrufen
    forum_channel = interaction.guild.get_channel(forum_channel_id)
    if not forum_channel or not isinstance(forum_channel, discord.ForumChannel):
        await interaction.response.send_message("Error: Forum channel not found!", ephemeral=True)
        return
    
    # Alle Threads abrufen
    threads = forum_channel.threads
    if not threads:
        await interaction.response.send_message("No toyboxes found.", ephemeral=True)
        return
    
    # Zufällige Threads auswählen
    selected_threads = random.sample(threads, min(count, len(threads)))
    thread_links = '\n'.join(thread.jump_url for thread in selected_threads)
    
    # Nachricht anpassen
    message_prefix = "Play this Toybox:" if len(selected_threads) == 1 else "Play these Toyboxes:"
    
    # Antwort senden
    await interaction.response.send_message(f"{message_prefix}\n{thread_links}", ephemeral=True)


class PlayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Keine Zeitbegrenzung für die View
        self.count = 1  # Standardwert für die Anzahl der Toyboxes

    @discord.ui.select(
        placeholder="Select number of random Toyboxes",  # Platzhalter zurücksetzen
        options=[
            discord.SelectOption(label=str(i), value=str(i)) for i in range(1, 21)
        ],
        custom_id="select_toybox_count"  # Wichtiger Custom ID für Persistenz
    )
    async def select_count(self, interaction: discord.Interaction, select: discord.ui.Select):
        # Speichert die ausgewählte Anzahl, ohne eine Nachricht zu senden
        self.count = int(select.values[0])
        await interaction.response.defer()  # Bestätigt die Aktion, ohne eine sichtbare Antwort zu geben

    @discord.ui.button(label="Random", style=discord.ButtonStyle.blurple, custom_id="random_toybox_button")
    async def random_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Forum-Kanal abrufen
        forum_channel = interaction.guild.get_channel(forum_channel_id)
        if not forum_channel or not isinstance(forum_channel, discord.ForumChannel):
            await interaction.response.send_message("Error: Forum channel not found!", ephemeral=True)
            return

        # Alle Threads abrufen
        threads = forum_channel.threads
        if not threads:
            await interaction.response.send_message("No toyboxes found!", ephemeral=True)
            return

        # Zufällige Threads auswählen
        selected_threads = random.sample(threads, min(self.count, len(threads)))
        thread_links = '\n'.join(thread.jump_url for thread in selected_threads)

        # Nachricht senden
        message_prefix = "Play this Toybox:" if len(selected_threads) == 1 else "Play these Toyboxes:"
        await interaction.response.send_message(f"{message_prefix}\n{thread_links}", ephemeral=True)

        # Auswahl im Dropdown-Menü zurücksetzen
        self.children[0].placeholder = "Select number of random Toyboxes"
        await interaction.message.edit(view=self)


@bot.tree.command(
    name="batch_infos",
    description="Extracts metadata from ZIP files for all records in a specified creator's table"
)
@discord.app_commands.choices(
    creator=[
        discord.app_commands.Choice(name="Modeltrainman", value="modeltrainman"),
        discord.app_commands.Choice(name="The Bow-Tie Guy", value="bowtieguy"),
        discord.app_commands.Choice(name="Allnightgaming", value="allnightgaming"),
        discord.app_commands.Choice(name="ThatBrownBat", value="thatbrownbat"),
        discord.app_commands.Choice(name="72Pringle", value="72pringle"),
        discord.app_commands.Choice(name="Misc", value="misc"),
        discord.app_commands.Choice(name="JK", value="jk")
    ]
)
async def batch_infos(interaction: discord.Interaction, creator: str):
    await interaction.response.defer()
    
    try:
        # Create initial progress embed
        progress_embed = discord.Embed(
            title="📝 Batch Metadata Extraction",
            description=f"Processing all records from {AIRTABLE_TABLES[creator]} table",
            color=0xec4e4e
        )
        progress_embed.add_field(
            name="Status",
            value="Starting batch process...",
            inline=False
        )
        message = await interaction.followup.send(embed=progress_embed)
        
        # Fetch all records from the table
        records = tables[creator].all()
        total_records = len(records)
        processed = 0
        success = 0
        failed = 0
        
        for record in records:
            processed += 1
            try:
                fields = record.get('fields', {})
                if 'file' not in fields or not fields['file']:
                    continue

                file_url = fields['file'][0]['url']
                
                # Update progress
                progress_embed.set_field_at(
                    0,
                    name="Status",
                    value=f"Processing record {processed}/{total_records}\nSuccesses: {success}\nFailures: {failed}",
                    inline=False
                )
                await message.edit(embed=progress_embed)
                
                # Create temporary directory for each record
                with tempfile.TemporaryDirectory() as temp_dir:
                    file_path = f"{temp_dir}/downloaded.zip"
                    
                    # Download file
                    async with aiohttp.ClientSession() as session:
                        async with session.get(file_url) as response:
                            if response.status != 200:
                                failed += 1
                                continue
                            file_content = await response.read()
                    
                    # Save downloaded file
                    async with aiofiles.open(file_path, 'wb') as f:
                        await f.write(file_content)

                    extracted_file_path = None
                    
                    # Extract ZIP and find EHRR/EHRA file
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        zip_ref.extractall(temp_dir)
                        
                        # Search for EHRR or EHRA file
                        for root, _, files in os.walk(temp_dir):
                            for file in files:
                                if file.startswith("EHRR") or file.startswith("EHRA"):
                                    extracted_file_path = os.path.join(root, file)
                                    break
                            if extracted_file_path:
                                break

                    if not extracted_file_path:
                        failed += 1
                        continue

                    # Read and process the file
                    async with aiofiles.open(extracted_file_path, 'rb') as f:
                        file_bytes = await f.read()

                    # Decompress and decode data
                    decompressed_data = zlib.decompress(file_bytes[CONTENT_OFFSET:]).decode('utf-8').rstrip('\x00')

                    # Extract metadata
                    auth_name_match = re.search(AUTHOREDNAME_PATTERN, decompressed_data)
                    auth_desc_match = re.search(AUTHOREDDESC_PATTERN, decompressed_data)
                    date_string_match = re.search(DATESTRING_PATTERN, decompressed_data)

                    # Update Airtable record
                    update_fields = {}

                    if auth_name_match:
                        update_fields['Name'] = auth_name_match.group(1)

                    if auth_desc_match:
                        update_fields['description'] = auth_desc_match.group(1)

                    if update_fields:
                        tables[creator].update(record['id'], update_fields)
                        success += 1
                    else:
                        failed += 1

            except Exception as e:
                failed += 1
                continue

        # Create final success embed
        final_embed = discord.Embed(
            title="✅ Batch Processing Complete",
            description=f"Processed {total_records} records from {AIRTABLE_TABLES[creator]} table",
            color=0x00ff00
        )
        final_embed.add_field(
            name="Results",
            value=f"Successfully processed: {success}\nFailed: {failed}",
            inline=False
        )
        await message.edit(embed=final_embed)

    except Exception as e:
        error_embed = discord.Embed(
            title="❌ Error",
            description=f"An error occurred during batch processing: {str(e)}",
            color=0xff0000
        )
        await message.edit(embed=error_embed)

@bot.tree.command(
    name="infos",
    description="Extracts metadata from ZIP file in Airtable and updates the record"
)
@discord.app_commands.choices(
    creator=[
        discord.app_commands.Choice(name="Modeltrainman", value="modeltrainman"),
        discord.app_commands.Choice(name="The Bow-Tie Guy", value="bowtieguy"),
        discord.app_commands.Choice(name="Allnightgaming", value="allnightgaming"),
        discord.app_commands.Choice(name="ThatBrownBat", value="thatbrownbat"),
        discord.app_commands.Choice(name="72Pringle", value="72pringle"),
        discord.app_commands.Choice(name="Misc", value="misc"),
        discord.app_commands.Choice(name="JK", value="jk")
    ]
)
async def infos(interaction: discord.Interaction, post_id: str, creator: str):
    await interaction.response.defer()
    
    try:
        # Create initial progress embed
        progress_embed = discord.Embed(
            title="📝 Extracting Metadata",
            description=f"Fetching data for ID: {post_id} from {AIRTABLE_TABLES[creator]} table",
            color=0xec4e4e
        )
        progress_embed.add_field(
            name="Status",
            value="Retrieving data from Airtable...",
            inline=False
        )
        await interaction.followup.send(embed=progress_embed)
        
        # Fetch record from appropriate table
        record = tables[creator].get(post_id)
        if not record:
            error_embed = discord.Embed(
                title="❌ Error",
                description=f"No record found with ID: {post_id} in {AIRTABLE_TABLES[creator]} table",
                color=0xff0000
            )
            await interaction.followup.send(embed=error_embed)
            return

        # Extract file URL from record
        fields = record.get('fields', {})
        if 'file' not in fields or not fields['file']:
            error_embed = discord.Embed(
                title="❌ Error",
                description="No file found in the record",
                color=0xff0000
            )
            await interaction.followup.send(embed=error_embed)
            return

        file_url = fields['file'][0]['url']
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = f"{temp_dir}/downloaded.zip"
            
            # Download file
            progress_embed.set_field_at(
                0,
                name="Status",
                value="Downloading ZIP file...",
                inline=False
            )
            await interaction.edit_original_response(embed=progress_embed)
            
            async with aiohttp.ClientSession() as session:
                async with session.get(file_url) as response:
                    if response.status != 200:
                        raise Exception("Failed to download file")
                    file_content = await response.read()
                    
            # Save downloaded file
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_content)

            extracted_file_path = None
            
            # Extract ZIP and find EHRR/EHRA file
            with zipfile.ZipFile(file_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
                
                # Search for EHRR or EHRA file
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        if file.startswith("EHRR") or file.startswith("EHRA"):
                            extracted_file_path = os.path.join(root, file)
                            break
                    if extracted_file_path:
                        break

            if not extracted_file_path:
                await interaction.followup.send("No valid EHRR or EHRA file found in the ZIP!", ephemeral=True)
                return

            # Read and process the file
            progress_embed.set_field_at(
                0,
                name="Status",
                value="Extracting metadata...",
                inline=False
            )
            await interaction.edit_original_response(embed=progress_embed)
            
            async with aiofiles.open(extracted_file_path, 'rb') as f:
                file_bytes = await f.read()

            # Decompress and decode data
            decompressed_data = zlib.decompress(file_bytes[CONTENT_OFFSET:]).decode('utf-8').rstrip('\x00')

            # Extract metadata
            auth_name_match = re.search(AUTHOREDNAME_PATTERN, decompressed_data)
            auth_desc_match = re.search(AUTHOREDDESC_PATTERN, decompressed_data)
            date_string_match = re.search(DATESTRING_PATTERN, decompressed_data)

            # Update Airtable record
            update_fields = {}
            metadata_text = "**Metadata Extracted:**\n"

            if auth_name_match:
                name = auth_name_match.group(1)
                update_fields['Name'] = name
                metadata_text += f"**Name:** {name}\n"

            if auth_desc_match:
                description = auth_desc_match.group(1)
                update_fields['description'] = description
                metadata_text += f"**Description:** {description}\n"

            if date_string_match:
                date = date_string_match.group(1)
                metadata_text += f"**Date:** {date}\n"

            if update_fields:
                progress_embed.set_field_at(
                    0,
                    name="Status",
                    value="Updating Airtable record...",
                    inline=False
                )
                await interaction.edit_original_response(embed=progress_embed)
                
                # Update Airtable
                tables[creator].update(post_id, update_fields)

            # Create success embed
            success_embed = discord.Embed(
                title="✅ Metadata Extracted",
                description=metadata_text if metadata_text != "**Metadata Extracted:**\n" else "No metadata found in the file.",
                color=0x00ff00
            )
            if update_fields:
                success_embed.add_field(
                    name="Airtable Update",
                    value="Record has been updated with the extracted metadata.",
                    inline=False
                )

            await interaction.edit_original_response(embed=success_embed)

    except zipfile.BadZipFile:
        await interaction.followup.send("Error: Invalid ZIP file!", ephemeral=True)
    except zlib.error:
        await interaction.followup.send("Error: Could not decompress the file!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)



@bot.tree.command(
    name="play_init",
    description="Start an interactive Toybox randomizer"
)
async def play_init(interaction: discord.Interaction):
    # Embed erstellen
    embed = discord.Embed(
        title="Random Toybox Selection",
        description=(
            "**Which Toybox should I play? Let us surprise you!** 🎁\n"
            "1. Choose how many random Toyboxes you would like to see (Dropdown Menu)\n"
            "2. Click on the button below and let the fun begin! 🎲"
        ),
        color=discord.Color.red()  # Optional: Embed-Farbe
    )
    
    # Nachricht mit der interaktiven Ansicht senden
    view = PlayView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=False)  # Nachricht für alle sichtbar


def load_blacklist():
    if os.path.exists(BLACKLIST_FILE):
        with open(BLACKLIST_FILE, "r") as f:
            return json.load(f)
    return []

def save_blacklist(blacklist):
    with open(BLACKLIST_FILE, "w") as f:
        json.dump(blacklist, f)

blacklisted_threads = load_blacklist()

@bot.tree.command(
    name="top_of_the_week",
    description="Get 7 random top threads of the week from the forum"
)
async def top_of_the_week(interaction: discord.Interaction):
    forum_channel = interaction.guild.get_channel(forum_channel_id)
    if not forum_channel or not isinstance(forum_channel, discord.ForumChannel):
        await interaction.response.send_message("Error: Forum channel not found!", ephemeral=True)
        return

    threads = [thread for thread in forum_channel.threads if str(thread.id) not in blacklisted_threads]
    if not threads:
        await interaction.response.send_message("No eligible threads found in the forum channel.", ephemeral=True)
        return

    selected_threads = random.sample(threads, min(7, len(threads)))
    message = "⭐ **TOP OF THE WEEK** ⭐\n\n"
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣"]
    
    for idx, thread in enumerate(selected_threads):
        message += f"{emojis[idx]} **{thread.name}**\n{thread.jump_url}\n\n"

    await interaction.response.send_message(message)

@bot.tree.command(
    name="blacklist_top_threads",
    description="Blacklist or unblacklist threads by their ID for top of the week ranking"
)
@app_commands.describe(thread_id="The ID of the thread to blacklist or remove from blacklist (optional)")
async def blacklist_top_threads(interaction: discord.Interaction, thread_id: str = None):
    global blacklisted_threads
    
    # Falls kein Thread ID angegeben wurde, versuchen, den aktuellen Thread zu identifizieren
    if thread_id is None:
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message("❌ You must provide a thread ID or use this command inside a thread.", ephemeral=True)
            return
        thread_id = str(interaction.channel.id)
    
    if thread_id in blacklisted_threads:
        blacklisted_threads.remove(thread_id)
        save_blacklist(blacklisted_threads)
        await interaction.response.send_message(f"✅ Removed thread `{thread_id}` from blacklist.", ephemeral=True)
    else:
        blacklisted_threads.append(thread_id)
        save_blacklist(blacklisted_threads)
        await interaction.response.send_message(f"❌ Added thread `{thread_id}` to blacklist.", ephemeral=True)


@bot.tree.command(
    name="set_tag",
    description="Set a tag for this thread (use in destination thread)"
)
@app_commands.choices(tag=[
    app_commands.Choice(name=tag, value=tag) for tag in VALID_TAGS
])
async def set_tag(interaction: discord.Interaction, tag: str):  # Removed thread_id parameter
    await interaction.response.defer(ephemeral=True)
    
    # Check if command is used in a thread
    if not isinstance(interaction.channel, discord.Thread):
        await interaction.followup.send("❌ This command can only be used in a thread!", ephemeral=True)
        return
    
    thread_id = str(interaction.channel.id)
    
    try:
        with open(toybox_data_file, "r", encoding='utf-8') as f:
            toybox_list = json.load(f)
        
        found = False
        for toybox in toybox_list:
            if str(toybox["id"]) == thread_id:
                toybox["tags"] = [tag]
                found = True
                break
        
        if found:
            with open(toybox_data_file, "w", encoding='utf-8') as f:
                json.dump(toybox_list, f, indent=4, ensure_ascii=False)
            await interaction.followup.send(f"✅ Updated tag for this thread to {tag}", ephemeral=True)
        else:
            await interaction.followup.send("❌ Thread not found in database. Try running /update_toyboxes first", ephemeral=True)
            
    except Exception as e:
        await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)
        
async def search_toyboxes(query: str) -> List[Dict]:
    try:
        with open(toybox_data_file, "r", encoding='utf-8') as f:
            toybox_list = json.load(f)
    except FileNotFoundError:
        print(f"Toybox data file not found!")
        return []
    
    query = query.lower()
    print(f"Searching for tag: '{query}'")
    
    matches = [
        t for t in toybox_list
        if any(tag.lower() == query for tag in t["tags"])
    ]
    
    print(f"Found {len(matches)} matches for '{query}'")
    return matches


@bot.tree.command(name="toybox_finder", description="Find Toyboxes by franchise")
@app_commands.default_permissions(administrator=True)
async def toybox_finder(interaction: discord.Interaction):
    # Initial message with category selection
    main_view = ToyboxView()
    await interaction.response.send_message(
        embed=discord.Embed(
            title="🕹 Disney Infinity Toybox Explorer",
            description="Select your universe and explore incredible Toyboxes from your favorite franchise Toyboxes.",
            color=discord.Color.blue()
        ),
        view=main_view
    )



@bot.tree.command(name="analyze_toyboxes", description="Analyze toybox files from a zip file")
@app_commands.default_permissions(administrator=True)
async def analyze_toyboxes(interaction: discord.Interaction, file: discord.Attachment = None, url: str = None):
    if not file and not url:
        await interaction.response.send_message("Please provide either a zip file or a URL to a zip file.", ephemeral=True)
        return

    try:
        # First, acknowledge the interaction
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        counter = slotCounter()
        temp_dir = None
        
        try:
            if file:
                # Send a status update
                await interaction.followup.send("📥 Downloading and processing file...", ephemeral=True)
                
                zip_data = await file.read()
                temp_dir = tempfile.mkdtemp()
                
                with zipfile.ZipFile(io.BytesIO(zip_data)) as zip_ref:
                    file_list = zip_ref.namelist()
                    shrr_files = [f for f in file_list if "SHRR" in f.upper()]
                    
                    if not shrr_files:
                        await interaction.followup.send("❌ No SHRR files found in the zip file.", ephemeral=True)
                        return
                        
                    for file in shrr_files:
                        zip_ref.extract(file, temp_dir)
                
                base_path = temp_dir
                
            else:
                # Send a status update
                await interaction.followup.send("📥 Downloading and processing URL...", ephemeral=True)
                base_path, temp_dir = await counter.download_and_extract_zip(url)

            # Send a status update
            await interaction.followup.send("🔍 Analyzing files...", ephemeral=True)
            
            total_count, file_results = counter.count_unique_files(base_path)
            missing_numbers = counter.find_missing_numbers(base_path)
            
            # Create embed for results
            embed = discord.Embed(
                title="🗂️ Toybox File Analysis",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="📊 Total Toyboxes",
                value=str(total_count),
                inline=False
            )
            
            # Split results into multiple embeds if needed
            embeds = [embed]
            current_embed = embed
            field_count = 1

            # Add file results
            for i, result in enumerate(file_results):
                if field_count >= 25:  # Discord has a limit of 25 fields per embed
                    current_embed = discord.Embed(
                        title=f"🗂️ Toybox File Analysis (Continued)",
                        color=discord.Color.blue()
                    )
                    embeds.append(current_embed)
                    field_count = 0

                current_embed.add_field(
                    name=f"📁 File {i+1}",
                    value=result,
                    inline=False
                )
                field_count += 1
            
            # Add missing numbers to the last embed
            if missing_numbers:
                missing_str = ", ".join(map(str, missing_numbers[:20]))
                if len(missing_numbers) > 20:
                    missing_str += f"... and {len(missing_numbers) - 20} more"
                
                current_embed.add_field(
                    name="🔍 Missing Numbers",
                    value=f"Count: {len(missing_numbers)}\nNumbers: {missing_str}",
                    inline=False
                )
            else:
                current_embed.add_field(
                    name="✅ Missing Numbers",
                    value="All numbers from 0 to 300 are present",
                    inline=False
                )
            
            # Send all embeds
            for i, embed in enumerate(embeds):
                if i == 0:
                    await interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            error_message = f"An error occurred while processing the file: {str(e)}"
            try:
                await interaction.followup.send(error_message, ephemeral=True)
            except:
                print(f"Failed to send error message: {error_message}")
        
        finally:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                
    except discord.errors.NotFound:
        print("Interaction not found - it may have timed out")
    except Exception as e:
        print(f"Failed to process command: {str(e)}")













# --- Event Listener for Messages (Handles AI Chat) ---
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot: return
    if not isinstance(message.channel, discord.Thread) or \
       not hasattr(message.channel, 'owner') or message.channel.owner != bot.user or \
       message.channel.type != discord.ChannelType.private_thread or \
       not message.channel.name.startswith("Toybox Chat with"):
        # await bot.process_commands(message) # Only if using prefix commands outside threads
        return

    # --- AI Chat Thread Logic ---
    original_query = message.content.strip()
    if not original_query or original_query.startswith(('/', '!', '$', '#')):
        return

    if not gemini_model:
        await message.channel.send("❌ Waaak! My thinking cap isn't working right now (AI features disabled). Please contact an admin.")
        return

    async with message.channel.typing():
        try:
            # ==================================================================
            # --- NEU: Schritt 1 - Keyword-Extraktion mit Gemini ---
            # ==================================================================
            extracted_keywords_str = ""
            search_query = original_query # Default to original if extraction fails

            try:
                # Prompt an Gemini: Extrahiere die Kernbegriffe
                extraction_prompt = f"""Analyze the following user request for Disney Infinity Toyboxes. Identify the **absolute core keywords or concepts** (like specific characters 'Stitch', 'Iron Man'; franchises 'Star Wars', 'Marvel'; locations 'Endor'; game types 'racing', 'combat'; episodes 'Episode 6'). Ignore generic filler words ('I want to play', 'find', 'show me', 'toybox', 'level', 'any', 'some', 'a'), greetings, and irrelevant numbers or quantities. Return ONLY the extracted core keywords as a single string, separated by spaces. If no clear keywords are found, return the original request, shortened if necessary.

User Request: "{original_query}"

Extracted Keywords:"""

                # API-Aufruf für die Extraktion
                extraction_response = await asyncio.to_thread(
                    gemini_model.generate_content,
                    extraction_prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.1, # Niedrige Temperatur für präzise Extraktion
                        max_output_tokens=60 # Begrenzte Länge für Keywords
                    ),
                    safety_settings=[ # Standard safety settings
                       {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                       {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                       {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                       {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
                    ]
                )

                # Verarbeitung der Extraktionsantwort
                if extraction_response.parts:
                    extracted_keywords_str = extraction_response.text.strip()
                    # Bereinigung: Entferne mögliche Anführungszeichen und normalisiere Leerzeichen
                    extracted_keywords_str = re.sub(r'^"|"$', '', extracted_keywords_str) # Entferne Anführungszeichen am Anfang/Ende
                    extracted_keywords_str = re.sub(r'[^\w\s-]', '', extracted_keywords_str) # Erlaube Buchstaben, Zahlen, Leerzeichen, Bindestriche
                    extracted_keywords_str = re.sub(r'\s+', ' ', extracted_keywords_str).strip() # Normalisiere Leerzeichen

                    if extracted_keywords_str: # Nur verwenden, wenn nach Bereinigung etwas übrig bleibt
                         search_query = extracted_keywords_str
                         print(f"🧠 LLM Keyword Extraction: Original='{original_query}' -> Extracted='{search_query}'")
                    else:
                         print(f"⚠️ LLM Keyword Extraction resulted in empty string after cleaning. Falling back to original query.")
                         # search_query bleibt original_query
                else:
                    # Handle blocked or empty response
                    block_reason = "Unknown"
                    if hasattr(extraction_response, 'prompt_feedback') and extraction_response.prompt_feedback:
                        block_reason = extraction_response.prompt_feedback.block_reason or "Not specified"
                    print(f"⚠️ LLM Keyword Extraction failed or blocked (Reason: {block_reason}) for query: '{original_query}'. Falling back to original query.")
                    # search_query bleibt original_query

            except Exception as extraction_err:
                print(f"❌ Error during LLM Keyword Extraction: {extraction_err}. Falling back to original query.")
                # search_query bleibt original_query

            print(f"🔍 Using search query for retrieval: '{search_query}'")

            # ==================================================================
            # --- Schritt 2: (Optional) Knowledge Base Expansion basierend auf extrahierten Keywords ---
            # ==================================================================
            expansion_keywords = set()
            triggered_expansion = False
            best_matching_item = None # Wird für den finalen RAG-Prompt benötigt
            KB_MATCH_THRESHOLD = 88 # Behalte Schwellenwert bei

            # Nur versuchen zu expandieren, wenn eine Knowledge Base existiert
            # und die extrahierte Query nicht zu lang ist (verhindert unsinnige Expansion)
            if bot.knowledge_base and len(search_query.split()) <= 5:
                # Finde das *beste* passende Konzept in der KB für die *extrahierte* Query
                best_kb_match = process.extractOne(
                    search_query.lower(), # Vergleiche mit Lowercase
                    [item.get('concept','').lower() for item in bot.knowledge_base if item.get('concept')],
                    scorer=fuzz.token_set_ratio,
                    score_cutoff=KB_MATCH_THRESHOLD
                )

                if best_kb_match:
                    matched_concept_name, score = best_kb_match
                    # Finde das vollständige Item, um Keywords zu extrahieren
                    for item in bot.knowledge_base:
                        if item.get('concept','').lower() == matched_concept_name:
                            best_matching_item = item # Speichere das gefundene Item
                            keywords_to_add = {k.lower() for k in item.get('keywords', []) if k}
                            if keywords_to_add:
                                expansion_keywords = keywords_to_add
                                triggered_expansion = True
                                print(f"💡 KB Expansion triggered based on extracted term '{search_query}' matching KB concept '{matched_concept_name}' (Score: {score}). Added boost keywords: {expansion_keywords}")
                            break
            # Wenn keine Expansion ausgelöst wurde oder die KB leer ist, bleibt expansion_keywords leer.

            # ==================================================================
            # --- Schritt 3: Rufe find_relevant_toyboxes mit der bereinigten Query auf ---
            # ==================================================================
            all_toyboxes = bot.toybox_data
            if not all_toyboxes:
                data_exists = os.path.exists(toybox_data_file)
                if data_exists and message.guild: await message.channel.send(f"Hmm, my notes look empty... `/update_toyboxes` might help! 🦆")
                elif not data_exists and message.guild: await message.channel.send(f"❌ Uh oh! `{toybox_data_file}` is missing. `/update_toyboxes` needed.")
                else: await message.channel.send("❌ Waaak! Can't access notes. Contact admin.")
                return

            # WICHTIG: Übergib die 'search_query' (extrahierte Keywords) an die Funktion
            # Die 'expansion_keywords' kommen aus dem optionalen Schritt 2 und dienen nur zum Boosten
            initially_retrieved_toyboxes = find_relevant_toyboxes(
                search_query, # Die (potenziell von LLM extrahierte) Hauptsuchanfrage
                all_toyboxes,
                expansion_keywords, # Keywords aus der KB-Expansion zum Boosten (kann leer sein)
                max_results=15
            )

            # ==================================================================
            # --- Schritt 4 & 5: Kontext bauen und an Gemini für die RAG-Antwort senden ---
            # ==================================================================
            if not initially_retrieved_toyboxes:
                 # Nachricht angepasst, um die verwendeten Suchbegriffe zu nennen
                 no_results_embed = discord.Embed(
                    title="🤔 Hmm, Quackers!",
                    description=(
                        f"Waaak! I looked for Toyboxes matching '**{search_query}**' but couldn't find anything specific in the collection this time. 🦆\n\n"
                        f"**Maybe try asking differently?**\n"
                        f"• Use other related terms.\n"
                        f"• Be more general or more specific.\n"
                        f"• Mention a character, franchise, or game type."
                    ),
                    color=discord.Color.orange()
                )
                 no_results_embed.set_thumbnail(url="https://i.imgur.com/FxMKfGt.png")
                 no_results_embed.set_footer(text="Keep trying! We'll find something fun!")
                 await message.channel.send(embed=no_results_embed)
                 return

            # --- Context Building (Logik bleibt gleich) ---
            context_str = "Found these potentially relevant Toyboxes in our forum archive:\n\n"
            context_limit = 10000 # Limit für Kontextlänge
            temp_context = ""
            actual_toyboxes_in_context = []

            for i, tb in enumerate(initially_retrieved_toyboxes, 1):
                toybox_name = tb.get('name', 'N/A').strip()
                toybox_desc = tb.get('description', '').strip()
                toybox_url = tb.get('url', '')
                toybox_tags = tb.get('tags', ['Other'])
                desc_preview = "No description provided."
                if toybox_desc:
                    # Versuche Zeilenumbrüche durch Leerzeichen zu ersetzen für kompaktere Vorschau
                    desc_preview = ' '.join(toybox_desc.splitlines())
                    desc_preview = desc_preview[:200] + ('...' if len(desc_preview) > 200 else '')

                entry_str = f"--- Toybox {i} ---\nName: {toybox_name}\nTags: {', '.join(toybox_tags)}\nDesc Preview: {desc_preview}\nLink: <{toybox_url}>\n\n"
                # Prüfe, ob das Hinzufügen dieses Eintrags das Limit überschreitet
                if len(context_str) + len(temp_context) + len(entry_str) > context_limit:
                    print(f"Context limit ({context_limit}) reached. Stopping context inclusion at Toybox {i-1}.")
                    break
                temp_context += entry_str
                actual_toyboxes_in_context.append(tb) # Füge Toybox hinzu, die tatsächlich im Kontext ist

            # Füge den gesammelten Kontext hinzu
            context_str += temp_context
            context_str += "---\nEnd of Provided Toybox Information."

            # Sicherheitscheck: Wenn nach dem Limit-Check keine Toyboxen im Kontext sind
            if not actual_toyboxes_in_context:
                 await message.channel.send("Waaak! The first found toybox info was too long to process even alone. Try a much more specific query? 🦆")
                 return


            # --- Angepasster RAG-Prompt für Gemini ---
            # Erwähnt Originalanfrage und extrahierte Suchbegriffe
            prompt = f"""You are a specialized, friendly and helpful assistant for the Disney Infinity community Discord server. Your goal is to help users find Toyboxes shared in the forum based on their questions, using ONLY the provided context. Be conversational and enthusiastic!

**Background:**
- The user's original request was: "{original_query}"
- To focus the search, the key subjects identified from the request were: "{search_query}"
- {("(Optional: The search was potentially boosted with related keywords for the concept '" + best_matching_item['concept'] + "': " + str(expansion_keywords) + ")") if triggered_expansion and best_matching_item else "(Optional: No relevant knowledge base concept found for boosting.)"}- The "Provided Toybox Information" below contains search results based on the identified key subjects "{search_query}".

**Instructions:**
1. Identify the core **subject or topic** the user is asking about, considering both their original request ("{original_query}") and the extracted search terms ("{search_query}"). Let's call this the 'User Topic'.
2. Carefully examine **each** item in the "Provided Toybox Information".
3. For each Toybox, determine if it is **genuinely relevant** to the 'User Topic' (especially related to '{search_query}').
    - **High Relevance:** Name, tags, or description *directly* relate to the 'User Topic' or the search terms '{search_query}'.
    - **Consider Relevance:** Even if the title doesn't exactly match, it's relevant if its content (judging by name, tags, description preview) clearly relates to the 'User Topic'/{search_query}.
    - **Ignore if irrelevant:** Disregard Toyboxes that seem unrelated to the 'User Topic'/{search_query}, even if they appeared in the search results.
4. Formulate a helpful and conversational response based **only** on the relevant Toyboxen you identified:
    - **If relevant Toyboxen were found:**
        - Start with a positive confirmation related to the 'User Topic'/{search_query}. Examples: "Oh boy, oh boy! I found some Toyboxes about {search_query}!", "Waaak! Look what I dug up for '{search_query}':", "Quack-tastic! Check out these Toyboxes featuring {search_query}:".
        - Recommend **only** the Toyboxen you deemed relevant in step 3, up to a maximum of 10.
        - For each recommended Toybox:
            - Use the Toybox Name as a **Markdown H2 heading** (e.g., `## Stitch's Great Escape`).
            - On the **next line**, briefly explain *why it's relevant* to the 'User Topic' or '{search_query}', citing details from the context (e.g., "This one features Stitch himself!" or "This race track sounds perfect for what you asked!").
            - Immediately following, include the **Link** as a **Markdown bullet point**: `* [🔗 Link](<URL>)`
    - **If, after careful review, none of the PROVIDED Toyboxen seem relevant to the 'User Topic'/{search_query}:**
        - State clearly in that none of the specific options **I examined from the search results** seemed to fit '{search_query}'. Example: "Aw, phooey! I looked through the list for '{search_query}', but none of these seem quite right..."
        - Briefly explain *why* based on the topic (e.g., "...they were mostly about other characters!").
        - Encourage them to try different terms. Example: "Maybe try asking for something else?"
    - **Strictly adhere to the provided information.** Do not make up details or add closing remarks like "Let me know...".

**Provided Toybox Information (Context - Use ONLY This):**
{context_str}

**User's Original Question:** {original_query}
**(Search focused on:** {search_query}**)

**Your Answer (Respond following all instructions, focusing *only* on relevant items from the provided context):**
"""

            # ==================================================================
            # --- Schritt 6: Sende RAG-Prompt an Gemini und verarbeite Antwort ---
            # ==================================================================
            try:
                # print(f"--- Sending RAG Prompt to Gemini (Length: {len(prompt)}) ---") # Debug Prompt
                # print(prompt[-1000:]) # Debug last part of prompt
                # print(f"--- End RAG Prompt ---") # Debug

                response = await asyncio.to_thread(
                    gemini_model.generate_content,
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.5 # Etwas höhere Temperatur für Donalds Persönlichkeit
                        ),
                    safety_settings=[ # Standard safety settings
                       {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                       {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                       {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
                       {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"}
                    ]
                )

                # --- Process Response (Logik bleibt gleich) ---
                if not response.parts:
                     block_reason = "Unknown"
                     safety_ratings_str = "N/A"
                     if hasattr(response, 'prompt_feedback') and response.prompt_feedback:
                         block_reason = response.prompt_feedback.block_reason or "Not specified"
                         safety_ratings_str = str(response.prompt_feedback.safety_ratings) if response.prompt_feedback.safety_ratings else "N/A"
                     print(f"Gemini RAG response potentially blocked or empty (Thread {message.channel.id}). Reason: {block_reason}, Safety: {safety_ratings_str}")
                     await message.channel.send(f"⚠️ Waaak! My response got filtered (Reason: `{block_reason}`). Could you ask differently? 🦆")
                     return

                answer = response.text.strip() # .strip() hinzugefügt
                # print(f"+++ Received Gemini RAG Response (Thread {message.channel.id}) +++\n{answer}\n+++ End Response +++") # Debug

            except ValueError as ve:
                print(f"❌ Gemini Configuration/Value Error (RAG) (Thread {message.channel.id}): {ve}")
                error_msg = "❌ Waaak! Setup wrong (Config Error). Tell admin!"
                if "api key" in str(ve).lower(): error_msg = "❌ Uh oh! Connection bad (API Key issue). Tell admin!"
                await message.channel.send(error_msg)
                return
            except Exception as gemini_err:
                print(f"❌ Gemini API Error (RAG) (Thread {message.channel.id}): {gemini_err}\n{traceback.format_exc()}")
                error_msg = f"🤖 Waaak! Brain snag ({type(gemini_err).__name__}). Try again? 🦆"
                err_str = str(gemini_err).lower()
                if "api key not valid" in err_str: error_msg = "❌ Uh oh! Connection bad (Invalid API key). Tell admin!"
                elif "quota" in err_str or "rate limit" in err_str: error_msg = "🦆 Aw, phooey! Too much thinking! (Quota/Rate Limit). Try later?"
                elif "resource has been exhausted" in err_str: error_msg = "🦆 Waaak! System busy! Try later!"
                elif "model `gemini" in err_str and "not found" in err_str: error_msg = f"❌ Uh oh! AI model missing! Tell admin!"
                elif "internal error" in err_str or "server error" in err_str: error_msg = "⚙️ Aw, nuts! AI glitch! Try again!" # Generischer Serverfehler hinzugefügt
                await message.channel.send(error_msg)
                return

                # Send formatted response
            try:
                response_embed = discord.Embed(
                    title="🦆 Toybox Recommendations:",
                    description=answer[:4096] if len(answer) <= 4096 else answer[:4093] + "...",
                    color=discord.Color.random()
                )
                await message.channel.send(embed=response_embed)
                if len(answer) > 4096:
                    remaining_text = "[...]\n" + answer[4096:]
                    MAX_MSG_LENGTH = 2000
                    remaining_chunks = [remaining_text[i:i+MAX_MSG_LENGTH] for i in range(0, len(remaining_text), MAX_MSG_LENGTH)]
                    for chunk in remaining_chunks:
                        await message.channel.send(chunk)
                        await asyncio.sleep(0.6)
            except Exception as e:
                print(f"Unexpected error in send_formatted_response: {e}\n{traceback.format_exc()}")
                # Fallback to sending plain text if embed fails
                await message.channel.send(f"Aw, phooey! Something went wrong displaying the results.\n\nHere's what I found:\n{answer}")

        except Exception as e:
            print(f"❌ Unexpected Error during RAG processing in thread {message.channel.id}:")
            print(traceback.format_exc())
            await message.channel.send(f"🦆 Waaak! Unexpected error ({type(e).__name__}). Logged. Try again or tell admin!")
            return # Wichtig: Beende die Funktion hier, da die AI-Chat-Nachricht behandelt wurde

    # --- DANN: count_publish Logik ---
    # Dieser Code wird nur ausgeführt, wenn es KEINE AI-Chat-Nachricht war
    if message.author.id in counter.counting_sessions: # Nur wenn der Autor in einer Zählsitzung ist
        processed_files = []
        for attachment in message.attachments:
            if attachment.filename.endswith('.zip'):
                zip_data = await attachment.read()
                count = counter.count_srr_files(zip_data, attachment.filename)
                
                counter.counting_sessions.setdefault(message.author.id, []).append((attachment.filename, count))
                processed_files.append((attachment.filename, count))
        
        if processed_files: # Nur wenn ZIPs verarbeitet wurden
            total = sum(count for _, count in counter.counting_sessions[message.author.id])
            
            progress_embed = discord.Embed(
                title="📊 Toybox Counting Session",
                description="Upload ZIP files to count toyboxes.\nCurrent progress shown below.",
                color=0xdb6534 # Orange
            )
            progress_embed.add_field(name="━━ File Details ━━", value="", inline=False)
            for fname, fcount in counter.counting_sessions[message.author.id]:
                formatted_filename = fname.replace('_', ' ').replace('.zip', '')
                progress_embed.add_field(
                    name=f"📦 {formatted_filename}",
                    value=f"> Found `{fcount}` Toybox{'es' if fcount != 1 else ''}",
                    inline=False
                )
            progress_embed.add_field(name="━━ Summary ━━", value="", inline=False)
            progress_embed.add_field(
                name="📈 Current Total",
                value=f"```\n{total} Toybox{'es' if total != 1 else ''}\n```",
                inline=False
            )
            progress_embed.timestamp = discord.utils.utcnow()
            progress_embed.set_footer(
                text="Toybox Count Bot | Session in Progress 🔄",
                icon_url="https://cdn.discordapp.com/emojis/1039238467898613851.webp?size=96&quality=lossless" # Beispiel-Emoji
            )
            
            progress_message_obj = counter.progress_messages.get(message.author.id) # progress_message ist jetzt progress_message_obj
            if progress_message_obj:
                await progress_message_obj.edit(embed=progress_embed, view=CountingView(counter, message.author.id, progress_message_obj))
            
            if len(processed_files) == len(message.attachments): # Nur löschen, wenn alle Anhänge ZIPs waren
                try:
                    await message.delete()
                except discord.HTTPException: # Kann fehlschlagen, wenn Berechtigungen fehlen oder Nachricht schon weg ist
                    pass
        # Wenn keine ZIPs verarbeitet wurden, aber der User in einer Session ist, passiert nichts weiter mit der Zähl-Logik für diese Nachricht.

    # --- ZULETZT: Prefixed Commands verarbeiten ---
    # Dieser Code wird nur ausgeführt, wenn es keine AI-Chat-Nachricht war
    # und entweder der User nicht in einer Zählsitzung ist ODER die Nachricht in der Zählsitzung keine ZIPs enthielt.
    await bot.process_commands(message)


# 🚀 Update ausführen, wenn der Bot startet
@bot.event
async def on_ready():
    print(f"Bot {bot.user} is online.")

    # Set presence
    await bot.change_presence(activity=discord.Game(name="Community Toyboxes"))

    # Load ratings
    load_ratings()

    # Register persistent views
    bot.add_view(ToyboxView())
    await setup_views()
    bot.add_view(PersistentView(timeout=None))
    bot.add_view(AskToyboxPanelView())
    bot.add_view(PlayView())

    # Register RatingView for all messages with ratings
    for message_id in message_ratings.keys():
        bot.add_view(RatingView(message_id))

    # Load knowledge base
    try:
        async with aiofiles.open(knowledge_base_file, "r", encoding='utf-8') as f:
            content = await f.read()
            bot.knowledge_base = json.loads(content)
        print(f"✅ Knowledge Base loaded successfully with {len(bot.knowledge_base)} concepts from {knowledge_base_file}.")
    except FileNotFoundError:
        print(f"⚠️ Knowledge Base file '{knowledge_base_file}' not found. Query expansion will be disabled.")
        bot.knowledge_base = []
    except Exception as e:
        print(f"❌ Unexpected error loading Knowledge Base '{knowledge_base_file}': {e}")
        bot.knowledge_base = []

    # Load toybox data
    try:
        with open(toybox_data_file, "r", encoding='utf-8') as f:
            bot.toybox_data = json.load(f)
        print(f"✅ Toybox database loaded with {len(bot.toybox_data)} entries.")
    except Exception as e:
        print(f"⚠️ Could not load toybox database: {e}")
        bot.toybox_data = []

    # Sync commands and register views
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
        print("Persistent views registered successfully.")
    except Exception as e:
        print(f"Error syncing commands: {e}")

    # Update toybox database (pass guild if needed)
    if bot.guilds:
        await update_toybox_database(bot.guilds[0])
    else:
        print("No guilds found for update_toybox_database!")

    print(f'Bot is ready! Logged in as {bot.user.name}')


# Bot starten
if __name__ == "__main__":
    bot.run(TOKEN)