from discord.ext import commands

from utils.custom_context import MyContext

class TagName(commands.Converter):
    async def convert(self, ctx: MyContext, argument: str):
        command = ctx.bot.get_command(argument)
        if command:
            raise commands.BadArgument(f"`{argument}` is already a registered default command.")

        tag = await ctx.bot.db.fetchval(
            "SELECT * FROM customcommands WHERE name = $1 AND guild_id = $2", argument, ctx.guild.id)
        if tag:
            raise commands.BadArgument(f"`{argument}` is already a registered tag or alias.")

        return "".join(argument.split())