import sys
from typing import Any, TYPE_CHECKING
import discord
from discord import errors
from discord.ext import commands
from discord.app_commands import AppCommandError
from discord import app_commands

import io
import humanize
import traceback
import pomice
import datetime as dt

from bot import MetroBot
from cogs.music import NotVoted
from utils import errors
from utils.constants import DEVELOPER_ROLE, ERROR_CHANNEL_ID
from utils.useful import Embed
from utils.checks import check_dev
from utils.custom_context import MyContext

if TYPE_CHECKING:
    from cogs.stats import stats

# thanks to leo for the missingrequiredargument handling
# https://github.com/LeoCx1000/discord-bots/blob/master/DuckBot/cogs/events.py#L201-L208

class ErrorView(discord.ui.View):
    def __init__(self, ctx : MyContext, traceback_string : str):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.traceback_string = traceback_string

        self.add_item(discord.ui.Button(label='Support Server', url='https://discord.gg/2ceTMZ9qJh'))


    @discord.ui.button(label='View Traceback', style=discord.ButtonStyle.blurple)
    async def view_traceback(self, interaction : discord.Interaction, button: discord.ui.Button):

        embed = Embed(color=discord.Colour.red(), title='Full Trackback')
        embed.description = f'```py\n{self.traceback_string}\n```'

        try:
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except (discord.HTTPException, discord.Forbidden):
            await interaction.response.defer(ephemeral=False)
            await self.ctx.message.reply('Full traceback was too long:',file=discord.File(io.StringIO(self.traceback_string), filename='traceback.py'))
        
class core(commands.Cog, description="Core events."):
    def __init__(self, bot : MetroBot):
        self.bot = bot
        self.cooldown_mapping = commands.CooldownMapping.from_cooldown(3, 5, commands.BucketType.user)
        self.blacklist_message_sent = []
        self.error_channel = ERROR_CHANNEL_ID
        self.error_emoji = 'https://images-ext-1.discordapp.net/external/b9E12Jxz-Fmlg25PNTCYYPrXMomcrAhxWu1JTM4MAh4/https/i.imgur.com/9gQ6A5Y.png'

        self.bot.tree.on_error = self.on_app_command_error

        # cooldowns
        self.normal_cd = commands.CooldownMapping.from_cooldown(3, 8, commands.BucketType.user)
        self.premium_cd = commands.CooldownMapping.from_cooldown(3, 6, commands.BucketType.user)

    @property
    def emoji(self) -> str:
        return ''

    async def bot_check(self, ctx: MyContext) -> bool:
        if ctx.invoked_with.lower() in ['help', 'h', 'command']:
            return True

        if not ctx.guild:
            return True

        if self.bot.premium_guilds.get(ctx.guild.id) or self.bot.premium_users.get(ctx.author.id):
            bucket = self.premium_cd.get_bucket(ctx.message)
        else:
            bucket = self.premium_cd.get_bucket(ctx.message)
        retry_after = bucket.update_rate_limit()
        if retry_after:
            raise commands.CommandOnCooldown(bucket, retry_after, commands.BucketType.user)
        else:
            return True

    async def on_app_command_error(
        self, interaction: discord.Interaction, error: AppCommandError):
        """Handle application command errors."""
        ctx: MyContext = await self.bot.get_context(interaction)
        embed = discord.Embed(color=discord.Color.red())

        if isinstance(error, errors.UserBlacklistedInteraction):

            self.blacklist_message_sent.append(ctx.author.id)
            info = await self.bot.db.fetchval('SELECT reason FROM blacklist WHERE member_id = $1', ctx.author.id)
            return await ctx.send(
                    f"You are blacklisted from using Metro" + (f" for {info}" if info else ""), hide=True
                )

        elif isinstance(error, app_commands.errors.BotMissingPermissions):
            missing_perms = ", ".join(["`%s`" % perm.replace('_', ' ').replace('guild', 'server').title() for perm in error.missing_permissions])
            embed.description = "I am missing the following permissions to run that command: \n%s" % missing_perms
            
            embed.set_author(name='Bot Missing Permissions', icon_url=self.error_emoji)

            try:
                return await ctx.send(embed=embed, hide=True)
            except:
                return await ctx.author.send(embed=embed)

        elif isinstance(error, app_commands.errors.MissingPermissions):
            if check_dev(ctx.bot, ctx.author):
                await ctx.reinvoke()
                return

            embed.set_author(name='Missing Permissions', icon_url=self.error_emoji)

            missing_perms = ", ".join(["`%s`" % perm.replace('_', ' ').replace('guild', 'server').title() for perm in error.missing_permissions])
            embed.description = "You are missing the following permissions to run that command: \n%s" % missing_perms
            
            return await ctx.send(embed=embed, hide=True)

        ctx = await self.bot.get_context(interaction)

        traceback_string = "".join(traceback.format_exception(
                    error, value=error, tb=error.__traceback__))

        view = ErrorView(ctx, traceback_string)

        #if check_dev(self.bot, ctx.author):
            #return await ctx.send("\U000026a0 **An error has occurred!**\nSince you are a developer this error has not been logged.", view=view, reply=False)
                
        embed = discord.Embed(color=discord.Colour.red(), title='Command Error')
        embed.description = "Oops! This command seems to have errored. The error has been fowarded to the owner and will be fixed soon. Please refrain from repeatedly invoking this command in the meanwhile."\
                                    f"\n\nIn the meantime you can join my support server to gain some context on this error and give any extra information by clicking the button below. You can send the error ID below in #support and the command you ran."
        message = await ctx.send(embed=embed, view=view, reply=False)
        embed.description += f'\n```prolog\nError ID: {message.id}\n```'
        await message.edit(embed=embed)

        channel = self.bot.get_channel(self.error_channel)

        embeds = []
        embed = Embed()
        embed.title = 'Command Error'
        embed.set_footer(text=f'ID: {ctx.channel.id}-{message.id}')
        if ctx.guild:
            embed.description = f'\n```prolog\nAuthor: {ctx.author} ({ctx.author.id})'\
                                        f'\nGuild ID: {ctx.guild.id}'\
                                        f'\nChannel ID: {ctx.channel.id}'\
                                        f'\nCommand: {ctx.command.name}'\
                                        f'\nAdmin: {await ctx.emojify(ctx.me.guild_permissions.administrator, False)}\n```'
        else:
            embed.description = f'```prolog\nID: {message.id}'\
                                        f'\nAuthor: {ctx.author} (ID: {ctx.author.id})'\
                                        f"\nCommand: {ctx.command.name}\n```"

        traceback_embed = Embed(color=discord.Colour.red())
        traceback_embed.title = 'Full Traceback'
        traceback_embed.description = f'```py\n{traceback_string}\n```'  
                
        embeds.append(embed)
        embeds.append(traceback_embed)
                
        try:
            await self.bot.error_logger.send(f"{channel.guild.get_role(DEVELOPER_ROLE).mention} ID: {message.id}", embeds=embeds)
        except (discord.Forbidden, discord.HTTPException):
            await self.bot.error_logger.send(content=f'{channel.guild.get_role(DEVELOPER_ROLE).mention} ID: {message.id} | Traceback string was too long to output.', embed=embed, file=discord.File(io.StringIO(traceback_string), filename='traceback.py'))
        return 

    async def on_command_error(self, ctx : MyContext, error):
        """Handle message command / traditional command errors."""

        cog: stats = self.bot.get_cog('stats')
        await cog.register_command(ctx)

        embed = Embed()
        embed.color = discord.Color.red()

        if ctx.command and ctx.command.has_error_handler():
            return

        if not ctx.command:
            return

        if ctx.command.cog.has_error_handler():
            return
        
        elif ctx.interaction and not ctx.guild:
            embed.description = "This command isn't available in my messages."
            return await ctx.send(embed=embed)

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

        if isinstance(error, (commands.CommandInvokeError, commands.HybridCommandError)):
            
            error = error.original
            if isinstance(error, app_commands.errors.CommandInvokeError):
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
            elif isinstance(error, pomice.exceptions.NoNodesAvailable):
                return await ctx.send(f"{self.bot.emotes['cross']} There are no lavalink nodes available.")
            elif isinstance(error, discord.errors.ClientException):
                return await ctx.send(str(error))
            else:
                traceback_string = "".join(traceback.format_exception(
                    error, value=error, tb=error.__traceback__))

                view = ErrorView(ctx, traceback_string)

                if check_dev(self.bot, ctx.author):
                    return await ctx.send("\U000026a0 **An error has occurred!**\nSince you are a developer this error has not been logged.", view=view, reply=False)
                
                embed = discord.Embed(color=discord.Colour.red(), title='Command Error')
                embed.description = "Oops! This command seems to have errored. The error has been fowarded to the owner and will be fixed soon. Please refrain from repeatedly invoking this command in the meanwhile."\
                                    f"\n\nIn the meantime you can join my support server to gain some context on this error and give any extra information by clicking the button below. You can send the error ID below in #support and the command you ran."
                message = await ctx.send(embed=embed, view=view, reply=False)
                embed.description += f'\n```prolog\nError ID: {message.id}\n```'
                await message.edit(embed=embed)

                channel = self.bot.get_channel(self.error_channel)

                embeds = []
                embed = Embed()
                embed.title = 'Command Error'
                embed.set_footer(text=f'ID: {ctx.channel.id}-{message.id}')
                if ctx.guild:
                    embed.description = f'\n```prolog\nAuthor: {ctx.author} ({ctx.author.id})'\
                                        f'\nGuild ID: {ctx.guild.id}'\
                                        f'\nChannel ID: {ctx.channel.id}'\
                                        f'\nCommand: {ctx.message.content[0:1500] if ctx.message else ctx.invoked_with}'\
                                        f'\nAdmin: {await ctx.emojify(ctx.me.guild_permissions.administrator, False)}\n```'
                else:
                    embed.description = f'```prolog\nID: {message.id}'\
                                        f'\nAuthor: {ctx.author} (ID: {ctx.author.id})'\
                                        f"\nCommand: {ctx.message.content[0:1500] if ctx.message else ctx.invoked_with}\n```"

                traceback_embed = Embed(color=discord.Colour.red())
                traceback_embed.title = 'Full Traceback'
                traceback_embed.description = f'```py\n{traceback_string}\n```'  
                
                embeds.append(embed)
                embeds.append(traceback_embed)
                
                try:
                    await self.bot.error_logger.send(f"{channel.guild.get_role(DEVELOPER_ROLE).mention} ID: {message.id}", embeds=embeds)
                except (discord.Forbidden, discord.HTTPException):
                    await self.bot.error_logger.send(content=f'{channel.guild.get_role(DEVELOPER_ROLE).mention} ID: {message.id} | Traceback string was too long to output.', embed=embed, file=discord.File(io.StringIO(traceback_string), filename='traceback.py'))
                return 

        elif isinstance(error, commands.errors.BotMissingPermissions):
            missing_perms = ", ".join(["`%s`" % perm.replace('_', ' ').replace('guild', 'server').title() for perm in error.missing_permissions])
            embed.description = "I am missing the following permissions to run that command: \n%s" % missing_perms
            
            embed.set_author(name='Bot Missing Permissions', icon_url=self.error_emoji)

            try:
                return await ctx.reply(embed=embed)
            except:
                return await ctx.author.send(embed=embed)

        elif isinstance(error, commands.errors.MissingPermissions):
            if check_dev(ctx.bot, ctx.author):
                await ctx.reinvoke()
                return

            embed.set_author(name='Missing Permissions', icon_url=self.error_emoji)

            missing_perms = ", ".join(["`%s`" % perm.replace('_', ' ').replace('guild', 'server').title() for perm in error.missing_permissions])
            embed.description = "You are missing the following permissions to run that command: \n%s" % missing_perms
            
            return await ctx.reply(embed=embed)

        elif isinstance(error, commands.CommandNotFound):
            return # Might change this later and only handle this if the prefix is decently long.

        elif isinstance(error, commands.NotOwner):
            if check_dev(self.bot, ctx.author):
                return

            embed.set_author(name='Owner only command', icon_url=self.error_emoji)
            embed.description = "This command is reserved for developers/owners of %s" % self.bot.user.mention
            return await ctx.send(embed=embed)

        elif isinstance(error, commands.MessageNotFound):
            embed.description = f'Message "{error.argument}" was not found.\n'\
                "\n__**Acceptable arguments:**__"\
                "\n - Message URL"\
                "\n - Message ID (must be in the same channel as message)"\
                "\n - <Channel ID>-<Message ID> (press shift with [developer mode](https://dartmern.github.io/metro/faq/#how-do-i-get-the-id-of-something))"
                
            embed.set_author(name='Message Not Found', icon_url=self.error_emoji)
            return await ctx.send(embed=embed)

        elif isinstance(error, commands.EmojiNotFound):
            embed.description = f"Emoji \"{error.argument}\" was not found.\n"\
                "\nAcceptable arguments are as follows:"\
                f"\nID, emoji itself, name"
            embed.set_author(name='Emoji Not Found', icon_url=self.error_emoji)
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
                #await ctx.reinvoke() # bypass cooldowns for now
                #return 
                pass

            command = ctx.command
    

            cooldowns = ""
            if error.cooldown is not None:
                cooldowns += (
                    f"\n\n**Cooldowns:**\nDefault: `3` time(s) every `8` seconds\nPremium: `3` time(s) every `6` seconds"
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
                await ctx.send("You have been blacklisted for spamming commands. (auto-ban)")
            else:
                await ctx.send(embed=em)

        elif isinstance(error, commands.MissingRequiredArgument):

            missing = f"{error.param.name}"
            command = f"{ctx.clean_prefix}{ctx.command} {ctx.command.signature}"
            separator = (' ' * (len([item[::-1] for item in command[::-1].split(missing[::-1], 1)][::-1][0]) - 1)) + (8*' ')
            indicator = ('^' * (len(missing) + 2))
            message = (f"\n```yaml\nSyntax: {command}\n{separator}{indicator}\n{missing} is a required argument that is missing.\n```")
            
            if isinstance(ctx.command, commands.Group):
                await ctx.get_help(ctx.command, content=message)
            else:
                await ctx.send(embed=await ctx.get_help(ctx.command, content=message))  

        elif isinstance(error, NotVoted):
            return await ctx.send(
                'This command requires you to vote for the bot to use.\n'\
                'You can support the bot and unlock great features.\n'\
                '> <https://top.gg/bot/788543184082698252/vote>'
            )

        elif isinstance(error, commands.TooManyArguments):
            return await ctx.send("Too many arguments were passed to this command!")

        elif isinstance(error, commands.NSFWChannelRequired):
            return await ctx.send("A NSFW marked channel is required to run this command.", hide=True)

        elif isinstance(error, commands.RangeError):
            return await ctx.send(f"Value of {error.value} must be between {error.minimum} and {error.maximum}.")

        elif isinstance(error, commands.NoPrivateMessage):
            embed.description = "This command isn't available in my messages."
            return await ctx.send(embed=embed)

        elif isinstance(error, commands.CheckFailure):
            return

        elif isinstance(error, commands.errors.DisabledCommand):
            return await ctx.send(f"The command `{ctx.command}` is currently globally disabled.")

        elif isinstance(error, errors.ConverterError):
            return await ctx.send(str(error), embed=error.embed)

        elif isinstance(error, commands.BadArgument):
            return await ctx.send(str(error), hide=True)

        elif isinstance(error, commands.CommandError):
            return await ctx.send(str(error))

        else:
                traceback_string = "".join(traceback.format_exception(
                    error, value=error, tb=error.__traceback__))

                view = ErrorView(ctx, traceback_string)

                if check_dev(self.bot, ctx.author):
                    return await ctx.send("\U000026a0 **An error has occurred!**\nSince you are a developer this error has not been logged.", view=view, reply=False)
                
                embed = discord.Embed(color=discord.Colour.red(), title='Command Error')
                embed.description = "Oops! This command seems to have errored. The error has been fowarded to the owner and will be fixed soon. Please refrain from repeatedly invoking this command in the meanwhile."\
                                    f"\n\nIn the meantime you can join my support server to gain some context on this error and give any extra information by clicking the button below. You can send the error ID below in #support and the command you ran."
                message = await ctx.send(embed=embed, view=view, reply=False)
                embed.description += f'\n```prolog\nError ID: {message.id}\n```'
                await message.edit(embed=embed)

                channel = self.bot.get_channel(self.error_channel)

                embeds = []
                embed = Embed()
                embed.title = 'Command Error'
                embed.set_footer(text=f'ID: {ctx.channel.id}-{message.id}')
                if ctx.guild:
                    embed.description = f'\n```prolog\nAuthor: {ctx.author} ({ctx.author.id})'\
                                        f'\nGuild ID: {ctx.guild.id}'\
                                        f'\nChannel ID: {ctx.channel.id}'\
                                        f'\nCommand: {ctx.message.content[0:1500] if ctx.message else ctx.invoked_with}'\
                                        f'\nAdmin: {await ctx.emojify(ctx.me.guild_permissions.administrator, False)}\n```'
                else:
                    embed.description = f'```prolog\nID: {message.id}'\
                                        f'\nAuthor: {ctx.author} (ID: {ctx.author.id})'\
                                        f"\nCommand: {ctx.message.content[0:1500] if ctx.message else ctx.invoked_with}\n```"

                traceback_embed = Embed(color=discord.Colour.red())
                traceback_embed.title = 'Full Traceback'
                traceback_embed.description = f'```py\n{traceback_string}\n```'  
                
                embeds.append(embed)
                embeds.append(traceback_embed)
                
                try:
                    await self.bot.error_logger.send(f"{channel.guild.get_role(DEVELOPER_ROLE).mention} ID: {message.id}", embeds=embeds)
                except (discord.Forbidden, discord.HTTPException):
                    await self.bot.error_logger.send(content=f'{channel.guild.get_role(DEVELOPER_ROLE).mention} ID: {message.id} | Traceback string was too long to output.', embed=embed, file=discord.File(io.StringIO(traceback_string), filename='traceback.py'))
                return 


async def setup(bot: MetroBot):
    await bot.add_cog(core(bot))

    cog: core = bot.get_cog('core')
    bot.on_command_error = cog.on_command_error
