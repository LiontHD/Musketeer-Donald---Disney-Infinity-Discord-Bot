import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio
import tempfile
import shutil
import zipfile
import io
import re
import zlib
import aiohttp
import aiofiles
from discord import ForumChannel
import config
from views.ask_toybox_view import AskToyboxPanelView
from views.rating_view import RatingView
from services.rating_service import rating_service
from services.tag_analyzer import SimpleTagAnalyzer
from services.counters import SlotCounter
from utils.logger import logger

AUTHOREDNAME_PATTERN = r'AUTHOREDNAME\s*=\s*"([^"]+)"'
AUTHOREDDESC_PATTERN = r'AUTHOREDDESC\s*=\s*"([^"]+)"'
DATESTRING_PATTERN = r'DATESTRING\s*=\s*"([^"]+)"'
CONTENT_OFFSET = 84

class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="create_ask_panel", description="ADMIN: Creates the panel to start an AI Toybox chat.")
    @app_commands.checks.has_permissions(administrator=True)
    async def create_ask_panel(self, interaction: discord.Interaction):
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

    @app_commands.command(name="clean_threads", description=f"ADMIN: Deletes all threads in the musketeer-donald channel.")
    @app_commands.checks.has_permissions(administrator=True)
    async def purge_target_channel_threads(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        if not interaction.guild:
            await interaction.followup.send("This command can only be used in a server.", ephemeral=True)
            return

        target_channel = interaction.guild.get_channel(config.TARGET_PURGE_CHANNEL_ID)

        if not target_channel:
            await interaction.followup.send(
                f"Error: The predefined target channel (ID: {config.TARGET_PURGE_CHANNEL_ID}) was not found in this server.",
                ephemeral=True
            )
            return

        if not isinstance(target_channel, (discord.TextChannel, discord.ForumChannel)):
            await interaction.followup.send(
                f"Error: The predefined target channel (ID: {config.TARGET_PURGE_CHANNEL_ID}) is not a text or forum channel.",
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
            logger.error(f"Permission error: Could not fetch general archived threads for {target_channel.name} ({target_channel.id}).")
        except Exception as e:
            logger.error(f"Error fetching general archived threads for {target_channel.name} ({target_channel.id}): {e}")

        if isinstance(target_channel, discord.TextChannel):
            try:
                async for thread_obj in target_channel.archived_threads(private=True, limit=None):
                     all_threads_map[thread_obj.id] = thread_obj
            except discord.Forbidden:
                logger.error(f"Permission error: Could not fetch private archived threads for TextChannel {target_channel.name} ({target_channel.id}).")
            except Exception as e:
                logger.error(f"Error fetching private archived threads for TextChannel {target_channel.name} ({target_channel.id}): {e}")

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
                logger.error(f"Permission error: Could not delete thread '{thread_obj_to_delete.name}' ({thread_obj_to_delete.id}).")
            except discord.HTTPException as e:
                failed_count += 1
                logger.error(f"HTTP error: Failed to delete thread '{thread_obj_to_delete.name}' ({thread_obj_to_delete.id}): {e.status} - {e.text}")
            except Exception as e:
                failed_count +=1
                logger.error(f"Generic error: Failed to delete thread '{thread_obj_to_delete.name}' ({thread_obj_to_delete.id}): {type(e).__name__} - {e}")

        result_message = f"Operation complete for {target_channel.mention}:\n"
        result_message += f"Successfully deleted: {deleted_count} threads.\n"
        if failed_count > 0:
            result_message += f"Failed to delete: {failed_count} threads. Check console logs for details."
        
        if len(result_message) > 2000:
            result_message = result_message[:1990] + "... (truncated)"
            
        await interaction.edit_original_response(content=result_message)

    @app_commands.command(name="update_toyboxes", description="ADMIN: Manually update the toybox search database.")
    @app_commands.checks.has_permissions(administrator=True)
    async def update_toyboxes_cmd(self, interaction: discord.Interaction):
        if not interaction.guild:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        from services.toybox_service import toybox_service
        try:
            result = await toybox_service.update_toybox_database(interaction.guild)
            
            # handle both old (int) and new (tuple) return types safely
            if isinstance(result, tuple):
                count, ingested_count = result
                msg = f"✅ Database update complete.\n- 📄 **JSON DB:** {count} total entries.\n- 🧠 **Vector DB:** {ingested_count} new entries ingested."
            else:
                count = result
                msg = f"✅ Toybox database update complete. ({count} entries processed)."

            await interaction.followup.send(msg, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"⚠️ Failed to update database: {e}", ephemeral=True)



    @app_commands.command(name="edit", description="Edit ratings for a specific message.")
    async def edit_ratings(self, interaction: discord.Interaction, message_id: str, user_to_remove: str):
        try:
            message_id_int = int(message_id)
            user_to_remove_int = int(user_to_remove)
        except ValueError:
            await interaction.response.send_message("Invalid ID format.", ephemeral=True)
            return

        # Check if message exists in ratings
        if message_id_int not in rating_service.message_ratings:
             await interaction.response.send_message(f"No ratings available for message ID {message_id}.", ephemeral=True)
             return

        # Check if user voted
        if user_to_remove_int in rating_service.message_ratings[message_id_int]['ratings']:
            del rating_service.message_ratings[message_id_int]['ratings'][user_to_remove_int]
            rating_service.message_ratings[message_id_int]['num_ratings'] -= 1
            rating_service.update_average_rating(message_id_int)
            rating_service.save_ratings()
            
            await interaction.response.send_message(f"Removed user <@{user_to_remove}> from the ratings.", ephemeral=True)
            
            # Update embed
            try:
                message = await interaction.channel.fetch_message(message_id_int)
                view = RatingView(message_id_int)
                await view.update_rating_embed(message, message_id_int)
            except discord.NotFound:
                pass
        else:
            await interaction.response.send_message(f"User ID <@{user_to_remove}> has not voted on this message.", ephemeral=True)

    @app_commands.command(name="batch_infos", description="Extracts metadata from ZIP files for all records in a specified creator's table")
    @app_commands.default_permissions(administrator=True)
    async def batch_infos(self, interaction: discord.Interaction, creator: str):
        await interaction.response.defer()
        
        try:
            from services.airtable_service import airtable_service
            
            # Check if table exists
            table = airtable_service.get_table(creator)
            if not table:
                # Try to find by name if key failed
                found = False
                for key, name in airtable_service.tables_map.items():
                    if name.lower() == creator.lower() or key == creator.lower():
                        table = airtable_service.get_table(key)
                        creator = key # Update to key
                        found = True
                        break
                if not found:
                    await interaction.followup.send(f"❌ Unknown creator/table: {creator}", ephemeral=True)
                    return

            # Create initial progress embed
            progress_embed = discord.Embed(
                title="📝 Batch Metadata Extraction",
                description=f"Processing all records from {airtable_service.tables_map.get(creator, creator)} table",
                color=0xec4e4e
            )
            progress_embed.add_field(name="Status", value="Starting batch process...", inline=False)
            message = await interaction.followup.send(embed=progress_embed)
            
            # Fetch all records from the table
            records = table.all()
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
                            table.update(record['id'], update_fields)
                            success += 1
                        else:
                            failed += 1

                except Exception as e:
                    failed += 1
                    continue

            # Create final success embed
            final_embed = discord.Embed(
                title="✅ Batch Processing Complete",
                description=f"Processed {total_records} records from {airtable_service.tables_map.get(creator, creator)} table",
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

    @batch_infos.autocomplete('creator')
    async def batch_infos_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        from services.airtable_service import airtable_service
        choices = airtable_service.creator_choices
        return [
            choice for choice in choices
            if current.lower() in choice.name.lower()
        ][:25]

    @app_commands.command(name="infos", description="Extracts metadata from ZIP file in Airtable and updates the record")
    @app_commands.default_permissions(administrator=True)
    async def infos(self, interaction: discord.Interaction, post_id: str, creator: str):
        await interaction.response.defer()
        
        try:
            from services.airtable_service import airtable_service
            
            # Check if table exists
            table = airtable_service.get_table(creator)
            if not table:
                # Try to find by name if key failed
                found = False
                for key, name in airtable_service.tables_map.items():
                    if name.lower() == creator.lower() or key == creator.lower():
                        table = airtable_service.get_table(key)
                        creator = key # Update to key
                        found = True
                        break
                if not found:
                    await interaction.followup.send(f"❌ Unknown creator/table: {creator}", ephemeral=True)
                    return

            # Create initial progress embed
            progress_embed = discord.Embed(
                title="📝 Extracting Metadata",
                description=f"Fetching data for ID: {post_id} from {airtable_service.tables_map.get(creator, creator)} table",
                color=0xec4e4e
            )
            progress_embed.add_field(name="Status", value="Retrieving data from Airtable...", inline=False)
            await interaction.followup.send(embed=progress_embed)
            
            # Fetch record
            try:
                record = table.get(post_id)
            except Exception:
                record = None
                
            if not record:
                error_embed = discord.Embed(
                    title="❌ Error",
                    description=f"No record found with ID: {post_id}",
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
                progress_embed.set_field_at(0, name="Status", value="Downloading ZIP file...", inline=False)
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
                progress_embed.set_field_at(0, name="Status", value="Extracting metadata...", inline=False)
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
                    progress_embed.set_field_at(0, name="Status", value="Updating Airtable record...", inline=False)
                    await interaction.edit_original_response(embed=progress_embed)
                    
                    # Update Airtable
                    table.update(post_id, update_fields)

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

    @infos.autocomplete('creator')
    async def infos_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        from services.airtable_service import airtable_service
        choices = airtable_service.creator_choices
        return [
            choice for choice in choices
            if current.lower() in choice.name.lower()
        ][:25]



    @app_commands.command(name="count_total_toyboxes", description="ADMIN: Counts all toyboxes in the forum channel by scanning zip files.")
    @app_commands.default_permissions(administrator=True)
    async def count_total_toyboxes(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        
        forum_channel = interaction.guild.get_channel(config.FORUM_CHANNEL_ID)
        if not isinstance(forum_channel, discord.ForumChannel):
            await interaction.followup.send(f"❌ Configured channel {config.FORUM_CHANNEL_ID} is not a Forum Channel.", ephemeral=True)
            return

        status_embed = discord.Embed(
            title="📊 Total Toybox Count",
            description="Starting scan of all threads...",
            color=discord.Color.blue()
        )
        status_message = await interaction.followup.send(embed=status_embed)

        total_threads = 0
        processed_threads = 0
        total_toyboxes = 0
        failed_threads = 0
        
        # Collect all threads (active and archived)
        all_threads = []
        try:
            # Active threads
            for thread in forum_channel.threads:
                all_threads.append(thread)
            
            # Archived threads
            async for thread in forum_channel.archived_threads(limit=None):
                all_threads.append(thread)
                
        except Exception as e:
            await interaction.followup.send(f"❌ Error fetching threads: {e}", ephemeral=True)
            return

        total_threads = len(all_threads)
        status_embed.description = f"Found {total_threads} threads. Processing..."
        await status_message.edit(embed=status_embed)

        for thread in all_threads:
            processed_threads += 1
            
            # Update status every 10 threads
            if processed_threads % 10 == 0:
                status_embed.description = f"Processing thread {processed_threads}/{total_threads}...\nCurrent Count: {total_toyboxes}"
                await status_message.edit(embed=status_embed)

            try:
                # Scan the first 5 messages of the thread for zip files
                messages_scanned = 0
                zip_found_in_thread = False
                
                async for message in thread.history(limit=5, oldest_first=True):
                    messages_scanned += 1
                    if not message.attachments:
                        continue

                    for attachment in message.attachments:
                        if attachment.filename.lower().endswith('.zip'):
                            logger.info(f"Thread {thread.id}: Found zip {attachment.filename} in message {message.id}")
                            
                            # Download zip
                            zip_data = await attachment.read()
                            
                            # Count SRR files using existing service
                            count = self.bot.counter.count_srr_files(zip_data, attachment.filename)
                            
                            if count > 0:
                                total_toyboxes += count
                                zip_found_in_thread = True
                                logger.info(f"Thread {thread.id}: Counted {count} toyboxes in {attachment.filename}")
                            
                if not zip_found_in_thread:
                     logger.info(f"Thread {thread.id}: No zip file found in first {messages_scanned} messages.")

            except Exception as e:
                failed_threads += 1
                logger.error(f"Error processing thread {thread.id}: {e}")

        # Final Report
        from utils.ascii_numbers import get_big_number
        ascii_count = get_big_number(total_toyboxes)
        
        final_embed = discord.Embed(
            title="✅ Toybox Count Complete",
            description=f"Scanned {total_threads} threads in {forum_channel.mention}.",
            color=discord.Color.green()
        )
        final_embed.add_field(name="Total Toyboxes", value=f"```\n{ascii_count}\n```", inline=False)
        final_embed.add_field(name="Threads Processed", value=str(processed_threads), inline=True)
        final_embed.add_field(name="Failed/Skipped", value=str(failed_threads), inline=True)
        
        await status_message.edit(embed=final_embed)

async def setup(bot):
    await bot.add_cog(AdminCommands(bot))
