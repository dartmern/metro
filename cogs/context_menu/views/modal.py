import discord

class PollModal(discord.ui.Modal):
    def __init__(self, *, title: str) -> None:
        super().__init__(title=title, timeout=300) # hard code 5m (fix later probs but most likely not)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(f"Your response has been recorded.", ephemeral=True)

