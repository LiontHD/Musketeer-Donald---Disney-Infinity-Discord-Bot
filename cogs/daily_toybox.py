import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import random
import datetime
from zoneinfo import ZoneInfo
from utils.logger import logger
import config

# Role ID for Daily Toybox Subscribers
DAILY_SUBSCRIBER_ROLE_ID = 1442263835594723559

class DailyToybox(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.daily_task.start()

    def cog_unload(self):
        self.daily_task.cancel()

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Detects when a user gets the subscriber role and sends a welcome DM."""
        role = after.guild.get_role(DAILY_SUBSCRIBER_ROLE_ID)
        if not role:
            return

        # Check if role was added
        if role not in before.roles and role in after.roles:
            logger.info(f"User {after.id} gained the Daily Toybox role. Sending welcome DM.")
            try:
                embed = discord.Embed(
                    title="🎉 Welcome to the Daily Toybox!",
                    description=(
                        "You've been given the **Daily Toybox Subscriber** role! 🦆\n\n"
                        "Every day at **8:00 AM UK Time**, I'll send you a toybox from our massive toybox database directly to your DMs.\n\n"
                        "Get ready to discover some hidden gems! 💎"
                    ),
                    color=discord.Color.green()
                )
                embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1039238467898613851.webp?size=96&quality=lossless")
                await after.send(embed=embed)
            except discord.Forbidden:
                logger.warning(f"Could not send welcome DM to {after.id} (Forbidden).")
            except Exception as e:
                logger.error(f"Error sending welcome DM to {after.id}: {e}")

    @tasks.loop(time=datetime.time(hour=8, minute=0, tzinfo=ZoneInfo('Europe/London')))
    async def daily_task(self):
        logger.info("⏰ Running Daily Toybox Task (Role-Based)...")
        
        # Load toyboxes
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

        # Pick a random toybox
        toybox = random.choice(toyboxes)
        
        embed = discord.Embed(
            title=f"🌟 Toybox of the Day: {toybox.get('name', 'Unknown')}",
            description=toybox.get('description', 'No description available.'),
            color=discord.Color.gold(),
            url=toybox.get('url', '')
        )
        
        tags = toybox.get('tags', [])
        if tags:
            embed.add_field(name="Tags", value=", ".join(tags), inline=False)
            
        embed.add_field(name="🔗 Link", value=f"[Click to Play]({toybox.get('url', '')})", inline=False)
        embed.set_footer(text="You received this because you have the Daily Toybox Subscriber role.")

        # Iterate over all guilds to find members with the role
        for guild in self.bot.guilds:
            role = guild.get_role(DAILY_SUBSCRIBER_ROLE_ID)
            if not role:
                continue
            
            # Refresh member list to ensure we have latest roles
            # Note: Depending on intents, this might need chunking, but for now we assume cache is okay or small enough
            for member in role.members:
                if member.bot:
                    continue
                    
                try:
                    await member.send(embed=embed)
                except discord.Forbidden:
                    logger.warning(f"Could not DM user {member.id} (Forbidden).")
                except Exception as e:
                    logger.error(f"Failed to send daily toybox to {member.id}: {e}")

    @daily_task.before_loop
    async def before_daily_task(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(DailyToybox(bot))
