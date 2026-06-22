import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import random
import datetime
import re
from zoneinfo import ZoneInfo
from utils.logger import logger
import config
from services.daily_toybox_service import daily_toybox_service
from views.daily_toybox_view import DailyToyboxView

# Role ID for Daily Toybox Subscribers
DAILY_SUBSCRIBER_ROLE_ID = 1484125406012506153
DAILY_CHANNEL_ID = 1483930072388997230

def get_youtube_link(description: str):
    """Extracts YouTube link if present."""
    match = re.search(r'(https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[\w-]+)', description)
    return match.group(1) if match else None

def get_youtube_thumbnail(url: str):
    match = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]+)', url)
    if match:
        return f"https://img.youtube.com/vi/{match.group(1)}/maxresdefault.jpg"
    return None

def get_color_for_tags(tags: list):
    tags_lower = [t.lower() for t in tags]
    if "star wars" in tags_lower:
        return discord.Color.from_rgb(0, 168, 255) # Force Blue
    elif "marvel" in tags_lower:
        return discord.Color.from_rgb(240, 19, 30) # Marvel Red
    elif "disney" in tags_lower:
        return discord.Color.from_rgb(17, 56, 91) # Disney Blue
    return discord.Color.gold()

async def get_thread_image(bot, url: str):
    """Attempts to fetch the first image attachment or embed image from a thread's starter message."""
    match = re.search(r'/channels/\d+/(\d+)', url)
    if not match: 
        return None
        
    thread_id = int(match.group(1))
    try:
        thread = await bot.fetch_channel(thread_id)
        # Fetch starter message
        try:
            msgs = [m async for m in thread.history(limit=1, oldest_first=True)]
            if not msgs: 
                return None
            msg = msgs[0]
            
            # Check attachments
            if msg.attachments:
                for att in msg.attachments:
                    if att.url.lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                        return att.url
            # Check embeds
            if msg.embeds:
                for emb in msg.embeds:
                    if emb.image and emb.image.url: 
                        return emb.image.url
        except Exception as e:
            logger.warning(f"Failed to fetch history for thread {thread_id}: {e}")
    except Exception as e:
        logger.warning(f"Could not fetch thread {thread_id} for image extraction: {e}")
    return None

class DailyToybox(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.daily_task.start()
        self.weekly_highlight_task.start()

    def cog_unload(self):
        self.daily_task.cancel()
        self.weekly_highlight_task.cancel()

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Detects when a user gets the subscriber role and sends a welcome DM."""
        role = after.guild.get_role(DAILY_SUBSCRIBER_ROLE_ID)
        if not role:
            return

        if role not in before.roles and role in after.roles:
            logger.info(f"User {after.id} gained the Daily Toybox role. Sending welcome DM.")
            try:
                embed = discord.Embed(
                    title="🎉 Welcome to the Daily Toybox!",
                    description=(
                        "You've been given the **Daily Toybox Subscriber** role! 🦆\n\n"
                        "Every day at **8:00 AM UK Time**, I'll post a toybox from our massive toybox database into the daily channel.\n\n"
                        "Get ready to discover some hidden gems! 💎"
                    ),
                    color=discord.Color.green()
                )
                embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1039238467898613851.webp?size=96&quality=lossless")
                await after.send(embed=embed)
            except Exception as e:
                logger.error(f"Error sending welcome DM to {after.id}: {e}")

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Global listener for the persistent Daily Toybox buttons (Play and Review)."""
        if interaction.type != discord.InteractionType.component or interaction.data.get('component_type') != 2:
            return
            
        custom_id = interaction.data.get('custom_id', '')
        if custom_id.startswith('daily_play_'):
            t_id_str = custom_id.replace("daily_play_", "")
            try:
                t_id = int(t_id_str)
                marked_played = await daily_toybox_service.toggle_play(t_id, interaction.user.id)
                if marked_played:
                    await interaction.response.send_message("✅ You have marked this Toybox as played!", ephemeral=True)
                else:
                    await interaction.response.send_message("❌ You have unmarked this Toybox as played.", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
                
        elif custom_id.startswith('daily_review_'):
            parts = custom_id.split("_", 2)
            if len(parts) >= 3:
                try:
                    t_id = int(parts[2])
                    thread_url = daily_toybox_service.get_toybox_url(t_id)
                    from views.daily_toybox_view import ReviewModal
                    await interaction.response.send_modal(ReviewModal(t_id, thread_url))
                except Exception as e:
                    await interaction.response.send_message(f"❌ Error setting up review modal: {e}", ephemeral=True)

    @tasks.loop(time=datetime.time(hour=8, minute=0, tzinfo=ZoneInfo('Europe/London')))
    async def daily_task(self):
        logger.info("⏰ Running Daily Toybox Task (V2)...")
        
        if not os.path.exists(config.TOYBOX_DATA_FILE):
            logger.error("Toybox data file not found!")
            return

        try:
            with open(config.TOYBOX_DATA_FILE, 'r') as f:
                toyboxes = json.load(f)
        except Exception as e:
            logger.error(f"Error loading toyboxes: {e}")
            return

        if not toyboxes:
            return

        # Filtering logic (Cooldown / Repeat Prevention)
        available_toyboxes = []
        for tb in toyboxes:
            # Skip if recently played (e.g. last 90 days)
            if not daily_toybox_service.is_on_cooldown(tb['id'], days=90):
                available_toyboxes.append(tb)

        # Fallback if all are on cooldown
        if not available_toyboxes:
            logger.warning("All toyboxes are on cooldown. Resetting pool.")
            available_toyboxes = toyboxes

        # Random Selection
        toybox = random.choice(available_toyboxes)
        
        # Extract Creator from description if possible
        desc = toybox.get('description', '')
        creator_name = "Unknown Creator"
        creator_match = re.search(r'(?i)Creator:\s*([^\n]+)', desc)
        if creator_match:
            creator_name = creator_match.group(1).replace('*', '').strip()
            
        # Clean description (remove boilerplate lines like the creator/video footer)
        clean_desc = re.sub(r'(-+\n)?(?:\*\*)?(?::art:|🎨).*Creator:[^\n]+(?:\n|$)', '', desc, flags=re.IGNORECASE)
        clean_desc = re.sub(r'(?:\*\*)?(?::film_frames:|🎞️).*Playthrough video:[^\n]+(?:\n|$)', '', clean_desc, flags=re.IGNORECASE)
        clean_desc = clean_desc.strip()
        if not clean_desc:
            clean_desc = "A mysterious Toybox waiting to be explored!"

        tags = toybox.get('tags', [])
        embed_color = get_color_for_tags(tags)
        
        embed = discord.Embed(
            title=f"🌟 Toybox of the Day: {toybox.get('name', 'Unknown')}",
            description=clean_desc,
            color=embed_color,
            url=toybox.get('url', '')
        )
        
        # Creator and Tags Field
        embed.add_field(name="👤 Creator", value=creator_name, inline=True)
        if tags:
            tag_icons = {"Star Wars": "🛸", "Marvel": "🦸‍♂️", "Disney": "🏰", "Other": "🎮"}
            formatted_tags = ", ".join([f"{tag_icons.get(t, '🏷️')} {t}" for t in tags])
            embed.add_field(name="🏷️ Theme", value=formatted_tags, inline=True)
        
        # Subtoyboxes
        sub_tbs = toybox.get('subtoyboxes', [])
        if sub_tbs:
            embed.add_field(name="🗺️ Includes Sub-Levels", value=f"{len(sub_tbs)} connected chambers", inline=False)
            
        # Image Resolution
        video_url = get_youtube_link(desc)
        img_url = None
        if video_url:
            img_url = get_youtube_thumbnail(video_url)
            
        if not img_url:
            img_url = await get_thread_image(self.bot, toybox.get('url', ''))
            
        if img_url:
            embed.set_image(url=img_url)

        embed.set_footer(text="Daily Toybox Alert • Click 'I Played This!' below if you've explored it.")

        # Prepare View
        view = DailyToyboxView(toybox_id=toybox['id'], thread_url=toybox.get('url', ''), video_url=video_url)

        # Send to channel
        channel = self.bot.get_channel(DAILY_CHANNEL_ID)
        if channel:
            try:
                await channel.send(
                    content=f"🔔 <@&{DAILY_SUBSCRIBER_ROLE_ID}>",
                    embed=embed,
                    view=view
                )
                logger.info(f"Successfully sent Daily Toybox ID {toybox['id']} to channel.")
                
                # Mark as played/cooldown in DB
                daily_toybox_service.add_to_history(toybox['id'])
            except Exception as e:
                logger.error(f"Failed to send daily toybox to channel: {e}")
        else:
            logger.error("Daily Toybox channel not found!")

    # Weekly Highlight on Sunday at 18:00 UK Time
    @tasks.loop(time=datetime.time(hour=18, minute=0, tzinfo=ZoneInfo('Europe/London')))
    async def weekly_highlight_task(self):
        # Only run on Sunday (0=Monday, 6=Sunday)
        if datetime.datetime.now(ZoneInfo('Europe/London')).weekday() != 6:
            return
            
        logger.info("🏆 Running Weekly Toybox Highlight...")
        best_toybox_stats = daily_toybox_service.get_toybox_of_the_week()
        
        if not best_toybox_stats:
            logger.info("No plays recorded this week.")
            return
            
        toybox_id = best_toybox_stats['toybox_id']
        play_count = best_toybox_stats['play_count']
        
        # Load toybox info
        if not os.path.exists(config.TOYBOX_DATA_FILE):
            return
            
        try:
            with open(config.TOYBOX_DATA_FILE, 'r') as f:
                toyboxes = json.load(f)
            best_tb = next((tb for tb in toyboxes if tb['id'] == toybox_id), None)
            
            if best_tb:
                channel = self.bot.get_channel(DAILY_CHANNEL_ID)
                if channel:
                    embed = discord.Embed(
                        title="🏆 Toybox of the Week!",
                        description=f"**{best_tb.get('name', 'Unknown')}** was the most played Daily Toybox this week with **{play_count} plays**!\n\nThanks for exploring with us. 🦆",
                        color=discord.Color.gold(),
                        url=best_tb.get('url', '')
                    )
                    await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Failed to run weekly highlight: {e}")

    @daily_task.before_loop
    @weekly_highlight_task.before_loop
    async def before_tasks(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="test_daily_toybox", description="Admin only: Force post the Daily Toybox immediately for testing.")
    @app_commands.checks.has_permissions(administrator=True)
    async def test_daily_toybox(self, interaction: discord.Interaction):
        await interaction.response.send_message("Starting manual Daily Toybox run...", ephemeral=True)
        await self.daily_task()

async def setup(bot):
    await bot.add_cog(DailyToybox(bot))
