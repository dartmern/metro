import datetime
import discord

from utils.embeds import create_embed

class PollModal(discord.ui.Modal):
    def __init__(self, *, title: str, question: str, close_time: datetime.datetime) -> None:
        super().__init__(title=title, timeout=300) # hard code 5m (fix later probs but most likely not)

        self._children = [discord.ui.TextInput(
                label=question,
                placeholder='Enter your response here...',
                style=discord.TextStyle.long
        )] 
        self.close_time = close_time

    async def on_submit(self, interaction: discord.Interaction) -> None:

        current_time = discord.utils.utcnow()
        if current_time > self.close_time:
            embed = create_embed('This poll has already closed. Sorry.', color=discord.Color.red())
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        await interaction.client.db.execute(
            'INSERT INTO poll_entries (poll_id, author_id, response) VALUES ($1, $2, $3)', 
            interaction.message.id,
            interaction.user.id,
            self.children[0].value
        )
        embed = create_embed('Your response has been recorded.', color=discord.Color.green())
        await interaction.response.send_message(f"Your response has been recorded.", ephemeral=True)

