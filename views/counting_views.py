import discord
from discord.ui import View, Button
from services.counters import ToyboxCounter

class EndCountingButton(Button):
    def __init__(self, counter: ToyboxCounter, user_id: int, progress_message: discord.Message):
        super().__init__(label="End Counting", style=discord.ButtonStyle.danger)
        self.counter = counter
        self.user_id = user_id
        self.progress_message = progress_message  # Store the progress message reference

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("You cannot end this session.", ephemeral=True)
            return
        
        session_data = self.counter.counting_sessions.pop(self.user_id, [])
        if not session_data:
            await interaction.response.send_message("No counting session found.", ephemeral=True)
            return

        total = sum(count for _, count in session_data)

        # Create a more structured embed
        embed = discord.Embed(
            title="📊 Toybox Counting Results",
            description="Summary of counted toyboxes in submitted files",
            color=0x4ecca5
        )
        
        # Add a divider field
        embed.add_field(
            name="━━ File Details ━━",
            value="",
            inline=False
        )

        # Add individual file results
        for filename, count in session_data:
            formatted_filename = filename.replace('_', ' ').replace('.zip', '')
            embed.add_field(
                name=f"📦 {formatted_filename}",
                value=f"> Found `{count}` Toybox{'es' if count != 1 else ''}",
                inline=False
            )

        # Add a divider before total
        embed.add_field(
            name="━━ Summary ━━",
            value="",
            inline=False
        )

        # Add total with more emphasis
        embed.add_field(
            name="📈 Total Count",
            value=f"```\n{total} Toybox{'es' if total != 1 else ''}\n```",
            inline=False
        )

        # Add timestamp
        embed.timestamp = discord.utils.utcnow()
        
        # Enhanced footer
        embed.set_footer(
            text="Toybox Count Bot | Session Complete ✨",
            icon_url="https://cdn.discordapp.com/emojis/1039238467898613851.webp?size=96&quality=lossless"
        )

        await interaction.response.send_message(embed=embed)
        
        # Delete the progress message
        try:
            await self.progress_message.delete()
        except discord.HTTPException:
            pass  # Ignore any errors if message is already deleted
            
        self.view.stop()

class CountingView(View):
    def __init__(self, counter: ToyboxCounter, user_id: int, progress_message: discord.Message):
        super().__init__()
        self.add_item(EndCountingButton(counter, user_id, progress_message))
