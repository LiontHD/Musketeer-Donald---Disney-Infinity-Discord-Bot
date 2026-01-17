import discord
from discord.ui import View, Button, Select

# Placeholder for search function - in a real app this would be injected or imported from a service
async def search_toyboxes_placeholder(category: str):
    return []

class ResultView(discord.ui.View):
    def __init__(self, results, category):
        super().__init__(timeout=None)
        self.results = results
        self.category = category
        self.page = 0
        self.items_per_page = 5
        self.total_pages = max(1, (len(results) + self.items_per_page - 1) // self.items_per_page)
        
        # Add pagination components
        self.update_buttons()
        if self.total_pages > 1:
            self.add_page_select()

    def update_buttons(self):
        # Update button states based on current page
        self.prev_button.disabled = self.page == 0
        self.next_button.disabled = self.page == self.total_pages - 1

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary, custom_id="toybox_prev")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            self.update_buttons()
            if hasattr(self, 'page_select'):
                self.update_page_select()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.defer()
            
    @discord.ui.button(label="Back to Categories", style=discord.ButtonStyle.secondary, custom_id="toybox_back")
    async def back_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.delete_original_response()

        
    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary, custom_id="toybox_next")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.total_pages - 1:
            self.page += 1
            self.update_buttons()
            if hasattr(self, 'page_select'):
                self.update_page_select()
            await interaction.response.edit_message(embed=self.create_embed(), view=self)
        else:
            await interaction.response.defer()

    def add_page_select(self):
        if self.total_pages <= 25:
            # Single dropdown for pages
            options = [
                discord.SelectOption(
                    label=f"Page {i + 1}",
                    value=str(i),
                    default=(i == self.page)
                )
                for i in range(self.total_pages)
            ]
            
            select = discord.ui.Select(
                placeholder=f"Page {self.page + 1}",
                options=options,
                custom_id="toybox_page_select"
            )
            
            async def page_select_callback(interaction: discord.Interaction):
                self.page = int(select.values[0])
                self.update_buttons()
                select.placeholder = f"Page {self.page + 1}"
                await interaction.response.edit_message(embed=self.create_embed(), view=self)
            
            select.callback = page_select_callback
            self.page_select = select
            self.add_item(select)
        else:
            # Group selection for many pages
            group_count = (self.total_pages + 24) // 25
            current_group = self.page // 25
            
            # Group selector
            group_options = [
                discord.SelectOption(
                    label=f"Pages {i * 25 + 1}-{min((i + 1) * 25, self.total_pages)}",
                    value=str(i),
                    default=(i == current_group)
                )
                for i in range(group_count)
            ]
            
            group_select = discord.ui.Select(
                placeholder=f"Pages {current_group * 25 + 1}-{min((current_group + 1) * 25, self.total_pages)}",
                options=group_options,
                custom_id="toybox_group_select"
            )
            
            # Page selector within group
            page_options = [
                discord.SelectOption(
                    label=f"Page {i + 1}",
                    value=str(i),
                    default=(i == self.page)
                )
                for i in range(current_group * 25, min((current_group + 1) * 25, self.total_pages))
            ]
            
            page_select = discord.ui.Select(
                placeholder=f"Page {self.page + 1}",
                options=page_options,
                custom_id="toybox_page_select"
            )
            
            async def group_select_callback(interaction: discord.Interaction):
                group_index = int(group_select.values[0])
                self.page = group_index * 25
                self.update_buttons()
                self.update_page_select()
                await interaction.response.edit_message(embed=self.create_embed(), view=self)
            
            async def page_select_callback(interaction: discord.Interaction):
                self.page = int(page_select.values[0])
                self.update_buttons()
                page_select.placeholder = f"Page {self.page + 1}"
                await interaction.response.edit_message(embed=self.create_embed(), view=self)
            
            group_select.callback = group_select_callback
            page_select.callback = page_select_callback
            
            self.group_select = group_select
            self.page_select = page_select
            self.add_item(group_select)
            self.add_item(page_select)

    def update_page_select(self):
        if hasattr(self, 'page_select'):
            if hasattr(self, 'group_select'):
                # Update group select
                current_group = self.page // 25
                self.group_select.placeholder = f"Pages {current_group * 25 + 1}-{min((current_group + 1) * 25, self.total_pages)}"
                
                # Update page select options within current group
                start_page = current_group * 25
                end_page = min((current_group + 1) * 25, self.total_pages)
                self.page_select.options = [
                    discord.SelectOption(
                        label=f"Page {i + 1}",
                        value=str(i),
                        default=(i == self.page)
                    )
                    for i in range(start_page, end_page)
                ]
            else:
                # Single page select
                self.page_select.placeholder = f"Page {self.page + 1}"
                for option in self.page_select.options:
                    option.default = (int(option.value) == self.page)

    def create_embed(self):
        embed = discord.Embed(
            title=f"🎮 {self.category} Toyboxes (Page {self.page + 1} of {self.total_pages})",
            color=discord.Color.blue()
        )
        embed.description = f"Found **{len(self.results)}** {self.category} Toyboxes"
        
        start_index = self.page * self.items_per_page
        end_index = min(start_index + self.items_per_page, len(self.results))
        
        for toybox in self.results[start_index:end_index]:
            embed.add_field(
                name=toybox["name"],
                value=f"🔗 [Link]({toybox['url']})\n📌 {', '.join(toybox['tags'])}",
                inline=False
            )
        return embed

class ToyboxView(discord.ui.View):
    def __init__(self, search_callback):
        super().__init__(timeout=None)  # Make view persistent
        self.search_callback = search_callback
        
    @discord.ui.button(label="🏰 Disney", style=discord.ButtonStyle.primary, custom_id="toybox_disney")
    async def disney_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.category_callback(interaction, "Disney")
        
    @discord.ui.button(label="🦸 Marvel", style=discord.ButtonStyle.primary, custom_id="toybox_marvel")
    async def marvel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.category_callback(interaction, "Marvel")
        
    @discord.ui.button(label="✨ Star Wars", style=discord.ButtonStyle.primary, custom_id="toybox_starwars")
    async def starwars_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.category_callback(interaction, "Star Wars")
        
    @discord.ui.button(label="🎯 Other", style=discord.ButtonStyle.primary, custom_id="toybox_other")
    async def other_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.category_callback(interaction, "Other")

    async def category_callback(self, interaction: discord.Interaction, category: str):
        # Defer the response to prevent interaction timeout
        await interaction.response.defer(ephemeral=True)
        
        results = await self.search_callback(category)
        
        if not results:
            embed = discord.Embed(
                title=f"🎮 {category} Toyboxes",
                description=f"No Toyboxes found in the **{category}** category.",
                color=discord.Color.blue()
            )
            view = ResultView([], category)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            return
            
        results.sort(key=lambda toybox: toybox['name'].lower())
        view = ResultView(results, category)
        await interaction.followup.send(embed=view.create_embed(), view=view, ephemeral=True)
