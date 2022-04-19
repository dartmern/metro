import datetime
from typing import Optional
import discord

from utils.embeds import create_embed

from .modal import PollModal

class PollView(discord.ui.View):
    def __init__(self, *, question: str, title: str, close_time: datetime.datetime):
        super().__init__(timeout=None)

        self.message: discord.Message = None
        self.question = question
        self.title = title
        self.close_time = close_time

    @discord.ui.button(label='Answer')
    async def answer_button(
        self, 
        interaction: discord.Interaction, 
        button: discord.ui.Button
    ):
        data = await interaction.client.db.fetchval(
            'SELECT * FROM poll_entries WHERE poll_id = $1 AND author_id = $2',
            interaction.message.id,
            interaction.user.id
        )
        if data:
            embed = create_embed('You have already responded to this poll.', color=discord.Color.orange())
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        modal = PollModal(title=self.title, question=self.question, close_time=self.close_time)
        await interaction.response.send_modal(modal)