from typing import Optional
import discord
from discord.ext import commands

from bot import MetroBot
from utils.custom_context import MyContext

from .handler import process

class customcommands(commands.Cog, description='Make custom commands with tagscript!'):
    def __init__(self, bot: MetroBot):
        self.bot = bot

    @property
    def emoji(self) -> str:
        return '\U0001f6e0'

    @commands.group(name='customcommand', aliases=['cc'], invoke_without_command=True)
    @commands.has_guild_permissions(manage_guild=True)
    async def customcommand(self, ctx: MyContext):
        """
        Manage custom commands.
        """
        await ctx.help()

    @customcommand.command(name='make')
    @commands.has_guild_permissions(manage_guild=True)
    async def customcommand_make(self, ctx: MyContext):
        """Make a custom command interactively."""
        pass

    @customcommand.command(name='invoke')
    async def customcommand_invoke(self, ctx: MyContext, tag_name: str, *, args: Optional[str] = ""):
        """
        Manually invoke a tag.
        
        This more of a lower level core command.
        """
        pass

    @customcommand.command(name='run')
    @commands.is_owner()
    async def customcommand_run(self, ctx: MyContext, *, tagscript: str):
        """Run some tagscript."""
        await process(ctx, tagscript)
        