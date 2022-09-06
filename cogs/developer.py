import asyncio
import discord
from discord.ext import commands
from discord import app_commands

from typing import Literal, Optional, Union

import traceback
import time
import os
import pytz
import asyncpg
import io
import datetime
import sys
import itertools
import copy
import os
import textwrap
from contextlib import redirect_stdout

import jishaku 
from jishaku.paginators import WrappedPaginator
from jishaku.codeblocks import codeblock_converter
from bot import MetroBot
from cogs.serverutils import serverutils
from utils.constants import TESTING_GUILD, TESTING_GUILD_ID

from utils.decos import in_support, is_dev, is_support
from utils.custom_context import MyContext
from utils.pages import StopView
from utils.useful import Embed, fuzzy, pages, get_bot_uptime
from utils.json_loader import write_json

class Input(discord.ui.Modal):
    def __init__(self, bot: MetroBot, *, title: str) -> None:
        super().__init__(title=title)
        self.bot = bot

    string = discord.ui.TextInput(label='Code', style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction):
        
        await interaction.response.defer(ephemeral=True)
        # most likely gonna take longer than 3 seconds

        query = self.string.value

        is_multistatement = query.count(';') > 1
        if is_multistatement:
            # fetch does not support multiple statements
            strategy = self.bot.db.execute
        else:
            strategy = self.bot.db.fetch

        try:
            start = time.perf_counter()
            results = await strategy(query)
            dt = (time.perf_counter() - start) * 1000.0
        except Exception:
            return await interaction.followup.send(f'```py\n{traceback.format_exc()}\n```', view=StopView(interaction))

        rows = len(results)
        if is_multistatement or rows == 0:
            return await interaction.followup.send(f'`{dt:.2f}ms: {results}`', view=StopView(interaction))

        headers = list(results[0].keys())
        table = TabularData()
        table.set_columns(headers)
        table.add_rows(list(r.values()) for r in results)
        render = table.render()

        fmt = f'```\n{render}\n```\n*Returned {plural(rows):row} in {dt:.2f}ms*'
        if len(fmt) > 2000:
            fp = io.BytesIO(fmt.encode('utf-8'))
            await interaction.followup.send('Too many results...', file=discord.File(fp, 'results.txt'), view=StopView(interaction))
        else:
            await interaction.followup.send(fmt, view=StopView(interaction))


def restart_program():
    python = sys.executable
    os.execl(python, python, * sys.argv)

class TabularData:
    def __init__(self):
        self._widths = []
        self._columns = []
        self._rows = []

    def set_columns(self, columns):
        self._columns = columns
        self._widths = [len(c) + 2 for c in columns]

    def add_row(self, row):
        rows = [str(r) for r in row]
        self._rows.append(rows)
        for index, element in enumerate(rows):
            width = len(element) + 2
            if width > self._widths[index]:
                self._widths[index] = width

    def add_rows(self, rows):
        for row in rows:
            self.add_row(row)

    def render(self):
        """Renders a table in rST format.
        Example:
        +-------+-----+
        | Name  | Age |
        +-------+-----+
        | Alice | 24  |
        |  Bob  | 19  |
        +-------+-----+
        """

        sep = '+'.join('-' * w for w in self._widths)
        sep = f'+{sep}+'

        to_draw = [sep]

        def get_entry(d):
            elem = '|'.join(f'{e:^{self._widths[i]}}' for i, e in enumerate(d))
            return f'|{elem}|'

        to_draw.append(get_entry(self._columns))
        to_draw.append(sep)

        for row in self._rows:
            to_draw.append(get_entry(row))

        to_draw.append(sep)
        return '\n'.join(to_draw)


# Moved this up because of some testing
async def setup(bot: MetroBot):
    await bot.add_cog(developer(bot))

class plural:
    def __init__(self, value):
        self.value = value
    def __format__(self, format_spec):
        v = self.value
        singular, sep, plural = format_spec.partition('|')
        plural = plural or f'{singular}s'
        if abs(v) != 1:
            return f'{v} {plural}'
        return f'{v} {singular}'


class developer(commands.Cog, description="Developer commands."):
    def __init__(self, bot: MetroBot):
        self.bot = bot
        self._last_result = None

    @property
    def emoji(self) -> str:
        return ''

    def cleanup_code(self, content):
        """Automatically removes code blocks from the code."""
        # remove ```py\n```
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])

        # remove `foo`
        return content.strip('` \n')

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.id != 525843819850104842:
            return
        await self.bot.process_commands(after)

    @commands.hybrid_command(name='fix')
    @app_commands.guilds(TESTING_GUILD)
    @is_support()
    async def fix_command(
        self, 
        ctx: MyContext, 
        error_id: str, 
        *, 
        comment: Optional[str] #= commands.Parameter(default=None, displayed_default='L', name='Comment to leave.')
    ):
        """Fix an error by sending the channel an "error fixed" message."""
        try:
            message = await commands.MessageConverter().convert(ctx, error_id)
        except Exception:
            return await ctx.send(f"Could not find a message with that error id.")

        if comment:
            if_comment = f'\n__Additional comments:__ {comment}'
        else:
            if_comment = ''

        try:
            await message.reply(f'This error has been fixed by my developers. \U0001f44d {if_comment}')
        except Exception as e:
            return await ctx.send(f"Had an issue replying to the message: {e}", ephemeral=True)

        await ctx.send('\U0001f44d', ephemeral=True)

    @commands.command(name='issue')
    @in_support()
    async def issue(self, ctx: MyContext, issue: int):
        """Sends the github issue link."""

        await ctx.send(f'https://github.com/dartmern/metro/issues/{issue}')

    @commands.group(name='moderator', aliases=['mod'], invoke_without_command=True, case_insensitive=True)
    @is_support()
    async def moderator(self, ctx: MyContext):
        """Base command for bot moderator actions."""
        await ctx.help()

    @moderator.command(name='sync')
    @is_support()
    async def moderator_sync(
        self, ctx: MyContext,
        guilds: commands.Greedy[discord.Object],
        option: Optional[Literal["~", "*", "^"]] = None):
        """
        Syncs application commands within the bot.
        
        Valid Options:
        `~`: syncs the current guild
        `*`: copies all global app commands to current guild and syncs
        `^`: clears all commands from the current guild target and syncs

        You can sync multiple guilds like: [p]mod sync guild1 guild2
        """
        if not guilds:
            if option == "~":
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif option == "*":
                ctx.bot.tree.copy_global_to(guild=ctx.guild)
                synced = await ctx.bot.tree.sync(guild=ctx.guild)
            elif option == "^":
                ctx.bot.tree.clear_commands(guild=ctx.guild)
                await ctx.bot.tree.sync(guild=ctx.guild)
                synced = []
            else:
                synced = await ctx.bot.tree.sync()

            await ctx.send(
                f"Synced {len(synced)} commands {'globally' if option is None else 'to the current guild.'}"
            )
            return

        ret = 0
        for guild in guilds:
            try:
                await ctx.bot.tree.sync(guild=guild)
            except discord.HTTPException:
                pass
            else:
                ret += 1

        await ctx.send(f"Synced the tree to {ret}/{len(guilds)}.")


    @moderator.command(name='whatown')
    @is_support()
    async def moderator_whatown(self, ctx: MyContext, *, member: discord.Member):
        """See what server a user owns that has Metro it in."""

        owns = []

        for guild in self.bot.guilds:
            if guild.owner_id == member.id:
                owns.append(guild.id)

        await ctx.send(f"{member} owns: {', '.join(map(str, owns))}")

    @moderator.command(name='guilds', aliases=['servers'])
    @is_support()
    async def moderator_guilds(self, ctx, search=None):
        """
        Get all the guilds the bot is in.

        You can search a server name or get all the guild's name and guild's id.
        """

        if not search:
            to_paginate = []
            for guild in sorted(self.bot.guilds, key=lambda guild: len(guild.members), reverse=True):
                humans = [hum for hum in guild.members if not hum.bot]
                bots = [bot for bot in guild.members if bot.bot]
                summary = f"__**Guild:**__ {guild.name} [{guild.id}]\n__**Owner:**__ {guild.owner} [{guild.owner_id}]\n__**Members:**__ {len(guild.members)} <:members:908483589157576714> total | {len(humans)} \U0001f465 humans | {len(bots)} <:bot:925107948789837844> bots\n"
                to_paginate.append(summary)

            await ctx.paginate(to_paginate, per_page=4, compact=True)
        else:
            collection = {guild.name: guild.id for guild in self.bot.guilds}
            found = fuzzy.finder(search, collection, lazy=False)[:5]

            if len(found) == 1:
                guild = self.bot.get_guild(collection[found[0]])
                em = Embed(
                    description=f"ID: {guild.id}\nTotal members: {len(guild.members)}"
                )
                em.set_author(name=found[0])
                await ctx.send(embed=em)
            elif len(found) > 1:
                newline = "\n"
                await ctx.send(f"**__{len(found)} guilds found:__**\n{newline.join(found)}")
            else:
                await ctx.send(f"No guild was found named **{search}**")

    @moderator.command(name='serverinfo', aliases=['si'])
    @is_support()
    async def moderator_serverinfo(self, ctx: MyContext, *, guild: discord.Guild):
        """Get information about a guild that I'm in."""
        serverutils_cog: serverutils = self.bot.get_cog("serverutils")
        if not serverutils_cog:
            raise commands.BadArgument("This command is not available at this time.")
        await ctx.send(embed=await serverutils_cog.serverinfo_embed(ctx, guild))

    @moderator.group(name='guildblacklist', invoke_without_command=True, case_insensitive=True, aliases=['gb'])
    @is_support()
    async def moderator_guildblacklist(self, ctx: MyContext):
        """Manage the guild blacklist."""
        await ctx.help()

    @moderator_guildblacklist.command(name='add')
    @is_support()
    async def moderator_guildblacklist_add(self, ctx: MyContext, guild: int, *, reason: Optional[str]):
        """Add a guild to the guild blacklist."""
        await self.bot.add_to_guildblacklist(guild, reason=reason, ctx=ctx)

    @moderator_guildblacklist.command(name='remove')
    @is_support()
    async def moderator_guildblacklist_remove(self, ctx: MyContext, *, guild: int):
        """Remove a guild from the guild blacklist."""
        await self.bot.remove_from_guildblacklist(guild, ctx=ctx)

    @moderator_guildblacklist.command(name='list')
    @is_support()
    async def moderator_guildblacklist_list(self, ctx: MyContext):
        """List all of the blacklisted guilds."""
        records = await self.bot.db.fetch("SELECT (guild, moderator, added_time, reason) FROM guild_blacklist WHERE verify = True")
        if records:
            blacklisted = []

            for record in records:
                blacklisted.append(f'{record["row"][0]} {record["row"][3] if record["row"][3] else ""}\nVia: <@{record["row"][1]}> {discord.utils.format_dt(pytz.utc.localize(record["row"][2]), "R")}')

            await ctx.paginate(blacklisted, per_page=10, compact=True)
        else:
            await ctx.send("No guilds are currently blacklisted.")
    

    @moderator.group(name='blacklist', invoke_without_command=True,case_insensitive=True)
    @is_support()
    async def moderator_blacklist(self, ctx : MyContext) -> discord.Message:
        """Manage the bot's blacklist."""
        await ctx.help()
    
    @moderator_blacklist.command(name='add')
    @is_support()
    async def moderator_blacklist_add(
        self, ctx : MyContext, user : Union[discord.Member, discord.User], *, reason : str = None):
        """Add a user to the bot blacklist."""
        await self.bot.add_to_blacklist(ctx, user, reason)
        
    @moderator_blacklist.command(name='remove')
    @is_support()
    async def moderator_blacklist_remove(self, ctx : MyContext, user : Union[discord.Member, discord.User]):
        """Remove a user from the bot blacklist."""
        await self.bot.remove_from_blacklist(ctx, user)

    @moderator_blacklist.command(name='info')
    @is_support()
    async def moderator_blacklist_info(self, ctx : MyContext, user : Union[discord.Member, discord.User]):
        """Check information on a user's blacklist."""

        data = await self.bot.db.fetchrow("SELECT reason FROM blacklist WHERE member_id = $1", user.id)
        if not data:
            return await ctx.send("This user is not blacklisted.")

        await ctx.send(
            f"\nUser: {user} (ID: {user.id})"
            f"\nReason: {data['reason']}"
        )

    @moderator_blacklist.command(name='list', usage='[--cache]')
    @is_support()
    async def moderator_blacklist_list(self, ctx : MyContext, *, args : str = None):
        """List all the users blacklisted from bot."""
        
        records = await self.bot.db.fetch("SELECT (member_id, reason, added_time, moderator) FROM blacklist WHERE is_blacklisted = True")
        if records:
            blacklisted = []

            for record in records:
                blacklisted.append(f'{record["row"][0]} (<@{record["row"][0]}>) {record["row"][1] if record["row"][1] else ""}\nVia: <@{record["row"][3]}> {discord.utils.format_dt(pytz.utc.localize(record["row"][2]), "R")}\n')

            await ctx.paginate(blacklisted, per_page=10, compact=True)
        else:
            await ctx.send("No users are currently blacklisted.")

    @moderator.command(name='leave')
    @is_support()
    async def moderator_leave(self, ctx: MyContext, guild_id: int):
        """Leave a guild."""

        guilds = map(lambda x: x.id, self.bot.guilds)
        if guild_id in guilds:
            guild = self.bot.get_guild(guild_id)
            try:
                await guild.leave()
            except discord.HTTPException:
                return await ctx.send('Leaving this guild somehow failed...')
            await ctx.send(f'Left the guild **{guild.name}**')
        else:
            await ctx.send("I am not apart of that guild or it does not exist.")


    @commands.group(name='premium', aliases=['pm'], invoke_without_command=True, case_insensitive=True)
    #@is_support()
    async def premium(self, ctx: MyContext):
        """Manage bot premium."""
        
        embed = discord.Embed(title='Metro Premium', color=ctx.color)
        embed.description = f"This bot is fully free and little to none of my features are locked behind a paywall. We want to keep it this way for as long as we can. You can get \"Metro Premium\" by supporting my patreon, that way you can support the bot and get great perks.\n\n{self.bot.donate}"

        embed.set_footer(text='As of now Metro Premium has very unnoticeable features. Buying pateron can fund things like hosting and development.')
        await ctx.send(embed=embed)

    @premium.command(name='add', aliases=['+'])
    @is_support()
    async def premium_add(self, ctx: MyContext, *, object: Union[discord.Guild, discord.User]):
        """Add premium to a guild or a user."""
        
        if isinstance(object, discord.Guild):
            query = """
                    INSERT INTO premium_guilds (server, is_premium, added_time) VALUES ($1, $2, $3)
                    """
            try:
                await self.bot.db.execute(query, object.id, True, (discord.utils.utcnow()).replace(tzinfo=None))
                self.bot.premium_guilds[object.id] = True
            except asyncpg.exceptions.UniqueViolationError:
                raise commands.BadArgument(f"{self.bot.emotes['cross']} This guild already has premium perks!")

            await ctx.send(f"{self.bot.emotes['check']} Added premium perks to **{object.name}**")
        else:
            await ctx.send("Only premium **guilds** are available.")

    @premium.command(name='remove', aliases=['-'])
    @is_support()
    async def premium_remove(self, ctx: MyContext, *, object: Union[discord.Guild, discord.User]):
        """Remove premium from a guild or user."""

        if isinstance(object, discord.Guild):
            query = """
                    DELETE FROM premium_guilds WHERE server = $1
                    """
            status = await self.bot.db.execute(query, object.id)
            self.bot.premium_guilds[object.id] = False
            if status == "DELETE 0":
                raise commands.BadArgument(f"{self.bot.emotes['cross']} This guild doesn't even have premium perks.")

            await ctx.send(f"{self.bot.emotes['check']} Removed premium perks from **{object.name}**")
            
        else:
            await ctx.send("Only premium **guilds** are available.")

    @commands.command(aliases=['cls'])
    @is_dev()
    async def clearconsole(self, ctx):
        try:
            command = 'clear'
            if os.name in ('nt', 'dos'):  # If Machine is running on Windows, use cls
                command = 'cls'
            os.system(command)
        except Exception as e:
            return await ctx.send(str(e))
        await ctx.check()

    @commands.hybrid_command()
    @app_commands.describe(channel='The channel you want this command executed in.')
    @app_commands.describe(who='The user you want to run this command.')
    @app_commands.describe(command='The command string you want to execute.')
    @app_commands.guilds(TESTING_GUILD)
    @is_dev()
    async def sudo(self, ctx: MyContext, channel : Union[discord.TextChannel, None], who : Union[discord.Member, discord.User], *, command : str):
        """Run a command as another user optionally in another channel."""

        prefix = self.bot.user.mention + " " if ctx.interaction else ctx.prefix

        msg = copy.copy(ctx.message)
        channel = channel or ctx.channel
        msg.channel = channel
        msg.author = who
        msg.content = prefix + command

        new_ctx = await self.bot.get_context(msg, cls=type(ctx))
        
        await self.bot.invoke(new_ctx)

        if ctx.interaction:
            await ctx.interaction.response.send_message(f"Forced {who} to run {'/' if ctx.interaction else ctx.prefix}{command} in {channel.mention}", ephemeral=True)

    @commands.command(help="Reloads all extensions", aliases=['rall'])
    @is_dev()
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def reloadall(self, ctx, *extensions: jishaku.modules.ExtensionConverter):
        self.bot.last_rall = datetime.datetime.utcnow()
        pages = WrappedPaginator(prefix='', suffix='')
        first_reload_failed_extensions = []

        extensions = extensions or [await jishaku.modules.ExtensionConverter.convert(self, ctx, '~')]

        for extension in itertools.chain(*extensions):
            method, icon = (
                (self.bot.reload_extension, "\N{CLOCKWISE RIGHTWARDS AND LEFTWARDS OPEN CIRCLE ARROWS}")
                if extension in self.bot.extensions else
                (self.bot.load_extension, "\N{INBOX TRAY}")
            )
            # noinspection PyBroadException
            try:
                await method(extension)
                pages.add_line(f"{icon} `{extension}`")
            except Exception:
                first_reload_failed_extensions.append(extension)

        error_keys = {
            discord.ext.commands.ExtensionNotFound: 'Not found',
            discord.ext.commands.NoEntryPointError: 'No setup function',
            discord.ext.commands.ExtensionNotLoaded: 'Not loaded',
            discord.ext.commands.ExtensionAlreadyLoaded: 'Already loaded'
        }

        for extension in first_reload_failed_extensions:
            method, icon = (
                (self.bot.reload_extension, "\N{CLOCKWISE RIGHTWARDS AND LEFTWARDS OPEN CIRCLE ARROWS}")
                if extension in self.bot.extensions else
                (self.bot.load_extension, "\N{INBOX TRAY}")
            )
            try:
                await method(extension)
                pages.add_line(f"{icon} `{extension}`")

            except tuple(error_keys.keys()) as exc:
                pages.add_line(f"{icon}❌ `{extension}` - {error_keys[type(exc)]}")

            except discord.ext.commands.ExtensionFailed as e:
                traceback_string = f"```py" \
                                   f"\n{''.join(traceback.format_exception(e, value=e, tb=e.__traceback__))}" \
                                   f"\n```"
                pages.add_line(f"{icon}❌ `{extension}` - Execution error")
                to_dm = f"❌ {extension} - Execution error - Traceback:"

                if (len(to_dm) + len(traceback_string) + 5) > 2000:
                    await ctx.author.send(file=io.StringIO(traceback_string))
                else:
                    await ctx.author.send(f"{to_dm}\n{traceback_string}")

        for page in pages.pages:
            await ctx.send(page)


    @commands.hybrid_command()
    @is_dev()
    @app_commands.guilds(TESTING_GUILD)
    @app_commands.describe(query='The sql query you want to run. Leave blank for a modal.')
    async def sql(self, ctx: MyContext, *, query: Optional[str]):
        """Run some SQL."""

        if ctx.interaction and not query:
            return await ctx.interaction.response.send_modal(Input(self.bot, title='SQL'))

        if not ctx.interaction and not query:
            return await ctx.help()

        query = self.cleanup_code(query)

        is_multistatement = query.count(';') > 1
        if is_multistatement:
            # fetch does not support multiple statements
            strategy = ctx.bot.db.execute
        else:
            strategy = ctx.bot.db.fetch

        try:
            start = time.perf_counter()
            results = await strategy(query)
            dt = (time.perf_counter() - start) * 1000.0
        except Exception:
            return await ctx.send(f'```py\n{traceback.format_exc()}\n```', view=StopView(ctx))

        rows = len(results)
        if is_multistatement or rows == 0:
            return await ctx.send(f'`{dt:.2f}ms: {results}`', view=StopView(ctx))

        headers = list(results[0].keys())
        table = TabularData()
        table.set_columns(headers)
        table.add_rows(list(r.values()) for r in results)
        render = table.render()

        fmt = f'```\n{render}\n```\n*Returned {plural(rows):row} in {dt:.2f}ms*'
        if len(fmt) > 2000:
            fp = io.BytesIO(fmt.encode('utf-8'))
            await ctx.send('Too many results...', file=discord.File(fp, 'results.txt'), view=StopView(ctx))
        else:
            await ctx.send(fmt, view=StopView(ctx))

    def do_restart(self, message: discord.Message):
        write_json(
            {
                "id": message.id, 
                "channel": message.channel.id, 
                "now": ((discord.utils.utcnow()).replace(tzinfo=None)).timestamp()
            }, 
            'restart')
        restart_program()

    @commands.hybrid_command(name='restart', aliases=['reboot'])
    @app_commands.guilds(TESTING_GUILD)
    @is_support()
    async def restart(self, ctx: MyContext):
        """Restart the bot."""
        message = await ctx.send(f"Restarting...", reply=False)
        self.do_restart(message)

    @commands.hybrid_command(name='push')
    @app_commands.guilds(TESTING_GUILD)
    @commands.is_owner()
    async def push_update(self, ctx: MyContext):
        """Invokes git push"""

        command = self.bot.get_command("jsk shell")
        await ctx.invoke(command, argument=codeblock_converter('git push metro head'))

    @commands.hybrid_command()
    @app_commands.guilds(TESTING_GUILD)
    @app_commands.describe(restart='Whether or not to restart the bot.')
    @commands.is_owner()
    async def update(self, ctx: MyContext, *, restart: bool = False):
        """Update the bot."""

        message = await ctx.send("Restarting...")

        command = self.bot.get_command("jsk shell")
        await ctx.invoke(command, argument=codeblock_converter('git --git-dir=/home/pi/Documents/metro/.git pull https://github.com/dartmern/metro master --allow-unrelated-histories'))
        await asyncio.sleep(8)
        if restart is False:
            rall = self.bot.get_command("rall")
            await rall(ctx)
            return await ctx.send("Updated!")
             
        self.do_restart(message)

