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
import asyncio


# Discord Bot Token
load_dotenv()  # lädt die Variablen aus der .env Datei
TOKEN = os.getenv('BOT_TOKEN')

# Bot-Einstellungen
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True  # Stelle sicher, dass diese Intention gesetzt ist
intents.members = True
intents.presences = True

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

bot = commands.Bot(command_prefix="/", intents=intents)

# Globale Variablen für nachrichten-spezifische Bewertungen
message_ratings = {}  # Ein Dictionary, um die Bewertungen pro Nachricht zu speichern
channel_titles = {}  # Speichert die Titel der Kanäle für den /play-Befehl
counter = ToyboxCounter()

# Configuration for bot monitoring
TARGET_BOT_ID = 1284295445337739306  # Replace with the ID of the bot you want to monitor
NOTIFICATION_CHANNEL_ID = 741316090109362277  # Replace with the channel ID where you want to send notifications
GUILD_ID = 741308936036024341

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

# Custom View für die Knöpfe
class RatingView(View):
    def __init__(self, message_id):
        super().__init__(timeout=None)  # Timeout auf None setzen, damit die View nicht abläuft
        self.message_id = message_id  # Speichere die Nachrichten-ID

    async def handle_rating(self, interaction: discord.Interaction, rating: int):
        user_id = interaction.user.id
        message_id = self.message_id

        # Sicherstellen, dass die Nachricht existiert
        if message_id not in message_ratings:
            message_ratings[message_id] = {'ratings': {}, 'average': 0, 'num_ratings': 0}  # num_ratings initialisieren

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
            # Die Anzahl der Bewertungen nur erhöhen, wenn es eine neue Bewertung ist
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


    # Jeder Button benötigt einen eindeutigen custom_id, damit er persistent ist
    @discord.ui.button(label="⭐️", style=discord.ButtonStyle.primary, custom_id="rate_1_{self.message_id}")
    async def rate_1(self, interaction: discord.Interaction, button: Button):
        await self.handle_rating(interaction, 1)

    @discord.ui.button(label="⭐️⭐️", style=discord.ButtonStyle.primary, custom_id="rate_2_{self.message_id}")
    async def rate_2(self, interaction: discord.Interaction, button: Button):
        await self.handle_rating(interaction, 2)

    @discord.ui.button(label="⭐️⭐️⭐️", style=discord.ButtonStyle.primary, custom_id="rate_3_{self.message_id}")
    async def rate_3(self, interaction: discord.Interaction, button: Button):
        await self.handle_rating(interaction, 3)

    @discord.ui.button(label="⭐️⭐️⭐️⭐️", style=discord.ButtonStyle.primary, custom_id="rate_4_{self.message_id}")
    async def rate_4(self, interaction: discord.Interaction, button: Button):
        await self.handle_rating(interaction, 4)

    @discord.ui.button(label="⭐️⭐️⭐️⭐️⭐️", style=discord.ButtonStyle.primary, custom_id="rate_5_{self.message_id}")
    async def rate_5(self, interaction: discord.Interaction, button: Button):
        await self.handle_rating(interaction, 5)

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
    
import asyncio  # Fehlender Import

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

import math

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
    channel_id = interaction.channel_id  # Speichere die Kanal-ID
    message = await interaction.channel.send("<:EmojiName:741403450314850465>")
    message_id = message.id  # Nachrichten-ID speichern

    # Stelle sicher, dass es für diese Nachricht ein Bewertungssystem gibt
    if message_id not in message_ratings:
        message_ratings[message_id] = {'ratings': {}, 'average': 0, 'num_ratings': 0, 'channel_id': channel_id}  # channel_id speichern

    embed = discord.Embed(
        title="Toybox rating: ⭐️⭐️⭐️⭐️⭐️",
        description="What do you think about this toybox?",
        color=discord.Color.blue()
    )
    embed.add_field(name="Average rating", value="No ratings yet.", inline=False)
    embed.add_field(name="Number of ratings", value="0 ratings yet.", inline=False)

    # Nachricht mit Bewertungsknöpfen senden
    await interaction.response.send_message(embed=embed, view=RatingView(message_id))
    
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



async def is_bot_online():
    guild = bot.get_guild(GUILD_ID)
    
    if not guild:
        print("Gilde nicht gefunden.")
        return False
    
    # Wähle einen Textkanal, in dem beide Bots Zugriff haben
    channel = guild.system_channel or guild.text_channels[0]
    
    if not channel:
        print("Kein geeigneter Kanal gefunden.")
        return False
    
    try:
        # Sende "hello" in den Kanal
        await channel.send('hello')
        
        def check(m):
            return m.author.id == TARGET_BOT_ID and m.content.lower() == 'hi' and m.channel.id == channel.id
        
        # Warte auf die Antwort des Target Bots
        msg = await bot.wait_for('message', check=check, timeout=10)  # Timeout nach 10 Sekunden
        return True  # Bot hat geantwortet
    except asyncio.TimeoutError:
        return False  # Bot hat nicht geantwortet
    except Exception as e:
        print(f"Fehler beim Überprüfen des Bot-Status: {e}")
        return 


@bot.tree.command(name="monitor_status", description="Überprüfe den aktuellen Status des überwachten Bots")
async def check_bot_status(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    
    is_online = await is_bot_online()
    status_emoji = "🟢" if is_online else "🔴"
    status_text = "online" if is_online else "offline"
    
    await interaction.followup.send(f"{status_emoji} Bot <@{TARGET_BOT_ID}> ist derzeit {status_text}.", ephemeral=True)


@bot.tree.command(
    name="creator",
    description="Search for all Toybox threads by a specific creator"
)
async def creator_search(interaction: discord.Interaction, creator_name: str):
    # Interaktion aktiv halten
    await interaction.response.defer(thinking=True)

    # Forum-Kanal abrufen
    forum_channel = interaction.guild.get_channel(forum_channel_id)
    if not forum_channel or not isinstance(forum_channel, discord.ForumChannel):
        await interaction.followup.send("Error: Forum channel not found!", ephemeral=True)
        return

    # Threads abrufen
    print("Fetching threads...")
    threads = list(forum_channel.threads[:50])  # Begrenzung auf 50 aktive Threads
    archived_threads = []
    async for thread in forum_channel.archived_threads(limit=50):  # Begrenzung auf 50 archivierte Threads
        print(f"Found archived thread: {thread.name}")
        archived_threads.append(thread)
    threads.extend(archived_threads)

    print(f"Total threads fetched: {len(threads)}")
    if not threads:
        await interaction.followup.send("No threads found in the forum channel.", ephemeral=True)
        return

    matching_threads = []
    for thread in threads:
        print(f"Processing thread: {thread.name}")
        try:
            # Erste Nachricht abrufen
            first_message = await thread.fetch_message(thread.id)
            print(f"Fetched message for thread: {thread.name}")

            # Nachrichtentext prüfen
            content = first_message.content
            match = re.search(r"🎨 Creator:\s*(.+)", content)
            if match:
                extracted_creator = match.group(1).strip()
                if creator_name.lower() in extracted_creator.lower():
                    matching_threads.append(thread)
        except discord.NotFound:
            print(f"Message not found for thread: {thread.name}")
        except discord.Forbidden:
            print(f"Access forbidden for thread: {thread.name}")
        except Exception as e:
            print(f"Error processing thread {thread.name}: {e}")

    if not matching_threads:
        await interaction.followup.send(
            f"No threads found for the creator: {creator_name}.",
            ephemeral=True
        )
        return

    # Ergebnisse anzeigen
    embed = discord.Embed(
        title=f"🎨 Threads by {creator_name}",
        description=f"Here are all the threads by the creator '{creator_name}':",
        color=discord.Color.blue()
    )
    for idx, thread in enumerate(matching_threads, start=1):
        embed.add_field(
            name=f"{idx}. {thread.name}",
            value=f"[Jump to thread]({thread.jump_url})",
            inline=False
        )

    print("Sending results...")
    await interaction.followup.send(embed=embed)


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
    # Debug: Überprüfen, ob der Bot auf dem Server ist
    # Optional: Status beim Start überprüfen
    is_online = await is_bot_online()
    status_text = "online" if is_online else "offline"
    print(f"Der Target Bot ist {status_text}.")

    guild = bot.get_guild(GUILD_ID)
    if guild:
        target_bot = guild.get_member(TARGET_BOT_ID)
        if not target_bot:
            target_bot = await guild.fetch_member(TARGET_BOT_ID)
        if target_bot:
            print(f"Überwachter Bot {target_bot.name} gefunden in {guild.name}")
            print(f"Aktueller Status: {target_bot.status}")
        else:
            print(f"Überwachter Bot nicht gefunden in {guild.name}")
    else:
        print("Bot ist nicht auf dem angegebenen Server.")
    # Add the persistent views
    bot.add_view(ToyboxView())
    
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
