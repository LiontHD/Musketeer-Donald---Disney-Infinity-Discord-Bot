import discord
import re
from services.daily_toybox_service import daily_toybox_service

class ReviewModal(discord.ui.Modal, title='Submit Toybox Review'):
    review_text = discord.ui.TextInput(
        label='What did you think of the Toybox?',
        style=discord.TextStyle.long,
        placeholder='Write your review here... (max 1000 characters)',
        required=True,
        max_length=1000
    )

    def __init__(self, toybox_id: int, thread_url: str):
        super().__init__()
        self.toybox_id = toybox_id
        self.thread_url = thread_url

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Check for auto-approve roles
            AUTO_APPROVE_ROLE_IDS = {1483928682514088167, 1483928373167132754, 1483928684539805888}
            has_auto_approve = False
            if hasattr(interaction.user, 'roles'):
                user_role_ids = {role.id for role in interaction.user.roles}
                if AUTO_APPROVE_ROLE_IDS.intersection(user_role_ids):
                    has_auto_approve = True

            if has_auto_approve:
                # Submit as approved directly
                review_id = await daily_toybox_service.submit_review(
                    self.toybox_id, 
                    interaction.user.id, 
                    self.review_text.value,
                    status='approved'
                )
                
                # Post directly to thread
                thread_id = None
                match = re.search(r'/channels/\d+/(\d+)', self.thread_url)
                if match:
                    thread_id = int(match.group(1))
                
                if thread_id:
                    thread = await interaction.client.fetch_channel(thread_id)
                    if thread.archived:
                        await thread.edit(archived=False)
                        
                    embed = discord.Embed(
                        title="📝 Toybox Review",
                        description=self.review_text.value,
                        color=discord.Color.random() # Random color for each review
                    )
                    embed.set_author(
                        name=interaction.user.display_name,
                        icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None
                    )
                    await thread.send(embed=embed)
                    
                await interaction.response.send_message("✅ Your review has been automatically approved and posted directly to the thread!", ephemeral=True)
            else:
                # Submit to DB as pending
                review_id = await daily_toybox_service.submit_review(
                    self.toybox_id, 
                    interaction.user.id, 
                    self.review_text.value,
                    status='pending'
                )
                
                # Fetch toybox details for link
                tb_details = daily_toybox_service.get_toybox_details(self.toybox_id)
                tb_name = tb_details.get('name', 'Unknown Toybox') if tb_details else "Unknown Toybox"
                tb_url = tb_details.get('url', '') if tb_details else self.thread_url
                
                # Send to admin channel for approval
                admin_channel_id = 1483935264396284055
                admin_channel = interaction.client.get_channel(admin_channel_id)
                if admin_channel:
                    embed = discord.Embed(
                        title="📝 New Daily Toybox Review (Pending)",
                        description=(
                            f"**User:** {interaction.user.mention}\n"
                            f"**Toybox:** [{tb_name}]({tb_url})\n\n"
                            f"**Review:**\n{self.review_text.value}"
                        ),
                        color=discord.Color.orange()
                    )
                    from cogs.daily_toybox_admin import AdminReviewView
                    await admin_channel.send(
                        embed=embed, 
                        view=AdminReviewView(review_id, self.toybox_id, interaction.user.id, self.thread_url)
                    )
                    
                await interaction.response.send_message("✅ Your review has been submitted for approval! It will appear in the thread once approved.", ephemeral=True)
        except ValueError as e:
            await interaction.response.send_message(f"❌ {e}", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ An error occurred: {e}", ephemeral=True)


class DailyToyboxView(discord.ui.View):
    def __init__(self, toybox_id: int, thread_url: str, video_url: str = None):
        super().__init__(timeout=None)
        self.toybox_id = toybox_id
        self.thread_url = thread_url

        # Link to thread (View Toybox)
        # Note: Link buttons must use ButtonStyle.link.
        self.add_item(discord.ui.Button(label="🎮 View Toybox", url=thread_url, style=discord.ButtonStyle.link))
        
        # Link to video if available
        if video_url:
            self.add_item(discord.ui.Button(label="📺 Playthrough video", url=video_url, style=discord.ButtonStyle.link))

        # Persistent 'I Played This' button
        play_count = daily_toybox_service.get_play_count(toybox_id)
        play_btn = discord.ui.Button(
            label=f"✅ I played this! ({play_count})" if play_count > 0 else "✅ I played this!", 
            style=discord.ButtonStyle.secondary,
            custom_id=f"daily_play_{toybox_id}"
        )
        play_btn.callback = self.play_callback
        self.add_item(play_btn)

        # Persistent 'Write Review' button
        review_btn = discord.ui.Button(
            label="📝 Write review", 
            style=discord.ButtonStyle.secondary,
            custom_id=f"daily_review_{toybox_id}"
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
            await daily_toybox_service.toggle_play(t_id, interaction.user.id)
            play_count = daily_toybox_service.get_play_count(t_id)
            
            # Recreate view components with updated play count
            view = discord.ui.View.from_message(interaction.message)
            for item in view.children:
                if isinstance(item, discord.ui.Button) and item.custom_id == interaction.custom_id:
                    item.label = f"✅ I played this! ({play_count})" if play_count > 0 else "✅ I played this!"
            
            await interaction.response.edit_message(view=view)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

    async def review_callback(self, interaction: discord.Interaction):
        if not interaction.custom_id or not interaction.custom_id.startswith("daily_review_"):
            return
            
        parts = interaction.custom_id.split("_", 2)
        if len(parts) >= 3:
            try:
                t_id = int(parts[2])
                # Lookup the thread URL dynamically to avoid exceeding 100 character custom_id limit
                thread_url = daily_toybox_service.get_toybox_url(t_id)
                await interaction.response.send_modal(ReviewModal(t_id, thread_url))
            except Exception as e:
                await interaction.response.send_message(f"❌ Error setting up review modal: {e}", ephemeral=True)
