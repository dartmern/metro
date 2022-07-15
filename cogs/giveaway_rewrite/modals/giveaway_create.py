import traceback
import discord
from discord import app_commands
from discord.ext import commands
from cogs.giveaway_rewrite.converters.winners import Winners

from utils.custom_context import MyContext
from utils.remind_utils import FutureTime

class GiveawayCreate(discord.ui.Modal, title='Create a Giveaway'):
    def __init__(self, *, interaction: discord.Interaction) -> None:
        super().__init__(timeout=None)

        self.interaction = interaction

    duration = discord.ui.TextInput(
        label='Duration',
        placeholder='Ex. 10 minutes'
    )
    winners = discord.ui.TextInput(
        label='Amount of winners',
        default='1',
        max_length=2
    )
    prize = discord.ui.TextInput(
        label='Prize',
        max_length=100
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        
        command: commands.Command = interaction.client.get_command('giveaway start')
        context: MyContext = await interaction.client.get_context(self.interaction)

        try:
            duration = await FutureTime(self.duration.value).convert(context, self.duration.value)
            winners = await Winners().convert(context, self.winners.value)

            await interaction.response.defer()

            await context.invoke(
                command, 
                duration=duration, 
                winners=winners,
                requirements = {
                    "role": [],
                    "bypass": [],
                    "blacklist": []            
                },
                prize=self.prize.value)

        except Exception as e:
            traceback.print_exception(e)
            return await interaction.followup.send(str(e), ephemeral=True)
            