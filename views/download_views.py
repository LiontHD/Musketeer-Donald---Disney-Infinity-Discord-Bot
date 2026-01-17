import discord



class BrownbatDownloadView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Button won't timeout
        
    @discord.ui.button(
        label="Download",
        style=discord.ButtonStyle.primary,
        custom_id="brownbat_download_button"  # Persistent custom_id
    )
    async def brownbat_download_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        download_url = "https://drive.usercontent.google.com/download?id=1oJnfDwdiOE2xACPMVaMUQzRDXsaBVT0m&export=download&authuser=0"
        await interaction.response.send_message(
            f"Here's your download link: {download_url}",
            ephemeral=True
        )
