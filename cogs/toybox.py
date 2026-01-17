import discord
from discord.ext import commands
from discord import app_commands
import math
import tempfile
import os
import zipfile
import re
import subprocess
import asyncio
import io
import config
from services.counters import ToyboxCounter
from services.rating_service import rating_service
from views.counting_views import CountingView
from views.rating_view import RatingView
from utils.logger import logger

class ToyboxCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.counter = bot.counter

    async def process_toybox_publication(self, interaction, table, record, progress_embed):
        """Helper method to process a single toybox publication."""
        try:
            # Extract fields
            fields = record.get('fields', {})
            post_id = record.get('id')
            title = fields.get('title', 'Untitled Post')
            description = fields.get('description', 'No description provided')
            creator_name = fields.get('creator', 'Unknown')
            video_link = fields.get('videolink', '')
            
            formatted_description = (
                f"{description}\n"
                "-------------------------------------\n"
                f"**:art:⎮Creator: {creator_name}**\n"
                f"**:film_frames:⎮Playthrough video:** {video_link}"
            )

            # Handle images
            image_files = []
            if 'images' in fields and fields['images']:
                progress_embed.set_field_at(0, name="Status", value=f"Downloading images for {title}...", inline=False)
                await interaction.edit_original_response(embed=progress_embed)
                
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    for idx, image in enumerate(fields['images']):
                        if isinstance(image, dict) and image.get('url'):
                            try:
                                async with session.get(image['url']) as resp:
                                    if resp.status == 200:
                                        data = await resp.read()
                                        filename = image.get('filename', f"image_{idx}.jpg")
                                        image_files.append(discord.File(io.BytesIO(data), filename=filename))
                            except Exception as e:
                                logger.error(f"Error downloading image: {e}")

            # Get forum channel
            forum_channel = self.bot.get_channel(config.FORUM_CHANNEL_ID)
            if not forum_channel:
                return False, "Forum channel not found!"
            
            progress_embed.set_field_at(0, name="Status", value=f"Creating thread for {title}...", inline=False)
            await interaction.edit_original_response(embed=progress_embed)
            
            # Create thread
            thread_with_message = await forum_channel.create_thread(
                name=title,
                content=formatted_description,
                files=image_files if image_files else None,
                reason=f"Post created via command by {interaction.user.name}"
            )
            
            thread = thread_with_message.thread
            starter_message = thread_with_message.message
            
            # Handle file attachment
            file_url = None
            if 'file' in fields and fields['file']:
                files_data = fields['file']
                if isinstance(files_data, list) and files_data:
                    file_url = files_data[0].get('url')
            
            if file_url:
                progress_embed.set_field_at(0, name="Status", value=f"Uploading attachment for {title}...", inline=False)
                await interaction.edit_original_response(embed=progress_embed)
                
                try:
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        async with session.get(file_url) as resp:
                            if resp.status == 200:
                                file_data = await resp.read()
                                filename = fields['file'][0].get('filename', 'attachment.file')
                                await thread.send(
                                    content="**:arrow_down: ⎮DOWNLOAD:**",
                                    file=discord.File(io.BytesIO(file_data), filename=filename)
                                )

                except Exception as e:
                    logger.error(f"Error uploading file: {e}")
                    await thread.send("⚠️ Failed to upload attachment file")

            # Update Airtable status
            try:
                table.update(post_id, {'Status': 'Published'})
            except Exception as e:
                logger.error(f"Error updating Airtable: {e}")

            return True, starter_message.jump_url
            
        except Exception as e:
            logger.error(f"Error in publication process: {e}")
            return False, str(e)

    @app_commands.command(name="post", description="Create a forum post from Airtable data")
    async def post(self, interaction: discord.Interaction, post_id: str, creator: str):
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
                title="📝 Creating Forum Post",
                description=f"Fetching data from {airtable_service.tables_map.get(creator, creator)} table",
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
                await interaction.edit_original_response(embed=discord.Embed(
                    title="❌ Error",
                    description=f"No record found with ID: {post_id}",
                    color=0xff0000
                ))
                return

            # Process publication
            success, result = await self.process_toybox_publication(interaction, table, record, progress_embed)
            
            if success:
                success_embed = discord.Embed(
                    title="✅ Toybox published",
                    description=f"Successfully published {post_id}",
                    color=0x00ff00
                )
                success_embed.add_field(name="Post", value=f"[Click to view]({result})", inline=False)
                await interaction.edit_original_response(embed=success_embed)
            else:
                await interaction.edit_original_response(embed=discord.Embed(title="❌ Error", description=result, color=0xff0000))
            
        except Exception as e:
            logger.error(f"Error in post command: {e}")
            await interaction.edit_original_response(embed=discord.Embed(title="❌ Error", description=str(e), color=0xff0000))

    @app_commands.command(name="post_batch", description="Publish all 'Ready to publish' toyboxes from a creator")
    async def post_batch(self, interaction: discord.Interaction, creator: str):
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
                title="📝 Batch Processing Toyboxes",
                description=f"Fetching 'Ready to publish' records from {airtable_service.tables_map.get(creator, creator)}...",
                color=0xec4e4e
            )
            progress_embed.add_field(name="Status", value="Retrieving data...", inline=False)
            await interaction.followup.send(embed=progress_embed)
            
            # Fetch ready records
            records = airtable_service.get_ready_records(creator)
            
            if not records:
                await interaction.edit_original_response(embed=discord.Embed(
                    title="⚠️ No Records Found",
                    description="No records found with status 'Ready to publish'.",
                    color=0xffaa00
                ))
                return
            
            total_records = len(records)
            published_links = []
            failed_records = []
            
            progress_embed.description = f"Found {total_records} toyboxes to publish."
            await interaction.edit_original_response(embed=progress_embed)
            
            for index, record in enumerate(records, 1):
                title = record.get('fields', {}).get('title', 'Untitled')
                progress_embed.set_field_at(0, name="Status", value=f"Processing {index}/{total_records}: {title}", inline=False)
                await interaction.edit_original_response(embed=progress_embed)
                
                success, result = await self.process_toybox_publication(interaction, table, record, progress_embed)
                
                if success:
                    published_links.append(f"✅ **{title}**: [View Post]({result})")
                else:
                    failed_records.append(f"❌ **{title}**: {result}")
                    
            # Final Summary
            summary_embed = discord.Embed(
                title="✅ Batch Processing Complete",
                description=f"Processed {total_records} toyboxes.",
                color=0x00ff00
            )
            
            # Split into chunks if too long (Discord limits)
            chunk_size = 1000
            published_text = "\n".join(published_links)
            if len(published_text) > chunk_size:
                 published_text = published_text[:chunk_size] + "... (truncated)"
            
            if published_links:
                summary_embed.add_field(name="Published", value=published_text, inline=False)
                
            if failed_records:
                failed_text = "\n".join(failed_records)
                if len(failed_text) > chunk_size:
                    failed_text = failed_text[:chunk_size] + "... (truncated)"
                summary_embed.add_field(name="Failed", value=failed_text, inline=False)
                summary_embed.color = 0xffaa00 # Change to orange if there were failures

            await interaction.edit_original_response(embed=summary_embed)

        except Exception as e:
            logger.error(f"Error in post_batch command: {e}")
            await interaction.edit_original_response(embed=discord.Embed(title="❌ Error", description=str(e), color=0xff0000))



    @app_commands.command(name="user", description="List all user ratings for a specific message.")
    async def user_ratings(self, interaction: discord.Interaction, message_id: str):
        try:
            msg_id_int = int(message_id)
        except ValueError:
            await interaction.response.send_message("Invalid Message ID", ephemeral=True)
            return

        if msg_id_int not in rating_service.message_ratings or not rating_service.message_ratings[msg_id_int]['ratings']:
            await interaction.response.send_message(f"No ratings available for message ID {message_id}.", ephemeral=True)
            return

        user_ratings_list = rating_service.message_ratings[msg_id_int]['ratings']
        rating_output = []
        for user_id, rating in user_ratings_list.items():
            rating_output.append(f"<@{user_id}>: {rating} ⭐️")
        
        ratings_message = "\n".join(rating_output)
        await interaction.response.send_message(f"Ratings for message ID {message_id}:\n{ratings_message}", ephemeral=True)



    @app_commands.command(name="change_metadata", description="Legacy: Use /edit_toybox_zip instead.")
    async def change_metadata(self, interaction: discord.Interaction, file: discord.Attachment):
        await interaction.response.send_message(
            "⚠️ **Deprecated Command**\n"
            "Please use `/edit_toybox_zip` for a much better, interactive experience! \n"
            "It allows you to edit Metadata (Name/Description) and Text Creators directly in Discord without downloading files.",
            ephemeral=True
        )

    @post.autocomplete('creator')
    async def post_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        from services.airtable_service import airtable_service
        choices = airtable_service.creator_choices
        return [
            choice for choice in choices
            if current.lower() in choice.name.lower()
        ][:25]

    @post_batch.autocomplete('creator')
    async def post_batch_autocomplete(self, interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        return await self.post_autocomplete(interaction, current)

    @app_commands.command(name="rate", description="Create a Toybox rating with stars.")
    async def rate(self, interaction: discord.Interaction):
        channel_id = interaction.channel_id
        
        message = await interaction.channel.send("Creating rating...")
        message_id = message.id

        # Initialize ratings
        if message_id not in rating_service.message_ratings:
            rating_service.message_ratings[message_id] = {'ratings': {}, 'average': 0, 'num_ratings': 0, 'channel_id': channel_id}

        embed = discord.Embed(
            title="Toybox rating: ⭐️⭐️⭐️⭐️⭐️",
            description="What do you think about this toybox?",
            color=discord.Color.blue()
        )
        embed.add_field(name="Average rating", value="No ratings yet.", inline=False)
        embed.add_field(name="Number of ratings", value="0 ratings yet.", inline=False)

        view = RatingView(message_id)
        await message.edit(content=None, embed=embed, view=view)
        await interaction.response.send_message("Rating created!", ephemeral=True)
        
        rating_service.channel_titles[str(message_id)] = interaction.channel.name
        rating_service.save_ratings()



    @app_commands.command(name="play_init", description="Start an interactive Toybox randomizer")
    async def play_init(self, interaction: discord.Interaction):
        from views.play_view import PlayView
        embed = discord.Embed(
            title="Random Toybox Selection",
            description=(
                "**Which Toybox should I play? Let us surprise you!** 🎁\n"
                "1. Choose how many random Toyboxes you would like to see (Dropdown Menu)\n"
                "2. Click on the button below and let the fun begin! 🎲"
            ),
            color=discord.Color.red()
        )
        view = PlayView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=False)

    @app_commands.command(name="top_of_the_week", description="Get 7 random top threads of the week from the forum")
    async def top_of_the_week(self, interaction: discord.Interaction):
        forum_channel = interaction.guild.get_channel(config.FORUM_CHANNEL_ID)
        if not forum_channel or not isinstance(forum_channel, discord.ForumChannel):
            await interaction.response.send_message("Error: Forum channel not found!", ephemeral=True)
            return

        # Load blacklist
        import json
        blacklist = []
        if os.path.exists(config.BLACKLIST_FILE):
            with open(config.BLACKLIST_FILE, "r") as f:
                blacklist = json.load(f)

        threads = [thread for thread in forum_channel.threads if str(thread.id) not in blacklist]
        if not threads:
            await interaction.response.send_message("No eligible threads found in the forum channel.", ephemeral=True)
            return

        import random
        selected_threads = random.sample(threads, min(7, len(threads)))
        message = "⭐ **TOP OF THE WEEK** ⭐\n\n"
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣"]
        
        for idx, thread in enumerate(selected_threads):
            message += f"{emojis[idx]} **{thread.name}**\n{thread.jump_url}\n\n"

        await interaction.response.send_message(message)

    @app_commands.command(name="blacklist_top_threads", description="Blacklist or unblacklist threads by their ID for top of the week ranking")
    @app_commands.describe(thread_id="The ID of the thread to blacklist or remove from blacklist (optional)")
    async def blacklist_top_threads(self, interaction: discord.Interaction, thread_id: str = None):
        import json
        blacklist = []
        if os.path.exists(config.BLACKLIST_FILE):
            with open(config.BLACKLIST_FILE, "r") as f:
                blacklist = json.load(f)
        
        if thread_id is None:
            if not isinstance(interaction.channel, discord.Thread):
                await interaction.response.send_message("❌ You must provide a thread ID or use this command inside a thread.", ephemeral=True)
                return
            thread_id = str(interaction.channel.id)
        
        if thread_id in blacklist:
            blacklist.remove(thread_id)
            with open(config.BLACKLIST_FILE, "w") as f:
                json.dump(blacklist, f)
            await interaction.response.send_message(f"✅ Removed thread `{thread_id}` from blacklist.", ephemeral=True)
        else:
            blacklist.append(thread_id)
            with open(config.BLACKLIST_FILE, "w") as f:
                json.dump(blacklist, f)
            await interaction.response.send_message(f"❌ Added thread `{thread_id}` to blacklist.", ephemeral=True)

    @app_commands.command(name="set_tag", description="Set a tag for this thread (use in destination thread)")
    @app_commands.choices(tag=[
        app_commands.Choice(name=tag, value=tag) for tag in config.VALID_TAGS
    ])
    async def set_tag(self, interaction: discord.Interaction, tag: str):
        await interaction.response.defer(ephemeral=True)
        
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.followup.send("❌ This command can only be used in a thread!", ephemeral=True)
            return
        
        thread_id = str(interaction.channel.id)
        
        try:
            import json
            with open(config.TOYBOX_DATA_FILE, "r", encoding='utf-8') as f:
                toybox_list = json.load(f)
            
            found = False
            for toybox in toybox_list:
                if str(toybox["id"]) == thread_id:
                    toybox["tags"] = [tag]
                    found = True
                    break
            
            if found:
                with open(config.TOYBOX_DATA_FILE, "w", encoding='utf-8') as f:
                    json.dump(toybox_list, f, indent=4, ensure_ascii=False)
                await interaction.followup.send(f"✅ Updated tag for this thread to {tag}", ephemeral=True)
            else:
                await interaction.followup.send("❌ Thread not found in database. Try running /update_toyboxes first", ephemeral=True)
                
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

    @app_commands.command(name="toybox_finder", description="Find Toyboxes by franchise")
    @app_commands.default_permissions(administrator=True)
    async def toybox_finder(self, interaction: discord.Interaction):
        from views.toybox_search_view import ToyboxView
        from services.rag_service import rag_service
        
        # Wrapper for search callback
        async def search_callback(category):
            return await rag_service.search_by_category(category)

        main_view = ToyboxView(search_callback)
        await interaction.response.send_message(
            embed=discord.Embed(
                title="🕹 Disney Infinity Toybox Explorer",
                description="Select your universe and explore incredible Toyboxes from your favorite franchise Toyboxes.",
                color=discord.Color.blue()
            ),
            view=main_view
        )

async def setup(bot):
    await bot.add_cog(ToyboxCommands(bot))
