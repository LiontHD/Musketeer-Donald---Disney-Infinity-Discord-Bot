import discord
from discord.ext import commands
from discord import app_commands
import os
import tempfile
import shutil
import asyncio
import zipfile
import io
import re
import zlib
import aiofiles
import config
from views.download_views import BrownbatDownloadView
from views.bundle_view import AddToBundleView
from utils.logger import logger

AUTHOREDNAME_PATTERN = r'AUTHOREDNAME\s*=\s*"([^"]+)"'
AUTHOREDDESC_PATTERN = r'AUTHOREDDESC\s*=\s*"([^"]+)"'
DATESTRING_PATTERN = r'DATESTRING\s*=\s*"([^"]+)"'
CONTENT_OFFSET = 84

class DownloadCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_bundle_sessions: dict[int, AddToBundleView] = {}  # user_id -> view

    @app_commands.command(name="brownbat_mod", description="Get download link for ThatBrownBat's Mod")
    @app_commands.describe(version="The version number (e.g., 1.0, 1.1)")
    async def brownbat(self, interaction: discord.Interaction, version: str):
        embed = discord.Embed(
            title="Brown Bat Mod Download",
            description="Welcome to Brown Bat Mod!\nDownload the expansion mod now! 🥳",
            color=0x8C142E
        )
        embed.set_footer(text=f"Made by That Brown Bat (v{version})")
        await interaction.response.send_message(embed=embed, view=BrownbatDownloadView())



    @app_commands.command(name="playstation_links", description="Zeigt Download-Links für PlayStation Savefiles an.")
    async def playstation_links(self, interaction: discord.Interaction):
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
            color=discord.Color.blue()
        )
        embed.set_footer(text="Diese Links sind für die EU-Version der PlayStation.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="360_to_pc", description="Convert Xbox 360 format files to PC format")
    @app_commands.describe(file="Upload a zip file containing Xbox 360 format files to convert")
    async def convert_360_to_pc(self, interaction: discord.Interaction, file: discord.Attachment):
        await self.process_conversion(interaction, file, "360toPC.py")

    @app_commands.command(name="wiiu_to_pc_converter", description="Convert wii u format files to PC format")
    @app_commands.describe(file="Upload a zip file containing wii u format files to convert")
    async def convert_wiiu_to_pc(self, interaction: discord.Interaction, file: discord.Attachment):
        await self.process_conversion(interaction, file, "360toPC.py")

    async def process_conversion(self, interaction: discord.Interaction, file: discord.Attachment, script_name: str):
        await interaction.response.defer()

        if not file or not file.filename.lower().endswith('.zip'):
            return await interaction.followup.send("Please upload a .zip file.")

        if file.size > 10 * 1024 * 1024:
            return await interaction.followup.send("File too large. Please upload a zip file smaller than 10MB.")
            
        original_filename = file.filename

        with tempfile.TemporaryDirectory() as temp_dir:
            input_zip_path = os.path.join(temp_dir, "input.zip")
            extract_dir = os.path.join(temp_dir, "extracted")
            output_zip_path = os.path.join(temp_dir, "converted.zip")
            
            os.makedirs(extract_dir, exist_ok=True)
            
            try:
                zip_content = await file.read()
                with open(input_zip_path, 'wb') as f:
                    f.write(zip_content)
                
                with zipfile.ZipFile(input_zip_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)
            except Exception as e:
                return await interaction.followup.send(f"Error processing zip file: {str(e)}")
            
            # Find target directory (handle nested folders)
            target_dir = extract_dir
            contents = os.listdir(extract_dir)
            if len(contents) == 1 and os.path.isdir(os.path.join(extract_dir, contents[0])):
                target_dir = os.path.join(extract_dir, contents[0])
            
            original_dir = os.getcwd()
            try:
                # Copy script
                script_path = os.path.join(original_dir, script_name)
                target_script_path = os.path.join(target_dir, script_name)
                shutil.copy2(script_path, target_script_path)
                
                os.chdir(target_dir)
                
                # Check for RR files
                files_before = os.listdir(target_dir)
                if not any("RR" in f for f in files_before):
                    os.chdir(original_dir)
                    return await interaction.followup.send("No matching *RR* files found.")
                
                # Run script
                process = await asyncio.create_subprocess_exec(
                    "python3", target_script_path, "*RR*", "*RR*",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                
                if process.returncode != 0:
                    os.chdir(original_dir)
                    return await interaction.followup.send(f"Error running conversion: {stderr.decode()}")
                
                os.chdir(original_dir)
                
                # Check output
                converted_dir = os.path.join(target_dir, "converted_files")
                if not os.path.exists(converted_dir) or not os.listdir(converted_dir):
                    return await interaction.followup.send("Conversion produced no files.")
                
                # Zip output
                with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_out:
                    for root, _, files in os.walk(converted_dir):
                        for file_name in files:
                            file_path = os.path.join(root, file_name)
                            arcname = os.path.relpath(file_path, converted_dir)
                            zip_out.write(file_path, arcname)
                
                # Send result
                with open(output_zip_path, 'rb') as f:
                    output_file = discord.File(fp=io.BytesIO(f.read()), filename=f"converted_{original_filename}")
                    await interaction.followup.send(
                        content="✅ Files converted successfully!",
                        file=output_file
                    )
                    
            except Exception as e:
                if os.getcwd() != original_dir:
                    os.chdir(original_dir)
                await interaction.followup.send(f"An error occurred: {str(e)}")

    @app_commands.command(name="batch_download_renumber", description="Download, filter, and renumber toyboxes from forum threads.")
    @app_commands.describe(
        number_sequence="Sequence of numbers (e.g. '1, 2, 15, 120').",
        limit="How many toyboxes to process (e.g. 10).",
        excluded_tags="Tags to exclude (comma separated).",
        google_drive_folder="Link to Google Drive folder (Not implemented yet)."
    )
    async def batch_download_renumber(self, interaction: discord.Interaction, number_sequence: str, limit: int, excluded_tags: str = None, google_drive_folder: str = None):
        await interaction.response.defer(ephemeral=True)

        # 1. Parse Inputs
        try:
            sequence = [int(x.strip()) for x in number_sequence.split(',') if x.strip().isdigit()]
        except ValueError:
            await interaction.followup.send("❌ Invalid number sequence format. Use: `1, 2, 15, 120`")
            return
            
        if limit > len(sequence):
            await interaction.followup.send(f"⚠️ Limit ({limit}) is higher than the provided numbers ({len(sequence)}). I will stop after {len(sequence)} files.")
            limit = len(sequence)

        excluded_tag_list = [t.strip().lower() for t in excluded_tags.split(',')] if excluded_tags else []

        # 2. Get Forum Channel
        forum_channel = interaction.guild.get_channel(config.FORUM_CHANNEL_ID)
        if not forum_channel or not isinstance(forum_channel, discord.ForumChannel):
            await interaction.followup.send("❌ Forum channel configuration error.")
            return

        # 3. Iterate Threads
        processed_count = 0
        zip_files_data = [] # List of (filename, file_content_bytes)

        # We need to sort threads maybe? For now, we take them in default order (usually recent activity)
        # or we might want to sort by creation date if the user expects a specific order.
        # However, the user didn't specify order, so we iterate as is.
        # Note: 'threads' property only has active threads. We might need archived ones too.
        # But fetching archived threads is an async generator.
        
        active_threads = forum_channel.threads
        
        progress_msg = await interaction.followup.send(f"🔍 Scanning threads (Active & Archived)... (Target: {limit})")

        found_threads = []
        
        # Function to process a list/iterator of threads
        async def process_thread_list(threads_iterable, is_async=False):
            nonlocal processed_count
            
            iterator = threads_iterable
            if is_async:
                # For async generators (archived_threads)
                async for thread in iterator:
                    if processed_count >= limit:
                        break
                    
                    if await check_thread(thread):
                        processed_count += 1
            else:
                # For standard lists (active_threads)
                for thread in iterator:
                    if processed_count >= limit:
                        break
                    
                    if await check_thread(thread):
                        processed_count += 1
                        
        async def check_thread(thread):
            # Check tags
            thread_tags = [t.name.lower() for t in thread.applied_tags]
            if any(ex_tag in thread_tags for ex_tag in excluded_tag_list):
                return False

            # Check for zip
            try:
                # If we have the message in cache, good. If not, fetch.
                # starter_message might be None if not cached.
                starter_msg = thread.starter_message
                if not starter_msg:
                    try:
                        starter_msg = await thread.fetch_message(thread.id)
                    except discord.NotFound:
                        return False
                
                if not starter_msg:
                    return False
                    
                zip_attachment = next((a for a in starter_msg.attachments if a.filename.lower().endswith('.zip')), None)
                if zip_attachment:
                    found_threads.append((thread.name, zip_attachment))
                    return True
            except Exception as e:
                logger.error(f"Error checking thread {thread.id}: {e}")
            return False

        # 1. Check Active Threads
        await process_thread_list(active_threads, is_async=False)
        
        # 2. Check Archived Threads (if limit not reached)
        if processed_count < limit:
            # Fetch archived threads
            # Note: archived_threads() returns an async iterator
            await process_thread_list(forum_channel.archived_threads(limit=None), is_async=True)

        
        if not found_threads:
            await interaction.followup.send("❌ No matching threads with ZIP files found.")
            return

        # 4. Process found threads
        await progress_msg.edit(content=f"⬇️ Found {len(found_threads)} threads. Downloading and processing...")
        import collections 
        
        # Temp dir for processing
        with tempfile.TemporaryDirectory() as temp_dir:
            merged_dir = os.path.join(temp_dir, "merged_output")
            os.makedirs(merged_dir, exist_ok=True)
            
            success_count = 0
            
            async with aiohttp.ClientSession() as session:
                for idx, (thread_name, attachment) in enumerate(found_threads):
                    if idx >= len(sequence):
                        break
                        
                    new_number = sequence[idx]
                    
                    try:
                        # Download
                        async with session.get(attachment.url) as resp:
                            if resp.status != 200:
                                continue
                            data = await resp.read()
                        
                        # Extract and Renumber
                        with zipfile.ZipFile(io.BytesIO(data)) as zf:
                            for file_info in zf.infolist():
                                if file_info.filename.endswith('/'):
                                    continue
                                
                                # Read content
                                content = zf.read(file_info.filename)
                                original_name = os.path.basename(file_info.filename)
                                
                                # Renumber logic
                                # Be more flexible: Look for the pattern [A-Z]+[Digits] anywhere in the string, 
                                # but usually we want to target the LAST occurrence if there are multiple?
                                # Or specifically look for common patterns like SRR#, EHRR#, BIN#?
                                # Let's try to match [Any Prefix]([A-Z]+)(\d+)(.*)
                                
                                # New Regex: Match standard toybox patterns
                                # Cases: "SRR1.txt", "MyFile_SRR1.txt", "DATA_1.bin" (maybe not data)
                                # Let's stick to the user's implicit requirement: Rename the ID part.
                                # Safe bet: Look for "SRR", "EHRR", "SCCA" etc followed by digits.
                                
                                match = re.search(r'([A-Z]+)(\d+)(\.[^.]+)$', original_name)
                                if match:
                                    prefix_part, old_num, ext = match.groups()
                                    # Use substring replacement to keep the rest of the filename intact?
                                    # Actually, usually we just want to replace the number associated with that ID.
                                    # Construct new name
                                    # If original is "JAILHOUSE_SRS5.bin": match might qualify if SRS is known?
                                    # Actually the "SRS" part IS the prefix.
                                    
                                    # Let's try a safer replacement: replace the digits in the match
                                    new_name = original_name[:match.start(2)] + str(new_number) + original_name[match.end(2):]
                                else:
                                    # Fallback: try strictly replacing digits at end of name before extension?
                                    pass
                                
                                # Write to merged folder
                                # Handle collisions? If two zips have "SRR1", we are renumbering them to different numbers
                                # "SRR{seq[0]}", "SRR{seq[1]}"...
                                # So collisions shouldn't happen unless specific files inside zip don't follow pattern
                                
                                with open(os.path.join(merged_dir, new_name), 'wb') as f:
                                    f.write(content)
                        
                        success_count += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing {thread_name}: {e}")
                        continue

            # 5. Zip Result
            await progress_msg.edit(content=f"📦 Zipping {success_count} processed toyboxes...")
            
            output_zip_path = os.path.join(temp_dir, "batch_renumbered.zip")
            with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(merged_dir):
                    for file in files:
                        zf.write(os.path.join(root, file), file)
            
            # 6. Send
            file_size = os.path.getsize(output_zip_path)
            if file_size < 25 * 1024 * 1024:
                await interaction.followup.send(
                    f"✅ Processed **{success_count}** toyboxes!",
                    file=discord.File(output_zip_path, filename="batch_renumbered.zip")
                )
            else:
                await interaction.followup.send(
                    f"✅ Processed **{success_count}** toyboxes!\n"
                    f"⚠️ The resulting file is **{file_size / (1024*1024):.2f} MB**, which works for me but might be too big for Discord limits on some requests.\n"
                    f"Google Drive upload is not currently configured locally."
                )

    @batch_download_renumber.autocomplete('excluded_tags')
    async def tags_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        # Fetch actual tags from the forum channel
        forum_channel = interaction.guild.get_channel(config.FORUM_CHANNEL_ID)
        available_tags = []
        if forum_channel and isinstance(forum_channel, discord.ForumChannel):
            available_tags = [tag.name for tag in forum_channel.available_tags]
        else:
            available_tags = config.VALID_TAGS

        # Multi-tag logic
        if ',' in current:
            parts = [p.strip() for p in current.split(',')]
            completed_tags = parts[:-1]
            current_fragment = parts[-1].lower()
            
            # Filter tags that match fragment and aren't already selected
            options = []
            for tag in available_tags:
                if current_fragment in tag.lower() and tag not in completed_tags:
                    # Construct value: "Tag1, Tag2, NewTag"
                    full_value = ", ".join(completed_tags + [tag])
                    options.append(app_commands.Choice(name=full_value, value=full_value))
            return options[:25]
        else:
            # Single tag logic
            return [
                app_commands.Choice(name=tag, value=tag)
                for tag in available_tags 
                if current.lower() in tag.lower()
            ][:25]

    @app_commands.command(name="toybox_to_toybox_game", description="Convert toybox files in a ZIP and optionally change their number")
    @app_commands.describe(zip_file="Upload a ZIP file containing toybox files", new_number="Optional: New number for the toybox files (0-300)")
    async def toybox_to_toybox_game(self, interaction: discord.Interaction, zip_file: discord.Attachment, new_number: int = None):
        if new_number is not None and not (0 <= new_number <= 300):
            await interaction.response.send_message("The number must be between 0 and 300!", ephemeral=True)
            return

        if not zip_file.filename.endswith('.zip'):
            await interaction.response.send_message("Please upload a ZIP file!", ephemeral=True)
            return

        await interaction.response.defer()

        try:
            zip_content = await zip_file.read()
            input_zip = zipfile.ZipFile(io.BytesIO(zip_content))
            
            output_zip_buffer = io.BytesIO()
            output_zip = zipfile.ZipFile(output_zip_buffer, 'w', zipfile.ZIP_DEFLATED)
            
            folder_name = None
            for name in input_zip.namelist():
                if name.endswith('/'):
                    folder_name = name
                    break
            
            if not folder_name:
                # If no folder, create one based on filename
                folder_name = zip_file.filename.replace('.zip', '') + '/'

            for file_info in input_zip.infolist():
                if file_info.filename.endswith('/'):
                    continue
                    
                filename = os.path.basename(file_info.filename)
                new_filename = filename
                
                # Regex to parse the filename: Prefix + Number + Suffix
                match = re.search(r'([A-Z]+)(\d+)(.*)', filename)
                
                if match:
                    prefix_part, num_part, suffix_part = match.groups()
                    
                    # 1. Change 'R' in the prefix to 'A' (only if it ends with R)
                    # "Reverse the process" of toybox_game_to_toybox which did A->R
                    if prefix_part.endswith('R'):
                        prefix_part = prefix_part[:-1] + 'A'
                    
                    # 2. Change number if provided
                    if new_number is not None:
                        num_part = str(new_number)
                        
                    new_filename = f"{prefix_part}{num_part}{suffix_part}"
                
                # Add to new zip
                file_content = input_zip.read(file_info.filename)
                output_zip.writestr(folder_name + new_filename, file_content)
            
            input_zip.close()
            output_zip.close()
            output_zip_buffer.seek(0)
            
            await interaction.followup.send(
                "✅ Conversion complete!",
                file=discord.File(output_zip_buffer, filename=f"converted_{zip_file.filename}")
            )
            
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {str(e)}")

    @app_commands.command(name="toybox_game_to_toybox", description="Convert a toybox game ZIP back to a regular toybox format")
    async def toybox_game_to_toybox(self, interaction: discord.Interaction, zip_file: discord.Attachment, new_number: int = None):
        if new_number is not None and not (0 <= new_number <= 300):
            await interaction.response.send_message("The number must be between 0 and 300!", ephemeral=True)
            return
            
        if not zip_file.filename.endswith('.zip'):
            await interaction.response.send_message("Please upload a ZIP file!", ephemeral=True)
            return
            
        await interaction.response.defer()
        
        try:
            zip_content = await zip_file.read()
            input_zip = zipfile.ZipFile(io.BytesIO(zip_content))
            output_zip_buffer = io.BytesIO()
            output_zip = zipfile.ZipFile(output_zip_buffer, 'w', zipfile.ZIP_DEFLATED)
            
            # Determine folder name
            folder_name = None
            for name in input_zip.namelist():
                if name.endswith('/'):
                    folder_name = name
                    break
            if not folder_name:
                folder_name = zip_file.filename.replace('.zip', '') + '/'
                
            for file_info in input_zip.infolist():
                if file_info.filename.endswith('/'):
                    continue
                    
                filename = os.path.basename(file_info.filename)
                
                # Skip macOS metadata files
                if '__MACOSX' in file_info.filename or filename.startswith('._'):
                    continue

                new_filename = filename
                
                # Regex to parse the filename: Prefix + Number + Suffix
                # e.g., "SHRA5A" -> Prefix="SHRA", Num="5", Suffix="A"
                match = re.match(r'([A-Z]+)(\d+)(.*)', filename)
                
                if match:
                    prefix_part, num_part, suffix_part = match.groups()
                    
                    # 1. Change 'A' in the prefix to 'R' (only if it ends with A)
                    if prefix_part.endswith('A'):
                        prefix_part = prefix_part[:-1] + 'R'
                    
                    # 2. Change number if provided
                    if new_number is not None:
                        num_part = str(new_number)
                        
                    new_filename = f"{prefix_part}{num_part}{suffix_part}"

                file_content = input_zip.read(file_info.filename)
                output_zip.writestr(folder_name + new_filename, file_content)
                
            input_zip.close()
            output_zip.close()
            output_zip_buffer.seek(0)
            
            await interaction.followup.send(
                "✅ Conversion complete!",
                file=discord.File(output_zip_buffer, filename=f"converted_{zip_file.filename}")
            )
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {str(e)}")

    @app_commands.command(name="change_number", description="Change the number in toybox or toybox game files inside a ZIP")
    async def change_number(self, interaction: discord.Interaction, zip_file: discord.Attachment, new_number: int):
        if not (1 <= new_number <= 300):
            await interaction.response.send_message("The number must be between 1 and 300!", ephemeral=True)
            return
            
        if not zip_file.filename.endswith('.zip'):
            await interaction.response.send_message("Please upload a ZIP file!", ephemeral=True)
            return
            
        await interaction.response.defer()
        
        try:
            zip_content = await zip_file.read()
            input_zip = zipfile.ZipFile(io.BytesIO(zip_content))
            output_zip_buffer = io.BytesIO()
            output_zip = zipfile.ZipFile(output_zip_buffer, 'w', zipfile.ZIP_DEFLATED)
            
            folder_name = None
            for name in input_zip.namelist():
                if name.endswith('/'):
                    folder_name = name
                    break
            if not folder_name:
                folder_name = zip_file.filename.replace('.zip', '') + '/'
                
            for file_info in input_zip.infolist():
                if file_info.filename.endswith('/'):
                    continue
                    
                filename = os.path.basename(file_info.filename)
                new_filename = filename
                
                match = re.match(r'([A-Z]+)(\d+)(.*)', filename)
                if match:
                    prefix, num, suffix = match.groups()
                    new_filename = f"{prefix}{new_number}{suffix}"
                    
                file_content = input_zip.read(file_info.filename)
                output_zip.writestr(folder_name + new_filename, file_content)
                
            input_zip.close()
            output_zip.close()
            output_zip_buffer.seek(0)
            
            await interaction.followup.send(
                f"✅ Number changed to {new_number}!",
                file=discord.File(output_zip_buffer, filename=f"renumbered_{zip_file.filename}")
            )
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {str(e)}")

    @app_commands.command(name="batch_change_number", description="Changes numbers in multiple toybox ZIP files at once.")
    @app_commands.describe(
        numbers="A comma-separated list of new numbers (e.g., '300,256,288'). Order must match files.",
        file1="The first ZIP file.",
        file2="The second ZIP file (optional).",
        file3="The third ZIP file (optional).",
        file4="The fourth ZIP file (optional)."
    )
    async def batch_change_number(self, interaction: discord.Interaction, numbers: str, file1: discord.Attachment, file2: discord.Attachment = None, file3: discord.Attachment = None, file4: discord.Attachment = None):
        files = [f for f in [file1, file2, file3, file4] if f]
        num_list = [n.strip() for n in numbers.split(',')]
        
        if len(files) != len(num_list):
            await interaction.response.send_message("❌ Number of files and numbers must match!", ephemeral=True)
            return
            
        await interaction.response.defer()
        
        try:
            processed_files = []
            for idx, file in enumerate(files):
                new_number = int(num_list[idx])
                zip_content = await file.read()
                input_zip = zipfile.ZipFile(io.BytesIO(zip_content))
                output_zip_buffer = io.BytesIO()
                output_zip = zipfile.ZipFile(output_zip_buffer, 'w', zipfile.ZIP_DEFLATED)
                
                folder_name = None
                for name in input_zip.namelist():
                    if name.endswith('/'):
                        folder_name = name
                        break
                if not folder_name:
                    folder_name = file.filename.replace('.zip', '') + '/'
                    
                for file_info in input_zip.infolist():
                    if file_info.filename.endswith('/'):
                        continue
                    filename = os.path.basename(file_info.filename)
                    new_filename = filename
                    match = re.match(r'([A-Z]+)(\d+)(.*)', filename)
                    if match:
                        prefix, num, suffix = match.groups()
                        new_filename = f"{prefix}{new_number}{suffix}"
                    file_content = input_zip.read(file_info.filename)
                    output_zip.writestr(folder_name + new_filename, file_content)
                    
                input_zip.close()
                output_zip.close()
                output_zip_buffer.seek(0)
                processed_files.append(discord.File(output_zip_buffer, filename=f"renumbered_{file.filename}"))
                
            await interaction.followup.send("✅ Batch processing complete!", files=processed_files)
            
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {str(e)}")

    @app_commands.command(name="meta", description="Extracts metadata from ZIP, EHRR or EHRA file.")
    async def meta(self, interaction: discord.Interaction, ehr_file: discord.Attachment):
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                file_path = f"{temp_dir}/{ehr_file.filename}"
                
                async with aiofiles.open(file_path, 'wb') as f:
                    await f.write(await ehr_file.read())
                
                extracted_file_path = None
                
                if ehr_file.filename.endswith(".zip"):
                    with zipfile.ZipFile(file_path, 'r') as zip_ref:
                        zip_ref.extractall(temp_dir)
                        for root, _, files in os.walk(temp_dir):
                            for file in files:
                                if file.startswith("EHRR") or file.startswith("EHRA"):
                                    extracted_file_path = os.path.join(root, file)
                                    break
                            if extracted_file_path:
                                break
                else:
                    extracted_file_path = file_path
                
                if not extracted_file_path:
                    await interaction.response.send_message("No valid EHRR or EHRA file found in the ZIP!", ephemeral=True)
                    return
                
                async with aiofiles.open(extracted_file_path, 'rb') as f:
                    file_bytes = await f.read()
                    
                decompressed_data = zlib.decompress(file_bytes[CONTENT_OFFSET:]).decode('utf-8').rstrip('\x00')
                
                auth_name_match = re.search(AUTHOREDNAME_PATTERN, decompressed_data)
                auth_desc_match = re.search(AUTHOREDDESC_PATTERN, decompressed_data)
                date_string_match = re.search(DATESTRING_PATTERN, decompressed_data)
                
                metadata_text = "**Metadata Extracted:**\n"
                if auth_name_match:
                    metadata_text += f"**Name:** {auth_name_match.group(1)}\n"
                if auth_desc_match:
                    metadata_text += f"**Description:** {auth_desc_match.group(1)}\n"
                if date_string_match:
                    metadata_text += f"**Date:** {date_string_match.group(1)}\n"
                
                if not (auth_name_match or auth_desc_match or date_string_match):
                    metadata_text = "No metadata found in the file."
                
                await interaction.response.send_message(metadata_text)
        
        except zipfile.BadZipFile:
            await interaction.response.send_message("Error: Invalid ZIP file!", ephemeral=True)
        except zlib.error:
            await interaction.response.send_message("Error: Could not decompress the file!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An error occurred: {str(e)}", ephemeral=True)

    @app_commands.command(name="add_to_bundle", description="Collect toyboxes from Discord threads and create a renumbered bundle.")
    @app_commands.describe(numbers="Comma-separated sequence of numbers (e.g., '243, 244, 246, 248')")
    async def add_to_bundle(self, interaction: discord.Interaction, numbers: str):
        # Parse numbers
        try:
            number_sequence = [int(n.strip()) for n in numbers.split(',') if n.strip()]
        except ValueError:
            await interaction.response.send_message(
                "❌ Invalid number format. Use comma-separated integers like: `1, 2, 3, 10`",
                ephemeral=True
            )
            return

        # Validate range
        for num in number_sequence:
            if not (0 <= num <= 300):
                await interaction.response.send_message(
                    f"❌ Number `{num}` is out of range. All numbers must be between 0 and 300.",
                    ephemeral=True
                )
                return

        if not number_sequence:
            await interaction.response.send_message("❌ Please provide at least one number.", ephemeral=True)
            return

        # Check for existing session
        if interaction.user.id in self.active_bundle_sessions:
            await interaction.response.send_message(
                "⚠️ You already have an active bundle session. Please complete or cancel it first.",
                ephemeral=True
            )
            return

        # Create view and send
        view = AddToBundleView(number_sequence, interaction.user.id, self)
        embed = view.create_embed()
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

        # Register session
        self.active_bundle_sessions[interaction.user.id] = view

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listens for thread links from users with active bundle sessions."""
        if message.author.bot:
            return

        if message.author.id not in self.active_bundle_sessions:
            return

        view = self.active_bundle_sessions[message.author.id]
        if view.is_processing or view.is_cancelled:
            return

        # Check if message contains Discord thread links
        # Pattern: https://discord.com/channels/{guild_id}/{thread_id}
        pattern = r'https://discord\.com/channels/(\d+)/(\d+)'
        matches = re.findall(pattern, message.content)

        added_count = 0
        for guild_id, thread_id in matches:
            if view.add_link(int(thread_id)):
                added_count += 1

        if added_count > 0:
            await view.update_embed()
            try:
                await message.add_reaction('✅')
            except discord.Forbidden:
                pass

    def cog_unload(self):
        """Cleanup when cog is unloaded."""
        self.active_bundle_sessions.clear()

async def setup(bot):
    await bot.add_cog(DownloadCommands(bot))

