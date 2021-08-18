import discord
from discord.ext import commands, tasks

import humanize
import asyncio
import datetime as dt
import re
import binascii
import base64
import yarl

from utils.useful import Cooldown, Embed



class core(commands.Cog, description="Core events."):
    def __init__(self, bot):
        self.bot = bot


    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):

        if ctx.command and ctx.command.has_error_handler():
            return


        if isinstance(error, commands.CommandInvokeError):
            
            error = error.original
            if isinstance(error, discord.errors.Forbidden):
                try:
                    return await ctx.reply(
                        f"I am missing permissions to do that!"
                    )
                except discord.Forbidden:
                    return await ctx.author.send(
                        f"I am missing permissions to do that!"
                    )
            else:
                print(error)
                return

        elif isinstance(error, commands.MissingRequiredArgument):

            missing = f"{str(error.param).split(':')[0]}"
            command = f"{ctx.prefix}{ctx.command} {ctx.command.signature}"
            separator = (' ' * (len(command.split(missing)[0]) - 1))
            indicator = ('^' * (len(missing) + 2))
            separator = (' '*8 + separator)

            await ctx.send(content=f"```yaml\nSyntax: {command}\n{separator}{indicator}\n{missing} is a required argument that is missing```",embed=ctx.bot.help_command.get_command_help(ctx.command))

        elif isinstance(error, commands.BotMissingPermissions):
            return await ctx.send(
                f"I am missing the `{error.missing_permissions[0]}` permission to do that."
            )

        elif isinstance(error, commands.MissingPermissions):

            return await ctx.send(
                f"You are missing the `{error.missing_permissions[0]}` permission to do that!"
            )


        elif isinstance(error, commands.CommandNotFound):
            return

        elif isinstance(error, commands.CheckFailure):
            await ctx.send("You do not have permission to use this command!")
            return

        elif isinstance(error, commands.MemberNotFound):
            return await ctx.send(
                f"I couldn't find the member `{error.argument}`\nTry mentioning them and check for spelling."
            )
        elif isinstance(error, commands.RoleNotFound):
            return await ctx.send(
                f"I couldn't find the role `{error.argument}`\nTry mentioning the role and check for spelling."
            )

        elif isinstance(error, commands.ChannelNotFound):
            return await ctx.send(
                f"I couldn't find the channel `{error.argument}`\nTry mentioning it and check for spelling."
            )

        elif isinstance(error, commands.CommandOnCooldown):
            command = ctx.command
            default = discord.utils.find(
                lambda c: isinstance(c, Cooldown), command.checks
            ).default_mapping._cooldown.per

            cooldowns = f""
            if default is not None:
                cooldowns += (
                    f"\n\n**Cooldowns:**\nDefault: `{default}s`"
                )
            em = Embed(
                description=f"You are on cooldown! Try again in **{humanize.precisedelta(dt.timedelta(seconds=error.retry_after), format='%.0f' if error.retry_after > 1 else '%.1f')}**"
                            + cooldowns
            )
            return await ctx.send(embed=em)

        elif isinstance(error, commands.BadArgument):
            await ctx.send(str(error))

        else:
            print(error)

            embed = Embed(
                title=error,
                description=f"```py\n{error}``` \nPlease join my [support server](https://discord.gg/2ceTMZ9qJh) for more information\n - This bug has been reported to our developers and is being fixed"
            )
            embed.set_footer(text="Continuing to spam commands can result in a blacklist")
            m = await ctx.send(embed=embed)


    @commands.Cog.listener()
    async def on_message(self, message):

        if message.author.bot:
            return

        if message.content.startswith(f"<@!{self.bot.user.id}>") and \
            len(message.content) == len(f"<@!{self.bot.user.id}>"):

            await message.channel.send(f"My prefix here is: `m.` \nFor more information type `m.help`")



def setup(bot):
    bot.add_cog(core(bot))
