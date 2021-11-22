import io
from typing import List
import discord
from discord import errors
from discord.ext import commands

import humanize
import traceback

import datetime as dt
from utils.errors import UserBlacklisted

from utils.useful import Cooldown, Embed
from utils.checks import check_dev
from utils.custom_context import MyContext



class core(commands.Cog, description="Core events."):
    def __init__(self, bot):
        self.bot = bot
        self.cooldown_mapping = commands.CooldownMapping.from_cooldown(3, 7, commands.BucketType.member)
        self.blacklist_message_sent : List = []

    async def blacklist(self, user):
        query = """
                INSERT INTO blacklist(member_id, is_blacklisted) VALUES ($1, $2) 
                """

        await self.bot.db.execute(query, user.id, True)

        self.bot.blacklist[user.id] = True



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
                error_id = f"{ctx.message.channel.id}-{ctx.message.id}"
                view = discord.ui.View()
                button = discord.ui.Button(url=self.bot.support, emoji='🛠️', label='Support Server')
                view.add_item(button)
                await ctx.send(f"An error occurred!\nJoin my support server for more information.\n\nError ID: {error_id}", view=view)

                channel = self.bot.get_channel(912447757212606494)

                traceback_string = "".join(traceback.format_exception(
                    etype=None, value=error, tb=error.__traceback__))

                if ctx.guild:
                    command_info = f"```yaml\nby: {ctx.author} (id: {ctx.author.id})" \
                                    f"\ncommand: {ctx.message.content[0:1700]}" \
                                    f"\nguild_id: {ctx.guild.id} - channel_id: {ctx.channel.id}"\
                                    f"\nis bot admin: {'✅' if ctx.me.guild_permissions.administrator else '❌'}"\
                                    f"\ntop role pos: {ctx.me.top_role.position}\n```"
                else:
                    command_info = f"by: {ctx.author} (id: {ctx.author.id})"\
                                    f"command: {ctx.message.content[0:1700]}" \
                                    f"this command was executed in dms"

                send = f"\n{command_info}\nerror_id: `{error_id}`\n**Command raised an error:**\n```py\n{traceback_string}\n```\n"
                if len(send) < 2000:
                    try:
                        await channel.send(send)
                    except (discord.Forbidden, discord.HTTPException):
                        await channel.send(
                            f"\n{command_info}\n\nCommand raised an error:\n",
                            file=discord.File(io.StringIO(traceback_string), filename='traceback.py')
                        )
                
                else:
                    await channel.send(
                            f"\n{command_info}\n\nCommand raised an error:\n",
                            file=discord.File(io.StringIO(traceback_string), filename='traceback.py'),
                    )
                            


                print("----------------------------")
                print("ERROR!")
                print("USER ID: {}".format(ctx.author.id))
                print("ERROR ID: {}".format(error_id))
                print("----------------------------")
                
                raise error

        elif isinstance(error, commands.BadArgument):
            await ctx.send(str(error))

        elif isinstance(error, commands.MissingRequiredArgument):

            missing = f"{error.param.name}"
            command = f"{ctx.clean_prefix}{ctx.command} {ctx.command.signature}"
            separator = (' ' * (len([item[::-1] for item in command[::-1].split(missing[::-1], 1)][::-1][0]) - 1)) + (8*' ')
            indicator = ('^' * (len(missing) + 2))
            return await ctx.send(
                                  f"\n```yaml\nSyntax: {command}\n{separator}{indicator}"
                                  f'\n{missing} is a required argument that is missing.\n```',
                                  embed=await self.bot.help_command.get_command_help(ctx.command))

            
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

            if check_dev(ctx.bot, ctx.author):
                await ctx.reinvoke()
                return

            missing_perms = ', '.join(error.missing_permissions)

            return await ctx.send(
                f"You are missing the `{missing_perms}` permission to do that!"
            )


        elif isinstance(error, commands.CommandNotFound):
            return

        elif isinstance(error, commands.CheckFailure):
            return

        elif isinstance(error, commands.MessageNotFound):
            return await ctx.send(
                f"Message not found!"
            )

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
            em.set_footer(text='Spamming commands may result in a blacklist.')

            
            bucket = self.cooldown_mapping.get_bucket(ctx.message)
            retry_after = bucket.update_rate_limit()
            
            if retry_after:
                await self.blacklist(ctx.author)
                return await ctx.reply(f"You have been blacklisted for spamming commands.\nJoin my support server for a appeal: {self.bot.support}")
            else:
                return await ctx.send(embed=em)

        elif isinstance(error, commands.errors.DisabledCommand):
            return await ctx.send(
                f"This command is globally disabled."
            )

        elif isinstance(error, commands.errors.BadUnionArgument):
            return await ctx.send(str(error))

        elif isinstance(error, commands.CommandError):
            return await ctx.send(str(error))

        elif isinstance(error, UserBlacklisted):
            if ctx.author.id in self.blacklist_message_sent:
                return
            else:
                self.blacklist_message_sent.append(ctx.author.id)
                return await ctx.send(
                    f"You are blacklisted from using Metro.\nJoin my support server to appeal: {self.bot.support}"
                )
        else:
                error_id = f"{ctx.message.channel.id}-{ctx.message.id}"
                view = discord.ui.View()
                button = discord.ui.Button(url=self.bot.support, emoji='🛠️', label='Support Server')
                view.add_item(button)
                await ctx.send(f"An error occurred!\nJoin my support server for more information.\n\nError ID: {error_id}", view=view)

                channel = self.bot.get_channel(912447757212606494)

                traceback_string = "".join(traceback.format_exception(
                    etype=None, value=error, tb=error.__traceback__))

                if ctx.guild:
                    command_info = f"```yaml\nby: {ctx.author} (id: {ctx.author.id})" \
                                    f"\ncommand: {ctx.message.content[0:1700]}" \
                                    f"\nguild_id: {ctx.guild.id} - channel_id: {ctx.channel.id}"\
                                    f"\nis bot admin: {'✅' if ctx.me.guild_permissions.administrator else '❌'}"\
                                    f"\ntop role pos: {ctx.me.top_role.position}\n```"
                else:
                    command_info = f"by: {ctx.author} (id: {ctx.author.id})"\
                                    f"command: {ctx.message.content[0:1700]}" \
                                    f"this command was executed in dms"

                send = f"\n{command_info}\nerror_id: `{error_id}`\n**Command raised an error:**\n```py\n{traceback_string}\n```\n"
                if len(send) < 2000:
                    try:
                        await channel.send(send)
                    except (discord.Forbidden, discord.HTTPException):
                        await channel.send(
                            f"\n{command_info}\n\nCommand raised an error:\n",
                            file=discord.File(io.StringIO(traceback_string), filename='traceback.py')
                        )
                
                else:
                    await channel.send(
                            f"\n{command_info}\n\nCommand raised an error:\n",
                            file=discord.File(io.StringIO(traceback_string), filename='traceback.py'),
                    )
                            


                print("----------------------------")
                print("ERROR!")
                print("USER ID: {}".format(ctx.author.id))
                print("ERROR ID: {}".format(error_id))
                print("----------------------------")
                
                raise error

    @commands.command(aliases=['dbe'])
    @commands.is_owner()
    async def debug_error(self, ctx, error_id : str):

        message = await commands.MessageConverter().convert(ctx, error_id)
        if message is None:
            raise commands.MessageNotFound('Message not found!')

        await ctx.send(f"Message Link: {message.jump_url}\nMessage Guild ID: {message.guild.id}\nMessage Author ID: {message.author.id}\n\nMessage Content: {message.content}")


    
def setup(bot):
    bot.add_cog(core(bot))
