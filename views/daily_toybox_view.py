import discord
from services.daily_toybox_service import daily_toybox_service

class ReviewModal(discord.ui.Modal, title='Submit Toybox Review'):
    review_text = discord.ui.TextInput(
        label='What did you think of the Toybox?',
        style=discord.TextStyle.long,
        placeholder='Write your review here... (max 1000 chars)',
        required=True,
        max_length=1000
    )

    def __init__(self, toybox_id: int, thread_url: str):
        super().__init__()
        self.toybox_id = toybox_id
        self.thread_url = thread_url

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Submit to DB
            review_id = await daily_toybox_service.submit_review(
                self.toybox_id, 
                interaction.user.id, 
                self.review_text.value
            )
            
            # Send to admin channel for approval
            admin_channel_id = 1483935264396284055
            admin_channel = interaction.client.get_channel(admin_channel_id)
            if admin_channel:
                embed = discord.Embed(
                    title="📝 New Daily Toybox Review (Pending)",
                    description=f"**User:** {interaction.user.mention}\n**Toybox ID:** {self.toybox_id}\n\n**Review:**\n{self.review_text.value}",
                    color=discord.Color.orange()
                )
                from cogs.daily_toybox_admin import AdminReviewView
                await admin_channel.send(
                    embed=embed, 
                    view=AdminReviewView(review_id, self.toybox_id, interaction.user.id, self.thread_url)
                )
                
            await interaction.response.send_message("✅ Your review has been submitted for approval! It will appear in the thread once approved.", ephemeral=True)
        except ValueError as e:
            # e.g., user already submitted a review
            await interaction.response.send_message(f"❌ {e}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ An error occurred: {e}", ephemeral=True)


class DailyToyboxView(discord.ui.View):
    def __init__(self, toybox_id: int, thread_url: str, video_url: str = None):
        # Timeout is None so the view is persistent if we re-register it, 
        # but for dynamic toybox_ids, we might just store toybox_id in the custom_id 
        # to make it truly persistent.
        # Let's make it persistent by embedding toybox_id in custom_ids
        super().__init__(timeout=None)
        self.toybox_id = toybox_id
        self.thread_url = thread_url

        # Link to thread
        self.add_item(discord.ui.Button(label="🎮 View Thread", url=thread_url, style=discord.ButtonStyle.link))
        
        # Link to video if available
        if video_url:
            self.add_item(discord.ui.Button(label="📺 Playthrough Video", url=video_url, style=discord.ButtonStyle.link))

        # Persistent 'I Played This' button
        play_btn = discord.ui.Button(
            label="✅ I Played This!", 
            style=discord.ButtonStyle.secondary,
            custom_id=f"daily_play_{toybox_id}"
        )
        play_btn.callback = self.play_callback
        self.add_item(play_btn)

        # Persistent 'Write Review' button
        review_btn = discord.ui.Button(
            label="📝 Write Review", 
            style=discord.ButtonStyle.secondary,
            custom_id=f"daily_review_{toybox_id}_{thread_url}" # Encode thread_url too, though it's long.
            # Better: thread_url is known via toybox_id. But keeping it simple for now.
        )
        review_btn.callback = self.review_callback
        self.add_item(review_btn)

    async def play_callback(self, interaction: discord.Interaction):
        # Check if custom_id starts with daily_play_
        if not interaction.custom_id or not interaction.custom_id.startswith("daily_play_"):
            return
            
        t_id_str = interaction.custom_id.replace("daily_play_", "")
        try:
            t_id = int(t_id_str)
            marked_played = await daily_toybox_service.toggle_play(t_id, interaction.user.id)
            if marked_played:
                # Also update embed to show plays count if we want, but user requested no player count.
                await interaction.response.send_message("✅ You have marked this Toybox as played!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ You have unmarked this Toybox as played.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

    async def review_callback(self, interaction: discord.Interaction):
        if not interaction.custom_id or not interaction.custom_id.startswith("daily_review_"):
            return
            
        parts = interaction.custom_id.split("_", 3)
        if len(parts) >= 3:
            t_id = int(parts[2])
            thread_url = parts[3] if len(parts) > 3 else ""
            await interaction.response.send_modal(ReviewModal(t_id, thread_url))
