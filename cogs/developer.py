import asyncio
import discord
from discord.ext import commands

from typing import Optional, Union

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

from utils.decos import is_dev, is_support
from utils.custom_context import MyContext
from utils.useful import Embed, fuzzy, pages, get_bot_uptime
from utils.json_loader import write_json

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

    @commands.group(name='moderator', aliases=['mod'], invoke_without_command=True, case_insensitive=True)
    @is_support()
    async def moderator(self, ctx: MyContext):
        """Base command for bot moderator actions."""
        await ctx.help()

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
                summary = f"__**Guild:**__ {guild.name} [{guild.id}]\n__**Owner:**__ {guild.owner} [{guild.owner_id}]\n__**Members:**__ {len(guild.members)} <:members:908483589157576714> total | {len(guild.humans)} \U0001f465 humans | {len(guild.bots)} <:bot:925107948789837844> bots\n"
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
    async def moderator_guildblacklist_add(self, ctx: MyContext, guild: discord.Guild, *, reason: Optional[str]):
        """Add a guild to the guild blacklist."""
        await self.bot.add_to_guildblacklist(guild, reason=reason, ctx=ctx)

    @moderator_guildblacklist.command(name='remove')
    @is_support()
    async def moderator_guildblacklist_remove(self, ctx: MyContext, *, guild: discord.Guild):
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

    @commands.group(name='premium', aliases=['pm'], invoke_without_command=True, case_insensitive=True)
    @is_support()
    async def premium(self, ctx: MyContext):
        """Manage bot premium."""
        
        embed = discord.Embed(title='Metro Premium', color=ctx.color)
        embed.description = f"This bot is fully free and little to none of my features are locked behind a paywall. We want to keep it this way for as long as we can. You can get \"Metro Premium\" by supporting my patreon, that way you can support the bot and get great perks.\n\n{self.bot.donate}"
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



    @commands.command(slash_command=False)
    @is_dev()
    async def eval(self, ctx, *, body : str):
        """Evaluate python code."""

        env = {
            'bot': self.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'guild': ctx.guild,
            'message': ctx.message,
            '_': self._last_result
        }

        env.update(globals())

        body = self.cleanup_code(body)
        stdout = io.StringIO()

        to_compile = f'async def func():\n{textwrap.indent(body, "  ")}'

        try:
            exec(to_compile, env)
        except Exception as e:
            return await ctx.send(f'```py\n{e.__class__.__name__}: {e}\n```')

        func = env['func']
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception as e:
            value = stdout.getvalue()
            await ctx.send(f'```py\n{value}{traceback.format_exc()}\n```')
        else:
            value = stdout.getvalue()
            try:
                await ctx.message.add_reaction('\u2705')
            except:
                pass

            if ret is None:
                if value:
                    await ctx.send(f'```py\n{value}\n```')
            else:
                self._last_result = ret
                await ctx.send(f'```py\n{value}{ret}\n```')

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

    @commands.command()
    @is_dev()
    async def sudo(self, ctx, channel : Union[discord.TextChannel, None], who : Union[discord.Member, discord.User], *, command : str):
        """Run a command as another user optionally in another channel."""

        msg = copy.copy(ctx.message)
        channel = channel or ctx.channel
        msg.channel = channel
        msg.author = who
        msg.content = ctx.prefix + command
        new_ctx = await self.bot.get_context(msg, cls=type(ctx))
        
        await self.bot.invoke(new_ctx)


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
                method(extension)
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
                method(extension)
                pages.add_line(f"{icon} `{extension}`")

            except tuple(error_keys.keys()) as exc:
                pages.add_line(f"{icon}❌ `{extension}` - {error_keys[type(exc)]}")

            except discord.ext.commands.ExtensionFailed as e:
                traceback_string = f"```py" \
                                   f"\n{''.join(traceback.format_exception(etype=None, value=e, tb=e.__traceback__))}" \
                                   f"\n```"
                pages.add_line(f"{icon}❌ `{extension}` - Execution error")
                to_dm = f"❌ {extension} - Execution error - Traceback:"

                if (len(to_dm) + len(traceback_string) + 5) > 2000:
                    await ctx.author.send(file=io.StringIO(traceback_string))
                else:
                    await ctx.author.send(f"{to_dm}\n{traceback_string}")

        for page in pages.pages:
            await ctx.send(page)


    @commands.command()
    @is_dev()
    async def sql(self, ctx, *, query: str):
        """Run some SQL."""

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
            return await ctx.send(f'```py\n{traceback.format_exc()}\n```')

        rows = len(results)
        if is_multistatement or rows == 0:
            return await ctx.send(f'`{dt:.2f}ms: {results}`')

        headers = list(results[0].keys())
        table = TabularData()
        table.set_columns(headers)
        table.add_rows(list(r.values()) for r in results)
        render = table.render()

        fmt = f'```\n{render}\n```\n*Returned {plural(rows):row} in {dt:.2f}ms*'
        if len(fmt) > 2000:
            fp = io.BytesIO(fmt.encode('utf-8'))
            await ctx.send('Too many results...', file=discord.File(fp, 'results.txt'))
        else:
            await ctx.send(fmt)

    @commands.command()
    @is_dev()
    async def inspect(self, ctx : MyContext, *, object : str):
        """
        Get source code of an object.
        """
        command = self.bot.get_command('eval')
        await command(ctx, body=f'import inspect\nreturn inspect.getsource({object})')

    def do_restart(self, message: discord.Message):
        write_json({"id": message.id, "channel": message.channel.id, "now": ((discord.utils.utcnow()).replace(tzinfo=None)).timestamp()}, 'restart')
        restart_program()

    @commands.command(name='restart', aliases=['reboot'])
    @is_support()
    async def restart(self, ctx: MyContext):
        """Restart the bot."""
        message = await ctx.send(f"Restarting...", reply=False)
        self.do_restart(message)

    @commands.command()
    @commands.is_owner()
    async def update(self, ctx: MyContext, *, restart: bool = False):
        """Update the bot."""

        message = await ctx.send("Restarting...")

        command = self.bot.get_command("jsk shell")
        await ctx.invoke(command, argument=codeblock_converter('git pull https://github.com/dartmern/metro master --allow-unrelated-histories'))
        await asyncio.sleep(8)
        if restart is False:
            rall = self.bot.get_command("rall")
            await rall(ctx)
            return await ctx.send("Updated!")
             
        self.do_restart(message)

def setup(bot):
    bot.add_cog(developer(bot))


