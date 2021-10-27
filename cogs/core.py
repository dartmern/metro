import discord
from discord.ext import commands

import humanize

import datetime as dt

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

        elif isinstance(error, commands.BadArgument):
            await ctx.send(str(error))

        elif isinstance(error, commands.MissingRequiredArgument):

            missing = f"{str(error.param).split(':')[0]}"
            command = f"{ctx.prefix}{ctx.command} {ctx.command.signature}"
            separator = (' ' * (len(command.split(missing)[0]) - 1))
            indicator = ('^' * (len(missing) + 2))
            separator = (' '*8 + separator)

            await ctx.send(content=f"```yaml\nSyntax: {command}\n{separator}{indicator}\n{missing} is a required argument that is missing```",embed=await ctx.bot.help_command.get_command_help(ctx.command))

        elif isinstance(error, commands.errors.BotMissingPermissions):

            missing_perms = ', '.join(error.missing_permissions)
            try:
                return await ctx.send(
                f"I am missing the `{missing_perms}` permissions to do that."
            )
            except:
                return await ctx.author.send(
                f"I am missing the `{missing_perms}` permissions to do that."
                )

        elif isinstance(error, commands.errors.MissingPermissions):

            if ctx.author.id == ctx.bot.owner_id:
                await ctx.reinvoke()
                return

            missing_perms = ', '.join(error.missing_permissions)

            return await ctx.send(
                f"You are missing the `{missing_perms}` permission to do that!"
            )


        elif isinstance(error, commands.CommandNotFound):
            return

        elif isinstance(error, commands.CheckFailure):
            await ctx.send("You do not have permission to use this command.")
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

            if ctx.channel.id == 895082808161226803:
                await ctx.reinvoke()
                return

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
            em.set_footer(text='Spamming commands may result in a blacklist.')
            return await ctx.send(embed=em)



        else:
            

            embed = Embed(
            
                description=f"```py\n{error}``` \njust chill out. my dev got an angry dm and should know what happened"
            )
            embed.set_footer(text="Continuing to spam commands can result in a blacklist")
            m = await ctx.send(embed=embed)
            
            await ctx.send("_")
            print(f'This happened in:\n\nguild_id : {ctx.guild.id}\nmember_id : {ctx.author.id}\nmessage_link : {ctx.message.jump_url}')
            raise error


    
def setup(bot):
    bot.add_cog(core(bot))
