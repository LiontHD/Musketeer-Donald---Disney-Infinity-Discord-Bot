import discord
from services.rating_service import rating_service

class RatingView(discord.ui.View):
    def __init__(self, message_id):
        super().__init__(timeout=None)  # Make view persistent
        self.message_id = message_id

    @discord.ui.button(label="⭐️", style=discord.ButtonStyle.primary, custom_id="rate_1")
    async def rate_1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_rating(interaction, 1)

    @discord.ui.button(label="⭐️⭐️", style=discord.ButtonStyle.primary, custom_id="rate_2")
    async def rate_2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_rating(interaction, 2)

    @discord.ui.button(label="⭐️⭐️⭐️", style=discord.ButtonStyle.primary, custom_id="rate_3")
    async def rate_3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_rating(interaction, 3)

    @discord.ui.button(label="⭐️⭐️⭐️⭐️", style=discord.ButtonStyle.primary, custom_id="rate_4")
    async def rate_4(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_rating(interaction, 4)

    @discord.ui.button(label="⭐️⭐️⭐️⭐️⭐️", style=discord.ButtonStyle.primary, custom_id="rate_5")
    async def rate_5(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_rating(interaction, 5)

    async def handle_rating(self, interaction: discord.Interaction, rating: int):
        msg = rating_service.add_rating(self.message_id, interaction.user.id, rating)
        await interaction.response.send_message(msg, ephemeral=True)
        
        # Update the embed
        await self.update_rating_embed(interaction.message, self.message_id)

    async def update_rating_embed(self, message: discord.Message, message_id: int):
        avg_rating = rating_service.get_average_rating(message_id)
        
        # Create a new embed based on the existing one or create a new one
        if message.embeds:
            embed = message.embeds[0]
            # Update fields or description as needed
            # This part depends on how the embed is structured in the original code
            # For now, we'll just update a field if it exists or add it
             
            found = False
            for i, field in enumerate(embed.fields):
                if "Average Rating" in field.name:
                    embed.set_field_at(i, name="Average Rating", value=f"{avg_rating:.1f} {rating_service.get_star_rating(avg_rating)}", inline=True)
                    found = True
                    break
            
            if not found:
                embed.add_field(name="Average Rating", value=f"{avg_rating:.1f} {rating_service.get_star_rating(avg_rating)}", inline=True)

            await message.edit(embed=embed)
