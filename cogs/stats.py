from discord.ext import commands

from bot import MetroBot

async def setup(bot: MetroBot):
    await bot.add_cog(stats(bot))

class stats(commands.Cog, description='Bot statistics tracking related.'):
    def __init__(self, bot: MetroBot):
        self.bot = bot

    @property
    def emoji(self) -> str:
        return '\U0001f4c8'


