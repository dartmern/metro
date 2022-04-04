import discord
from discord.ext import commands

from bot import MetroBot
from utils.custom_context import MyContext

async def setup(bot: MetroBot):
    await bot.add_cog(automod(bot))

class automod(commands.Cog, description='Manage auto-moderation settings such as filters..'):
    def __init__(self, bot: MetroBot):
        self.bot = bot

    @property
    def emoji(self) -> str:
        return self.bot.emotes['moderator']

    @commands.group(name='anti-scam', aliases=['anti-phish'])
    @commands.has_guild_permissions(manage_guild=True)
    @commands.bot_has_guild_permissions(manage_messages=True)
    async def anti_scam(self, ctx: MyContext):
        """Manage the anti-scam link prevention system"""
        await ctx.help()

        







