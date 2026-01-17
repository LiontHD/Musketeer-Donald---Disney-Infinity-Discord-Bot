import discord
from discord import ui
import re
import asyncio
import zipfile
import io
import os
import tempfile
import aiohttp
from utils.logger import logger


class AddToBundleView(ui.View):
    """View for the Add to Bundle command. Collects thread links and processes them."""

    def __init__(self, number_sequence: list[int], user_id: int, cog):
        super().__init__(timeout=600)  # 10 minute timeout
        self.number_sequence = number_sequence
        self.user_id = user_id
        self.cog = cog
        self.collected_thread_ids: list[int] = []
        self.message: discord.Message = None
        self.is_processing = False
        self.is_cancelled = False

    def create_embed(self) -> discord.Embed:
        """Creates the status embed."""
        embed = discord.Embed(
            title="📦 Add to Bundle",
            description=(
                "Paste Discord thread links in this channel.\n"
                "I will collect ZIP files from each thread.\n\n"
                "**Format:** `https://discord.com/channels/.../thread_id`"
            ),
            color=discord.Color.blue()
        )
        embed.add_field(
            name="📊 Status",
            value=f"**Links collected:** {len(self.collected_thread_ids)}\n"
                  f"**Numbers available:** {len(self.number_sequence)}",
            inline=False
        )
        
        if len(self.collected_thread_ids) >= len(self.number_sequence):
            embed.add_field(
                name="⚠️ Limit Reached",
                value="You have collected as many links as numbers provided. "
                      "Press **Create Bundle** to process.",
                inline=False
            )
        
        return embed

    async def update_embed(self):
        """Updates the message embed with current status."""
        if self.message:
            try:
                await self.message.edit(embed=self.create_embed(), view=self)
            except discord.NotFound:
                pass

    def add_link(self, thread_id: int) -> bool:
        """Adds a thread ID if not already present. Returns True if added."""
        if thread_id in self.collected_thread_ids:
            return False
        if len(self.collected_thread_ids) >= len(self.number_sequence):
            return False
        self.collected_thread_ids.append(thread_id)
        return True

    @ui.button(label="Create Bundle", style=discord.ButtonStyle.green, custom_id="create_bundle_btn", row=0)
    async def create_bundle_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your session!", ephemeral=True)
            return

        if not self.collected_thread_ids:
            await interaction.response.send_message("No links collected yet!", ephemeral=True)
            return

        if self.is_processing:
            await interaction.response.send_message("Already processing!", ephemeral=True)
            return

        self.is_processing = True
        self.stop()  # Stop listening to the view

        # Disable buttons
        for item in self.children:
            item.disabled = True
        await interaction.response.edit_message(view=self)

        # Start processing
        await self.process_bundle(interaction)

    @ui.button(label="Cancel", style=discord.ButtonStyle.red, custom_id="cancel_bundle_btn", row=0)
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your session!", ephemeral=True)
            return

        self.is_cancelled = True
        self.stop()
        
        # Cleanup session
        if self.user_id in self.cog.active_bundle_sessions:
            self.cog.active_bundle_sessions.pop(self.user_id)

        for item in self.children:
            item.disabled = True

        cancel_embed = discord.Embed(
            title="❌ Bundle Cancelled",
            description="The bundle creation was cancelled.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=cancel_embed, view=self)

    async def process_bundle(self, interaction: discord.Interaction):
        """Downloads, renumbers, and merges all collected ZIPs."""
        processing_embed = discord.Embed(
            title="⏳ Processing Bundle",
            description=f"Processing {len(self.collected_thread_ids)} threads...",
            color=discord.Color.gold()
        )
        processing_embed.add_field(name="Status", value="Starting...", inline=False)
        await self.message.edit(embed=processing_embed, view=self)

        guild = interaction.guild
        success_count = 0
        failed_threads = []

        with tempfile.TemporaryDirectory() as temp_dir:
            merged_dir = os.path.join(temp_dir, "merged")
            os.makedirs(merged_dir, exist_ok=True)

            async with aiohttp.ClientSession() as session:
                for idx, thread_id in enumerate(self.collected_thread_ids):
                    if idx >= len(self.number_sequence):
                        break

                    new_number = self.number_sequence[idx]

                    try:
                        # Fetch thread
                        thread = guild.get_thread(thread_id)
                        if not thread:
                            try:
                                thread = await guild.fetch_channel(thread_id)
                            except discord.NotFound:
                                failed_threads.append(f"Thread {thread_id} not found")
                                continue

                        # Update progress
                        processing_embed.set_field_at(
                            0, name="Status",
                            value=f"Processing {idx + 1}/{len(self.collected_thread_ids)}: {thread.name}",
                            inline=False
                        )
                        await self.message.edit(embed=processing_embed)

                        # Find ZIP attachment in thread
                        zip_attachment = None
                        async for msg in thread.history(limit=10, oldest_first=True):
                            for attachment in msg.attachments:
                                if attachment.filename.lower().endswith('.zip'):
                                    zip_attachment = attachment
                                    break
                            if zip_attachment:
                                break

                        if not zip_attachment:
                            failed_threads.append(f"{thread.name}: No ZIP found")
                            continue

                        # Download ZIP
                        async with session.get(zip_attachment.url) as resp:
                            if resp.status != 200:
                                failed_threads.append(f"{thread.name}: Download failed")
                                continue
                            zip_data = await resp.read()

                        # Extract and renumber
                        with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
                            for file_info in zf.infolist():
                                if file_info.filename.endswith('/'):
                                    continue
                                
                                # Skip macOS metadata files
                                if '__MACOSX' in file_info.filename or os.path.basename(file_info.filename).startswith('._'):
                                    continue

                                content = zf.read(file_info.filename)
                                original_name = os.path.basename(file_info.filename)

                                # Renumber logic (same as /change_number)
                                # Use re.match to ensure we only match valid filenames from the start
                                match = re.match(r'([A-Z]+)(\d+)(.*)', original_name)
                                if match:
                                    prefix, num, suffix = match.groups()
                                    new_name = f"{prefix}{new_number}{suffix}"
                                else:
                                    new_name = original_name

                                # Write to merged folder
                                output_path = os.path.join(merged_dir, new_name)
                                with open(output_path, 'wb') as f:
                                    f.write(content)

                        success_count += 1

                    except Exception as e:
                        logger.error(f"Error processing thread {thread_id}: {e}")
                        failed_threads.append(f"Thread {thread_id}: {str(e)}")

            # Create final ZIP
            processing_embed.set_field_at(0, name="Status", value="Creating final ZIP...", inline=False)
            await self.message.edit(embed=processing_embed)

            output_zip_path = os.path.join(temp_dir, "bundle.zip")
            with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for filename in os.listdir(merged_dir):
                    zf.write(os.path.join(merged_dir, filename), filename)

            # Check size and send
            file_size = os.path.getsize(output_zip_path)

            final_embed = discord.Embed(
                title="✅ Bundle Complete!",
                description=f"Processed **{success_count}** toyboxes successfully.",
                color=discord.Color.green()
            )

            if failed_threads:
                failed_text = "\n".join(failed_threads[:10])
                if len(failed_threads) > 10:
                    failed_text += f"\n... and {len(failed_threads) - 10} more"
                final_embed.add_field(name="⚠️ Failed", value=failed_text, inline=False)

            await self.message.edit(embed=final_embed, view=None)

            if file_size < 25 * 1024 * 1024:
                await interaction.channel.send(
                    file=discord.File(output_zip_path, filename="bundle.zip")
                )
            else:
                await interaction.channel.send(
                    f"⚠️ The bundle is **{file_size / (1024*1024):.2f} MB**, which exceeds Discord's file size limit. "
                    "Please try with fewer files or consider an external upload."
                )
        
        # Cleanup session
        if self.user_id in self.cog.active_bundle_sessions:
            self.cog.active_bundle_sessions.pop(self.user_id)

    async def on_timeout(self):
        """Called when the view times out."""
        if self.message and not self.is_processing and not self.is_cancelled:
            timeout_embed = discord.Embed(
                title="⏰ Session Expired",
                description="The bundle session timed out due to inactivity.",
                color=discord.Color.orange()
            )
            for item in self.children:
                item.disabled = True
            
            # Cleanup session
            if self.user_id in self.cog.active_bundle_sessions:
                self.cog.active_bundle_sessions.pop(self.user_id)

            try:
                await self.message.edit(embed=timeout_embed, view=self)
            except discord.NotFound:
                pass
