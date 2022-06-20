import discord
from discord.ext import commands

from utils.custom_context import MyContext

class Winners(commands.Converter):
    async def convert(self, ctx: MyContext, argument: str) -> int:
        argument = argument.replace('w', '')
        try:
            return int(argument)
        except:
            raise commands.BadArgument(f'Could not convert "{argument}" into an amount of winners.')
            
        