import discord
from discord.ui import View, Select, Button
import random
import config

class PlayView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # No timeout for the view
        self.count = 1  # Default count

    @discord.ui.select(
        placeholder="Select number of random Toyboxes",
        options=[
            discord.SelectOption(label=str(i), value=str(i)) for i in range(1, 21)
        ],
        custom_id="select_toybox_count"
    )
    async def select_count(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.count = int(select.values[0])
        await interaction.response.defer()

    @discord.ui.button(label="Random", style=discord.ButtonStyle.blurple, custom_id="random_toybox_button")
    async def random_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        forum_channel = interaction.guild.get_channel(config.FORUM_CHANNEL_ID)
        if not forum_channel or not isinstance(forum_channel, discord.ForumChannel):
            await interaction.response.send_message("Error: Forum channel not found!", ephemeral=True)
            return

        threads = forum_channel.threads
        if not threads:
            await interaction.response.send_message("No toyboxes found!", ephemeral=True)
            return

        selected_threads = random.sample(threads, min(self.count, len(threads)))
        thread_links = '\n'.join(thread.jump_url for thread in selected_threads)

        message_prefix = "Play this Toybox:" if len(selected_threads) == 1 else "Play these Toyboxes:"
        await interaction.response.send_message(f"{message_prefix}\n{thread_links}", ephemeral=True)

        # Reset placeholder
        self.children[0].placeholder = "Select number of random Toyboxes"
        await interaction.message.edit(view=self)
