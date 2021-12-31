import discord
from discord.ext import commands

from bot import MetroBot

def setup(bot: MetroBot):
    bot.add_cog(basic_cog(bot))

class basic_cog(commands.Cog, description=' '):
    def __init__(self, bot: MetroBot):
        self.bot = bot

    @property
    def emoji(self) -> str:
        return ''



# This is meant for easy copy/paste to make a new cog
#
# Things you need to edit:
# - cog.name (change the class name)
# - cog.description (change the description kwarg in the class)
# - cog.emoji (change the emoji property/attribute inside the class)