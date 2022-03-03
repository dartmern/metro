from discord.ext import commands

from utils.custom_context import MyContext

class TagConverter(commands.Converter):
    async def convert(self, ctx: MyContext, argument: str):
        if not ctx.guild:
            raise commands.BadArgument("Tag may only be used inside guilds.")

        tag = await ctx.bot.db.fetchval(
            "SELECT tagscript FROM customcommands WHERE name = $1 AND guild_id = $2", argument, ctx.guild.id)
        if not tag:
            raise commands.BadArgument("Tag not found.")
        return tag