import discord

from .modal import PollModal

class PollView(discord.ui.View):
    def __init__(self, *, question: str, title: str):
        super().__init__(timeout=None)
        self.message: discord.Message = None
        self.question = question
        self.title = title

    @discord.ui.button(label='Answer')
    async def answer_button(
        self, 
        interaction: discord.Interaction, 
        button: discord.ui.Button
    ):
        item = discord.ui.TextInput(
            label=self.question,
            placeholder='Enter your response here...',
            style=discord.TextStyle.long
        )

        modal = PollModal(title=self.title)
        modal.add_item(item)
        
        await interaction.response.send_modal(modal)