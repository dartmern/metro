import io
import re
from typing import List
import discord
from discord import errors
from discord.ext import commands

import humanize
import traceback

import datetime as dt
from bot import MetroBot
from utils.errors import UserBlacklisted

from utils.useful import Cooldown, Embed
from utils.checks import check_dev
from utils.custom_context import MyContext


class ErrorView(discord.ui.View):
    def __init__(self, ctx : MyContext, traceback_string : str):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.traceback_string = traceback_string

        self.add_item(discord.ui.Button(label='Support Server', url='https://discord.gg/2ceTMZ9qJh'))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.ctx.author.id:
            return True
        await interaction.response.send_message('This menu cannot be controlled by you, sorry!', ephemeral=True)
        return False

    @discord.ui.button(label='View Traceback', style=discord.ButtonStyle.blurple)
    async def view_traceback(self, button : discord.ui.Button, interaction : discord.Interaction):

        embed = Embed()
        embed.title = 'Full Traceback'
        embed.description = f'```py\n{self.traceback_string}\n```'

        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except (discord.HTTPException, discord.Forbidden):
            await interaction.channel.send('Full traceback was too long:',file=discord.File(io.StringIO(traceback_string)), filename='traceback.py')
        



class core(commands.Cog, description="Core events."):
    def __init__(self, bot : MetroBot):
        self.bot = bot
        self.cooldown_mapping = commands.CooldownMapping.from_cooldown(3, 7, commands.BucketType.user)
        self.blacklist_message_sent = []
        self.error_channel = 912447757212606494

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
                traceback_string = "".join(traceback.format_exception(
                    etype=None, value=error, tb=error.__traceback__))

                view = ErrorView(ctx, traceback_string)
                await ctx.send(':warning: **An error occurred!**', view=view)

                channel = self.bot.get_channel(self.error_channel)

                embeds = []
                embed = Embed()
                embed.title = 'An error occurred.'
                if ctx.guild:
                    embed.description = f'```yaml\nby: {ctx.author} (id: {ctx.author.id})'\
                                        f'\nguild_id: {ctx.guild.id}'\
                                        f'\nchannel_id: {ctx.channel.id}'\
                                        f'\nmessage_id: {ctx.message.id}'\
                                        f'\ncommand: {ctx.message.content[0:1500]}'\
                                        f'\nis bot admin: {await ctx.emojify(ctx.me.guild_permissions.administrator, False)}\n```'
                else:
                    embed.description = f'```yaml\nby: {ctx.author} (id: {ctx.author.id})'\
                                        f'\ncommand: {ctx.message.content[0:1500]}\n```'  

                traceback_embed = Embed(color=discord.Colour.red())
                traceback_embed.title = 'Full Traceback'
                traceback_embed.description = f'```py\n{traceback_string}\n```'  
                
                embeds.append(embed)
                embeds.append(traceback_embed)
                
                try:
                    await channel.send(embeds=embeds)
                except (discord.Forbidden, discord.HTTPException):
                    await channel.send(content='Traceback string was too long to output.', embed=embed, file=discord.File(io.StringIO(traceback_string)))
                
        elif isinstance(error, commands.BadArgument):
            await ctx.send(str(error))

        elif isinstance(error, commands.MissingRequiredArgument):
            return await self.bot.help_command.send_missing_required_argument(ctx, error)

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

            if check_dev(ctx.bot, ctx.author):
                #await ctx.reinvoke()
                #return
                pass

            command = ctx.command
            cooldown = discord.utils.find(lambda x: isinstance(x, Cooldown), command.checks) or Cooldown(1, 3, 1, 1,
                                                                                                        commands.BucketType.user)

            default_cooldown_per = cooldown.default_mapping._cooldown.per
            altered_cooldown_per = cooldown.altered_mapping._cooldown.per

            default_cooldown_rate = cooldown.default_mapping._cooldown.rate
            altered_cooldown_rate = cooldown.altered_mapping._cooldown.rate

            cooldowns = f""
            if default_cooldown_rate is not None:
                cooldowns += (
                    f"\n\n**Cooldowns:**\nDefault: `{default_cooldown_rate}` time(s) every `{default_cooldown_per}` seconds\nTester: `{altered_cooldown_rate}` time(s) every `{altered_cooldown_per}` seconds"
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
                await ctx.send(embed=em)

        elif isinstance(error, commands.errors.DisabledCommand):
            return await ctx.send(
                str(error)
            )

        elif isinstance(error, commands.errors.BadUnionArgument):
            return await ctx.send(str(error))

        elif isinstance(error, commands.CommandError):
            return await ctx.send(str(error))
        
        elif isinstance(error, UserBlacklisted):
                return await ctx.send(f"You are blacklisted from using my commands.")

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

                channel = self.bot.get_channel(self.error_channel)

                traceback_string = "".join(traceback.format_exception(
                    etype=None, value=error, tb=error.__traceback__))

                if ctx.guild:
                    command_info = f"```yaml\nby: {ctx.author} (id: {ctx.author.id})" \
                                    f"\ncommand: {ctx.message.content[0:1700]}" \
                                    f"\nguild_id: {ctx.guild.id} - channel_id: {ctx.channel.id}"\
                                    f"\nis bot admin: {await ctx.emojify(ctx.me.guild_permissions.administrator, False)}"\
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

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload : discord.RawReactionActionEvent):
        if payload.member == self.bot.user:
            return
        if payload.channel_id == self.error_channel:
            if str(payload.emoji) == '🗑':
                message = await self.bot.get_channel(payload.channel_id).fetch_message(payload.message_id)
                if not message.author == self.bot.user:
                    return
                old_content = message.content
                embed = Embed()
                embed.description = f"{self.bot.check} Error was resolved by the developers."
                
                await message.edit(content=old_content, embed=embed)
                await message.clear_reactions()
            
            
        

    @commands.command(aliases=['dbe'])
    @commands.is_owner()
    async def debug_error(self, ctx, error_id : str):

        message = await commands.MessageConverter().convert(ctx, error_id)
        if message is None:
            raise commands.MessageNotFound('Message not found!')

        await ctx.send(f"Message Link: {message.jump_url}\nMessage Guild ID: {message.guild.id}\nMessage Author ID: {message.author.id}\n\nMessage Content: {message.content}")


    
def setup(bot):
    bot.add_cog(core(bot))
