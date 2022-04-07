import asyncio
import datetime
import re
from typing import List, Optional
import discord
from discord import app_commands
from discord.ext import commands
from bot import MetroBot
from .views.view import PollView
from utils.constants import TESTING_GUILD

from .time_helpers import HumanTime

async def setup(bot: MetroBot):
    await bot.add_cog(AdvancedPoll(bot))

class AdvancedPoll(commands.Cog, description="Create more advanced and engaging polls."):
    def __init__(self, bot: MetroBot) -> None:
        self.bot = bot

    @app_commands.command(name='poll')
    @app_commands.guilds(TESTING_GUILD)
    @app_commands.describe(duration='The duration this poll will last for.')
    @app_commands.describe(question='The question you would like to poll.')
    @app_commands.describe(channel='The channel to post this poll.')
    async def poll_command(
        self, 
        interaction: discord.Interaction, 
        duration: str,
        question: str,
        channel: Optional[discord.TextChannel]
    ):
        """Start a modal based poll."""
        channel = channel or interaction.channel

        if not interaction.permissions.manage_guild:
            return await interaction.response.send_message("You don't have the Manage Guild permission to use this command.", ephemeral=True)
        
        created_at = discord.utils.utcnow()
        try:
            duration = await HumanTime(duration).convert(created_at, duration)
        except Exception as e:
            return await interaction.response.send_message(str(e), ephemeral=True)

        if duration.dt > (created_at + datetime.timedelta(days=7)):
            return await interaction.response.send_message('Polls may not be longer than 7 days.', ephemeral=True)

        if duration.dt < (created_at + datetime.timedelta(seconds=59)):
            return await interaction.response.send_message('Polls may not be shorter than 1 minute.', ephemeral=True)
        
        await interaction.response.send_message(f'Creating poll in {channel.mention}...', ephemeral=True)
        #await asyncio.sleep(2) lmao

        title = f"{interaction.user} is asking a question."

        embed = discord.Embed(color=interaction.guild.me.color)
        embed.description = f"*{question}*"\
                            f"\n\nYou can press the button below to answer. "\
                            f"\nNote that your answer may be viewed by the poll's author."
        embed.set_author(name=title, icon_url=interaction.user.display_avatar.url)

        view = PollView(question=question, title=title)
        view.message = await channel.send(embed=embed, view=view)
        await interaction.edit_original_message(content=f'{self.bot.check} Created poll in {channel.mention}')

    
        
    

        

