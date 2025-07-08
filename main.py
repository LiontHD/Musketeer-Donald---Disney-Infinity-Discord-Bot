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
from thefuzz import fuzz
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
import logging



# Discord Bot Token
load_dotenv()  # lädt die Variablen aus der .env Datei
TOKEN = os.getenv('BOT_TOKEN')
AIRTABLE_API_KEY = os.getenv('AIRTABLE_API_KEY')
AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID')

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
    "jk": "JK"
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



@bot.tree.command(name="post", description="Create a forum post from Airtable data")
@discord.app_commands.choices(
    creator=[
        discord.app_commands.Choice(name="Modeltrainman", value="modeltrainman"),
        discord.app_commands.Choice(name="The Bow-Tie Guy", value="bowtieguy"),
        discord.app_commands.Choice(name="Allnightgaming", value="allnightgaming"),
        discord.app_commands.Choice(name="ThatBrownBat", value="thatbrownbat"),
        discord.app_commands.Choice(name="72Pringle", value="72pringle"),
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
async def convert_360_to_pc(interaction: discord.Interaction, file: discord.Attachment = None):
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
@bot.event
async def on_ready():
    print(f"Bot {bot.user} is online.")
    
    # Setze den Status des Bots auf "Playing Disney Infinity"
    await bot.change_presence(activity=discord.Game(name="Community Toyboxes"))

    # Lade die gespeicherten Bewertungen, wenn der Bot startet
    load_ratings()

    # Registriere Views für alle Nachrichten, die Bewertungen haben
    for message_id in message_ratings.keys():
        bot.add_view(RatingView(message_id))

    # Befehle synchronisieren, um sicherzustellen, dass Slash-Befehle registriert sind
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")

        # Registriert die Persistente View
        bot.add_view(PlayView())
        print("Persistent views registered successfully.")
    except Exception as e:
        print(f"Error syncing commands: {e}")

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

BLACKLIST_FILE = "blacklisted_threads.json"

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
    name="update_toyboxes", 
    description="Update the Toybox database threads with tags"
)

async def update_toyboxes(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    success = await update_toybox_database(interaction.guild)
    if success:
        await interaction.followup.send("✅ Toybox database has been updated!", ephemeral=True)
    else:
        await interaction.followup.send("❌ Error updating toybox database", ephemeral=True)

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













@bot.event
async def on_message(message):
    await bot.process_commands(message)
    
    if message.author.bot:
        return

    if message.author.id not in counter.counting_sessions:
        return
    
    processed_files = []
    
    for attachment in message.attachments:
        if attachment.filename.endswith('.zip'):
            zip_data = await attachment.read()
            count = counter.count_srr_files(zip_data, attachment.filename)
            
            counter.counting_sessions.setdefault(message.author.id, []).append((attachment.filename, count))
            processed_files.append((attachment.filename, count))
    
    if processed_files:
        total = sum(count for _, count in counter.counting_sessions[message.author.id])
        
        # Updated progress embed with new design
        progress_embed = discord.Embed(
            title="📊 Toybox Counting Session",
            description="Upload ZIP files to count toyboxes.\nCurrent progress shown below.",
            color=0xdb6534
        )
        
        # Add divider before file details
        progress_embed.add_field(
            name="━━ File Details ━━",
            value="",
            inline=False
        )
        
        # Add file details with new formatting
        for fname, fcount in counter.counting_sessions[message.author.id]:
            formatted_filename = fname.replace('_', ' ').replace('.zip', '')
            progress_embed.add_field(
                name=f"📦 {formatted_filename}",
                value=f"> Found `{fcount}` Toybox{'es' if fcount != 1 else ''}",
                inline=False
            )
        
        # Add divider before total
        progress_embed.add_field(
            name="━━ Summary ━━",
            value="",
            inline=False
        )
        
        # Add total with code block formatting
        progress_embed.add_field(
            name="📈 Current Total",
            value=f"```\n{total} Toybox{'es' if total != 1 else ''}\n```",
            inline=False
        )
        
        # Add timestamp
        progress_embed.timestamp = discord.utils.utcnow()
        
        # Add enhanced footer
        progress_embed.set_footer(
            text="Toybox Count Bot | Session in Progress 🔄",
            icon_url="https://cdn.discordapp.com/emojis/1039238467898613851.webp?size=96&quality=lossless"
        )
        
        # Update the progress message
        progress_message = counter.progress_messages.get(message.author.id)
        if progress_message:
            await progress_message.edit(embed=progress_embed, view=CountingView(counter, message.author.id, progress_message))
        
        # Delete only if all attachments were ZIP files
        if len(processed_files) == len(message.attachments):
            try:
                await message.delete()
            except:
                pass



# 🚀 Update ausführen, wenn der Bot startet
@bot.event
async def on_ready():

    # Add the persistent views
    bot.add_view(ToyboxView())
    await setup_views()

    # Add any existing views here
    bot.add_view(PersistentView(timeout=None))
    print(f'Bot is ready! Logged in as {bot.user.name}')
    
    
    # Setze den Status des Bots auf "Playing Disney Infinity"
    await bot.change_presence(activity=discord.Game(name="Community Toyboxes"))

    # Lade die gespeicherten Bewertungen, wenn der Bot startet
    load_ratings()

    # Registriere Views für alle Nachrichten, die Bewertungen haben
    for message_id in message_ratings.keys():
        bot.add_view(RatingView(message_id))

    # Befehle synchronisieren, um sicherzustellen, dass Slash-Befehle registriert sind
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")

        # Registriert die Persistente View
        bot.add_view(PlayView())
        print("Persistent views registered successfully.")
    except Exception as e:
        print(f"Error syncing commands: {e}")
    await update_toybox_database()


# Bot starten
if __name__ == "__main__":
    bot.run(TOKEN)
