import discord
from discord.ui import View

class AskToyboxPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Start chat", style=discord.ButtonStyle.primary, custom_id="ask_toybox_start_chat")
    async def start_chat_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
            if not isinstance(interaction.channel, (discord.TextChannel, discord.ForumChannel)):
                await interaction.followup.send("Sorry, I can only start chats in regular text channels or forum channels.", ephemeral=True)
                return
            thread_name = f"Toybox Chat with {interaction.user.display_name[:50]}"
            bot_member = interaction.guild.me
            channel_perms = interaction.channel.permissions_for(bot_member)
            if not channel_perms.create_private_threads:
                await interaction.followup.send("I don't have permission to create private threads in this channel.", ephemeral=True)
                return
            if not channel_perms.send_messages_in_threads:
                await interaction.followup.send("I don't have permission to send messages in threads here.", ephemeral=True)
                return
            new_thread = await interaction.channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.private_thread,
                auto_archive_duration=1440,
                reason=f"Toybox AI chat initiated by {interaction.user.name}"
            )
            await new_thread.add_user(interaction.user)
            welcome_embed = discord.Embed(
                title="🦆 Find a Toybox with AI 🦆",
                description=(
                    f"Hi {interaction.user.mention}! I'm Donald Duck, ready to help you find the perfect Toybox adventure! 🎮\n\n"
                    f"**Tell me what you're looking for today:**\n"
                    f"• A specific character (like Iron Man or Stitch)\n"
                    f"• A type of game (racing, platformer, combat)\n"
                    f"• A franchise (Star Wars, Marvel Avengers)\n"
                    f"• Or any other ideas you have!"
                ),
                color=discord.Color.from_rgb(59, 136, 195)
            )
            await new_thread.send(embed=welcome_embed)
            await interaction.followup.send(f"I've started a private chat for you here: {new_thread.mention}", ephemeral=True)
        except Exception as e:
            print(f"Error in start_chat_button callback: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("Sorry, something went wrong while trying to start the chat.", ephemeral=True)
                else:
                    await interaction.followup.send("Sorry, something went wrong while trying to start the chat.", ephemeral=True)
            except Exception as final_e:
                print(f"Error sending final error message in start_chat_button: {final_e}")
