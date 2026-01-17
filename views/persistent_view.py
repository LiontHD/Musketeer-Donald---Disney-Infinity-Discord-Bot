import discord

class PersistentView(discord.ui.View):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.persistent = True

    async def on_timeout(self):
        return  # Prevents the view from timing out
