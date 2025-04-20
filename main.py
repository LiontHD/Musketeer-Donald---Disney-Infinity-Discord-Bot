import discord
from discord.ext import commands
from discord.ui import Button, View
import random
import json
import os
import zipfile
import io
import re
import math
# Discord Bot Token
TOKEN = 'MTI4OTk1MzMwMzU2Mzg2NjIwNg.GVdTII.BOK5_lAc0bWXOB7e4YruJETaY9IssdMf73Ixe4'  # Bitte Token sicher aufbewahren

# Bot-Einstellungen
intents = discord.Intents.default()
intents.message_content = True  # Stelle sicher, dass diese Intention gesetzt ist

bot = commands.Bot(command_prefix="/", intents=intents)

# Globale Variablen für nachrichten-spezifische Bewertungen
message_ratings = {}  # Ein Dictionary, um die Bewertungen pro Nachricht zu speichern
channel_titles = {}  # Speichert die Titel der Kanäle für den /play-Befehl

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

# Befehl für JSON Datei
@bot.tree.command(name="json", description="Send the current rating.json file.")
async def send_json(interaction: discord.Interaction):
    # Pfad zur JSON-Datei
    file_path = "ratings.json"
    
    # Überprüfe, ob die Datei existiert
    if os.path.exists(file_path):
        # Datei als Anhang senden
        await interaction.response.send_message("Here is the current `ratings.json` file:", file=discord.File(file_path))
    else:
        # Fehlermeldung, falls die Datei nicht existiert
        await interaction.response.send_message("The `ratings.json` file does not exist.", ephemeral=True)

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

        # Process each file
        for file_name in input_zip.namelist():
            if file_name.endswith('/'):  # Skip directories
                continue
                
            # Read the file content
            content = input_zip.read(file_name)
            
            # Get just the filename without path
            base_name = os.path.basename(file_name)

            # Replace the number in the filename (keeping any letter after it)
            new_name = re.sub(r'(\d+)([A-Z]?)$', f"{new_number}\\2", base_name)

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
            "File numbers changed successfully:",
            file=file
        )
        
    except Exception as e:
        await interaction.response.send_message(
            f"An error occurred: {str(e)}",
            ephemeral=True
        )
        return


# Befehl zum zufälligen Abspielen einer bewerteten Toybox
@bot.tree.command(name="play", description="Play a random rated toybox.")
async def play_random_toybox(interaction: discord.Interaction):
    if not channel_titles:
        await interaction.response.send_message("No toyboxes have been rated yet.")
        return

    random_message_id = random.choice(list(channel_titles.keys()))
    channel_title = channel_titles[random_message_id]

    await interaction.response.send_message(f"Play this toybox: {channel_title}")

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

# Bot starten
if __name__ == "__main__":
    bot.run(TOKEN)
