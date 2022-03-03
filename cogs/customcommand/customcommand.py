from typing import Optional
import discord
from discord.ext import commands

from bot import MetroBot
from cogs.converters.tag import TagConverter
from cogs.customcommand.helpers import cleanup_code
from utils.custom_context import MyContext

from .handler import process
from ..converters.name import TagName

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

    @customcommand.command(name='add', aliases=['create'])
    @commands.has_guild_permissions(manage_guild=True)
    async def customcommand_add(
        self, ctx: MyContext, tag_name: TagName, *, tagscript: str):
        """
        Add a customcommand with TagScript.
        This supports codeblocks.
        """
        tagscript = cleanup_code(tagscript)
        
        try:
            await self.bot.db.execute(
                "INSERT INTO customcommands(name, tagscript, guild_id) VALUES ($1, $2, $3)", 
                tag_name,
                tagscript,
                ctx.guild.id)
        except Exception as e:
            return await ctx.send(f"Something went wrong: {e}")

        await ctx.send(f"Tag `{tag_name}` added.")


    @customcommand.command(name='make')
    @commands.has_guild_permissions(manage_guild=True)
    async def customcommand_make(self, ctx: MyContext):
        """Make a custom command interactively."""
        pass

    @customcommand.command(name='invoke')
    async def customcommand_invoke(self, ctx: MyContext, tag_name: TagConverter, *, args: Optional[str] = ""):
        """
        Manually invoke a tag.
        
        This more of a lower level core command.
        """
        await process(ctx, tag_name)

    @customcommand.command(name='run')
    @commands.is_owner()
    async def customcommand_run(self, ctx: MyContext, *, tagscript: str):
        """
        Run some tagscript.
        This supports codeblocks and markdown.

        Please keep in mind that this is owner-only.
        """

        tagscript = cleanup_code(tagscript)
        await process(ctx, tagscript)
        