import discord
from discord.ext import commands
from services.daily_toybox_service import daily_toybox_service
import re

class AdminReviewView(discord.ui.View):
    def __init__(self, review_id: int, toybox_id: int, user_id: int, thread_url: str):
        super().__init__(timeout=None)
        
        # Approve button
        approve_btn = discord.ui.Button(
            label="🟢 Approve", 
            style=discord.ButtonStyle.success,
            custom_id=f"admin_approve_{review_id}_{toybox_id}_{user_id}"
        )
        approve_btn.callback = self.approve_callback
        self.add_item(approve_btn)

        # Reject button
        reject_btn = discord.ui.Button(
            label="🔴 Reject", 
            style=discord.ButtonStyle.danger,
            custom_id=f"admin_reject_{review_id}_{user_id}"
        )
        reject_btn.callback = self.reject_callback
        self.add_item(reject_btn)

        self.thread_url = thread_url

    async def approve_callback(self, interaction: discord.Interaction):
        # Format: admin_approve_{review_id}_{toybox_id}_{user_id}
        parts = interaction.custom_id.split("_")
        review_id = int(parts[2])
        toybox_id = int(parts[3])
        user_id = int(parts[4])

        await interaction.response.defer()

        # Update DB
        await daily_toybox_service.update_review_status(review_id, 'approved')
        review_data = daily_toybox_service.get_review(review_id)
        if not review_data:
            await interaction.followup.send("❌ Review not found in DB.", ephemeral=True)
            return

        # Extract thread ID from thread_url to post the review
        # Example URL: https://discord.com/channels/SERVER_ID/THREAD_ID
        thread_id = None
        match = re.search(r'/channels/\d+/(\d+)', self.thread_url)
        if match:
            thread_id = int(match.group(1))

        if thread_id:
            try:
                thread = await interaction.client.fetch_channel(thread_id)
                # Temporarily unarchive if needed
                if thread.archived:
                    await thread.edit(archived=False)

                # Post review
                embed = discord.Embed(
                    title="📝 Toybox Review",
                    description=review_data['review_text'],
                    color=discord.Color.green()
                )
                user = interaction.client.get_user(user_id)
                embed.set_author(name=user.display_name if user else f"User {user_id}", icon_url=user.display_avatar.url if user and user.display_avatar else None)
                
                await thread.send(embed=embed)
                
                # Notify User
                if user:
                    try:
                        await user.send(f"✅ Your review for the Daily Toybox has been approved and posted!\n{self.thread_url}")
                    except:
                        pass
                        
            except discord.Forbidden:
                await interaction.followup.send("❌ Failed to post review in thread due to permissions.", ephemeral=True)
            except discord.NotFound:
                await interaction.followup.send("❌ Thread not found. It might have been deleted.", ephemeral=True)
            except Exception as e:
                await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

        # Update Admin Message
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(content="✅ **APPROVED**", view=self)


    async def reject_callback(self, interaction: discord.Interaction):
        # Format: admin_reject_{review_id}_{user_id}
        parts = interaction.custom_id.split("_")
        review_id = int(parts[2])
        user_id = int(parts[3])

        await interaction.response.defer()
        await daily_toybox_service.update_review_status(review_id, 'rejected')

        user = interaction.client.get_user(user_id)
        if user:
            try:
                await user.send("🔴 Your recent review for the Daily Toybox was not approved.")
            except:
                pass

        # Update Admin Message
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(content="🔴 **REJECTED**", view=self)

class DailyToyboxAdmin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        # Listen globally for the persistent admin buttons if the bot restarts
        if interaction.type == discord.InteractionType.component and interaction.data.get('component_type') == 2:
            custom_id = interaction.data.get('custom_id', '')
            
            if custom_id.startswith('admin_approve_'):
                parts = custom_id.split("_")
                review_id = int(parts[2])
                toybox_id = int(parts[3])
                user_id = int(parts[4])
                
                await interaction.response.defer()
                
                # Update DB
                await daily_toybox_service.update_review_status(review_id, 'approved')
                review_data = daily_toybox_service.get_review(review_id)
                if not review_data:
                    await interaction.followup.send("❌ Review not found in DB.", ephemeral=True)
                    return
                
                # Lookup thread_url
                thread_url = daily_toybox_service.get_toybox_url(toybox_id)
                thread_id = None
                if thread_url:
                    match = re.search(r'/channels/\d+/(\d+)', thread_url)
                    if match:
                        thread_id = int(match.group(1))
                        
                if thread_id:
                    try:
                        thread = await interaction.client.fetch_channel(thread_id)
                        if thread.archived:
                            await thread.edit(archived=False)
                            
                        embed = discord.Embed(
                            title="📝 Toybox Review",
                            description=review_data['review_text'],
                            color=discord.Color.green()
                        )
                        user = interaction.client.get_user(user_id)
                        embed.set_author(
                            name=user.display_name if user else f"User {user_id}",
                            icon_url=user.display_avatar.url if user and user.display_avatar else None
                        )
                        await thread.send(embed=embed)
                        
                        if user:
                            try:
                                await user.send(f"✅ Your review for the Daily Toybox has been approved and posted!\n{thread_url}")
                            except:
                                pass
                    except Exception as e:
                        await interaction.followup.send(f"❌ Error posting review to thread: {e}", ephemeral=True)
                        
                # Update message
                await interaction.message.edit(content="✅ **APPROVED**", view=None)
                
            elif custom_id.startswith('admin_reject_'):
                parts = custom_id.split("_")
                review_id = int(parts[2])
                user_id = int(parts[3])
                
                await interaction.response.defer()
                await daily_toybox_service.update_review_status(review_id, 'rejected')
                
                user = interaction.client.get_user(user_id)
                if user:
                    try:
                        await user.send("🔴 Your recent review for the Daily Toybox was not approved.")
                    except:
                        pass
                        
                await interaction.message.edit(content="🔴 **REJECTED**", view=None)

async def setup(bot):
    await bot.add_cog(DailyToyboxAdmin(bot))
