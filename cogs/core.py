import asyncio
import io
import re
from typing import List
import discord
from discord import errors
from discord import interactions
from discord.ext import commands

import humanize
import traceback

import datetime as dt
from bot import MetroBot
from utils import errors

from utils.useful import Cooldown, Embed
from utils.checks import check_dev
from utils.custom_context import MyContext

# thanks to leo for the missingrequiredargument handling
# https://github.com/LeoCx1000/discord-bots/blob/master/DuckBot/cogs/events.py#L201-L208

class ErrorView(discord.ui.View):
    def __init__(self, ctx : MyContext, traceback_string : str):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.traceback_string = traceback_string

        self.add_item(discord.ui.Button(label='Support Server', url='https://discord.gg/2ceTMZ9qJh'))


    @discord.ui.button(label='View Traceback', style=discord.ButtonStyle.blurple)
    async def view_traceback(self, _, interaction : discord.Interaction):

        embed = Embed()
        embed.title = 'Full Traceback'
        embed.description = f'```py\n{self.traceback_string}\n```'

        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except (discord.HTTPException, discord.Forbidden):
            await interaction.response.defer(ephemeral=False)
            await self.ctx.message.reply('Full traceback was too long:',file=discord.File(io.StringIO(self.traceback_string), filename='traceback.py'))
        



class core(commands.Cog, description="Core events."):
    def __init__(self, bot : MetroBot):
        self.bot = bot
        self.cooldown_mapping = commands.CooldownMapping.from_cooldown(3, 7, commands.BucketType.user)
        self.blacklist_message_sent = []
        self.error_channel = 912447757212606494
        self.error_emoji = 'https://images-ext-1.discordapp.net/external/b9E12Jxz-Fmlg25PNTCYYPrXMomcrAhxWu1JTM4MAh4/https/i.imgur.com/9gQ6A5Y.png'

    @property
    def emoji(self) -> str:
        return ''

    @commands.Cog.listener()
    async def on_command_error(self, ctx : MyContext, error):

        embed = Embed()
        embed.color = discord.Color.red()

        if ctx.command and ctx.command.has_error_handler():
            return

        elif isinstance(error, errors.UserBlacklisted):
            if ctx.interaction:
                info = await self.bot.db.fetchval('SELECT reason FROM blacklist WHERE member_id = $1', ctx.author.id) 
                return await ctx.interaction.response.send_message(f"You are blacklisted from Metro" + (f" for {info}" if info else ""), ephemeral=True)
            if ctx.author.id in self.blacklist_message_sent:
                #AKA This user haven't been reminded they are blacklisted.
                #Of course this is like a cache and isn't filled on startup but it can't really be spammed.
                return
            else:
                self.blacklist_message_sent.append(ctx.author.id)
                info = await self.bot.db.fetchval('SELECT reason FROM blacklist WHERE member_id = $1', ctx.author.id)
                return await ctx.send(
                    f"You are blacklisted from using Metro" + (f" for {info}" if info else "")
                )

        if isinstance(error, commands.CommandInvokeError):
            
            error = error.original
            if isinstance(error, discord.errors.Forbidden):
                embed.description = "I don't have the permissions to do that."\
                        "\nThis might be due to me missing permissions in the current channel or server."\
                        "\nThis might also be a issue with role hierarchy, try moving my role to the top of the role list."
                embed.set_author(name='Forbidden', icon_url=self.error_emoji)
                try:
                    return await ctx.send(embed=embed)
                except discord.Forbidden:
                    return await ctx.author.send(embed=embed)
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
                    await channel.send(content='Traceback string was too long to output.', embed=embed, file=discord.File(io.StringIO(traceback_string), filename='traceback.py'))
                
        elif isinstance(error, commands.MissingRequiredArgument):
            missing = f"{error.param.name}"
            command = f"{ctx.clean_prefix}{ctx.command} {ctx.command.signature}"
            separator = (' ' * (len([item[::-1] for item in command[::-1].split(missing[::-1], 1)][::-1][0]) - 1)) + (8*' ')
            indicator = ('^' * (len(missing) + 2))
            message = (f"\n```yaml\nSyntax: {command}\n{separator}{indicator}\n{missing} is a required argument that is missing.\n```")
                                    
            return await ctx.send(message, embed=await ctx.get_help(ctx.command))

        elif isinstance(error, commands.errors.BotMissingPermissions):
            missing_perms = ", ".join(["`%s`" % perm.replace('_', ' ').replace('guild', 'server').title() for perm in error.missing_permissions])
            embed.description = "I am missing the following permissions to run that command: \n%s" % missing_perms
            
            embed.set_author(name='Bot Missing Permissions', icon_url=self.error_emoji)

            try:
                return await ctx.send(embed=embed)
            except:
                return await ctx.author.send(embed=embed)

        elif isinstance(error, commands.errors.MissingPermissions):

            if check_dev(ctx.bot, ctx.author):
                await ctx.reinvoke()
                return

            embed.set_author(name='Missing Permissions', icon_url=self.error_emoji)

            missing_perms = ", ".join(["`%s`" % perm.replace('_', ' ').replace('guild', 'server').title() for perm in error.missing_permissions])
            embed.description = "You are missing the following permissions to run that command: \n%s" % missing_perms
            
            return await ctx.send(embed=embed)

        elif isinstance(error, commands.CommandNotFound):
            return # Might change this later and only handle this if the prefix is decently long.

        elif isinstance(error, commands.NotOwner):
            embed.set_author(name='Owner only command', icon_url=self.error_emoji)
            embed.description = "This command is reserved for developers/owners of %s" % self.bot.user.mention
            return await ctx.send(embed=embed)

        elif isinstance(error, commands.MessageNotFound):
            embed.description = f'Message "{error.argument}" was not found.\n'\
                "\n__**Acceptable arguments:**__"\
                "\n - Message URL"\
                "\n - Message ID (must be in the same channel as message)"\
                "\n - <Channel ID>-<Message ID> (press shift with developer mode)"
                
            embed.set_author(name='Message Not Found', icon_url=self.error_emoji)
            return await ctx.send(embed=embed)

        elif isinstance(error, commands.MemberNotFound):
            embed.description = f'Member "{error.argument}" was not found.\n'\
                "\nAcceptable arguments are as follows:"\
                f"\nID, mention, name#discrim, name, nickname"
            embed.set_author(name='Member Not Found', icon_url=self.error_emoji)
            return await ctx.send(embed=embed)
           
        elif isinstance(error, commands.RoleNotFound):
            embed.description = f'Role "{error.argument}" was not found.\n'\
                "\nAcceptable arguments are as follows:"\
                f"\nID, mention, name"
            embed.set_author(name='Role Not Found', icon_url=self.error_emoji)
            return await ctx.send(embed=embed)

        elif isinstance(error, commands.ChannelNotFound):
            embed.description = f'Channel "{error.argument}" was not found.\n'\
                "\nAcceptable arguments are as follows:"\
                f"ID, mention, name"
            embed.set_author(name='Channel Not Found', icon_url=self.error_emoji)
            return await ctx.send(embed=embed)

        elif isinstance(error, commands.errors.BadUnionArgument):
            def _get_name(x):
                try:
                    return x.__name__
                except AttributeError:
                    if hasattr(x, "__origin__"):
                        return repr(x)
                    return x.__class__.__name__

            to_string = [_get_name(x) for x in error.converters]
            if len(to_string) > 2:
                fmt = "{}, or {}".format(", ".join(to_string[:-1]), to_string[-1])
            else:
                fmt = " or ".join(to_string)
            embed.set_author(name='Bad Union Argument', icon_url=self.error_emoji)
            embed.description = f'I could not convert "{error.param.name}" into a {fmt}.'
            return await ctx.send(embed=embed)

        elif isinstance(error, commands.CommandOnCooldown):

            if check_dev(ctx.bot, ctx.author):
                await ctx.reinvoke() # bypass cooldowns for now
                return 

            command = ctx.command
            cooldown = discord.utils.find(lambda x: isinstance(x, Cooldown), command.checks) or Cooldown(1, 3, 1, 1,
                                                                                                        commands.BucketType.user)

            default_cooldown_per = cooldown.default_mapping._cooldown.per
            altered_cooldown_per = cooldown.altered_mapping._cooldown.per

            default_cooldown_rate = cooldown.default_mapping._cooldown.rate
            altered_cooldown_rate = cooldown.altered_mapping._cooldown.rate

            cooldowns = ""
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
                await self.bot.add_to_blacklist(ctx, ctx.author, f'Spamming Commands (auto-ban)', silent=True)
                if not check_dev(self.bot, ctx.author):
                    await ctx.send("You have been blacklisted for spamming commands. (auto-ban)")
                else:
                    return
            else:
                await ctx.send(embed=em)

        elif isinstance(error, commands.TooManyArguments):
            return await ctx.send("Too many arguments were passed to this command!")

        elif isinstance(error, commands.CheckFailure):
            return

        elif isinstance(error, commands.errors.DisabledCommand):
            return await ctx.send(str(error))

        elif isinstance(error, commands.BadArgument):
            return await ctx.send(str(error))

        elif isinstance(error, commands.CommandError):
            return await ctx.send(str(error))

        else:
                # technically this can't be triggered
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
                


def setup(bot):
    bot.add_cog(core(bot))
