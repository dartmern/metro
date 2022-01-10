from collections import defaultdict
import re
import discord
from discord.ext import commands, menus

from typing import Dict, Optional

from bot import MetroBot

from utils.json_loader import read_json
from utils.custom_context import MyContext
from utils.remind_utils import FutureTime, human_timedelta
from utils.useful import Cooldown, Embed
from utils.useful import Embed
from utils.new_pages import SimplePages
from utils.remind_utils import UserFriendlyTime
from utils.pages import ExtraPages
from utils.converters import RoleConverter

from datetime import timedelta
import json
import random
import io
import pytz
import traceback
import asyncio
import datetime
import time
import os
import asyncpg
import yarl
import inspect
import unicodedata

class Flags(commands.FlagConverter, delimiter=' ', prefix='--'):
    ping: Optional[RoleConverter]
    message: Optional[str] = commands.Flag(aliases=['msg'], name='message')

class StopView(discord.ui.View):
    def __init__(self, ctx : MyContext):
        super().__init__(timeout=120)
        self.ctx = ctx

    async def interaction_check(self, interaction):
        if self.ctx.author.id == interaction.user.id:
            return True
        else:
            await interaction.response.send_message(
                "Only the command invoker can use this button.", ephemeral=True
            )

    @discord.ui.button(emoji='\U0001f5d1', style=discord.ButtonStyle.red)
    async def stop_view(self, button : discord.ui.Button, interaction : discord.Interaction):
        """
        Stop the pagination session. 
        Unless this pagination menu was invoked with a slash command
        """

        await interaction.response.defer()
        await interaction.delete_original_message()
        self.stop()


class SourceView(discord.ui.View):
    def __init__(self, ctx : MyContext, code : str):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.code = code

    async def interaction_check(self, interaction):
        if self.ctx.author.id == interaction.user.id:
            return True
        else:
            await interaction.response.send_message(
                "Only the command invoker can use this button.", ephemeral=True
            )

    @discord.ui.button(label='Source File', emoji='\U0001f4c1', style=discord.ButtonStyle.blurple)
    async def foo(self, button : discord.ui.Button, interaction : discord.Interaction):
        
        if len(self.code) >= 1500:
            file = discord.File(io.StringIO(self.code), filename='code.py')
            await interaction.response.defer()
            await self.ctx.message.reply(file=file, view=StopView(self.ctx))
        else:
            await interaction.response.send_message(f"```py\n{self.code}\n```", view=StopView(self.ctx))

        button.style = discord.ButtonStyle.gray
        button.disabled = True
        await interaction.message.edit(view=self)

    @discord.ui.button(label='Post Source', emoji='\U0001f587', style=discord.ButtonStyle.blurple)
    async def bar(self, button : discord.ui.Button, interaction : discord.Interaction):

        async with self.ctx.bot.session.post(f"https://mystb.in/documents", data=self.code) as s:
            res = await s.json()
            url_key = res['key']
        
        await interaction.response.send_message(f"Output: https://mystb.in/{url_key}.python", view=StopView(self.ctx))

        button.style = discord.ButtonStyle.gray
        button.disabled = True
        await interaction.message.edit(view=self)

    @discord.ui.button(emoji='\U0001f5d1', style=discord.ButtonStyle.red)
    async def stop_view(self, button : discord.ui.Button, interaction : discord.Interaction):
        """
        Stop the pagination session. 
        Unless this pagination menu was invoked with a slash command
        """

        await interaction.response.defer()
        await interaction.delete_original_message()
        self.stop()


class MySource(menus.ListPageSource):
    def __init__(self, data):
        super().__init__(data, per_page=5)

    async def format_page(self, menu, entries):

        embed= Embed()

        for i in entries:
            embed.add_field(name=f'ID: {i.get("id")}: {discord.utils.format_dt((i.get("expires")).replace(tzinfo=datetime.timezone.utc), "R")}',value=i.get("?column?"),inline=False)

        embed.set_footer(text=f'{len(entries)} reminder{"s" if len(entries) > 1 else ""}')

        return embed

class WinnerConverter(commands.Converter):
    async def convert(self, ctx : MyContext, argument : str):
        try:
            if int(argument) > 30:
                raise commands.BadArgument("You cannot have more than 30 winners.")
            if int(argument) <= 0:
                raise commands.BadArgument("You cannot have less than 0 winners.")
            return int(argument)
        except ValueError:
            argument = argument.replace("w", "")
            try:
                if int(argument) > 30:
                    raise commands.BadArgument("You cannot have more than 30 winners.")
                if int(argument) <= 0:
                    raise commands.BadArgument("You cannot have less than 0 winners.")
                return int(argument)
            except ValueError:
                raise commands.BadArgument("There was an issue converting your winners argument.")
                
    
class Timer:
    __slots__ = ("args", "kwargs", "event", "id", "created_at", "expires")

    def __init__(self, *, record):
        self.id = record["id"]
        extra = record["extra"]
        self.args = extra.get("args", [])
        self.kwargs = extra.get("kwargs", {})
        self.event = record["event"]
        self.created_at = record["created"]
        self.expires = record["expires"]

    @classmethod
    def temporary(cls, *, expires, created, event, args, kwargs):
        pseudo = {
            "id": None,
            "extra": {"args": args, "kwargs": kwargs},
            "event": event,
            "created": created,
            "expires": expires,
        }
        return cls(record=pseudo)

    def __eq__(self, other):
        try:
            return self.id == other.id
        except AttributeError:
            return False

    def __hash__(self):
        return hash(self.id)

    @property
    def human_delta(self):
        return human_timedelta(self.created_at)

    @property
    def author_id(self):
        if self.args:
            return int(self.args[0])
        return None

    def __repr__(self):
        return f"<Timer created={self.created_at} expires={self.expires} event={self.event}>"


class GithubError(commands.CommandError):
    pass

info_file = read_json('info')
github_token = info_file["github_token"]
bitly_token = info_file['bitly_token']


class TodoListSource(menus.ListPageSource):
    def __init__(self, entries, ctx : MyContext):
        super().__init__(entries, per_page=14)
        self.ctx = ctx

    async def format_page(self, menu, entries):
        maximum = self.get_max_pages()

        embed = Embed()
        embed.set_author(name=self.ctx.author, icon_url=self.ctx.author.avatar.url)

        todo_list = []
        
        for index, entry in enumerate(entries, start=menu.current_page * self.per_page):
            todo_list.append(f"**[{index + 1}]({entry['jump_url']} \"Jump to message\").** {entry['text']}")

        embed.description = '\n'.join(todo_list)
        return embed

class Source(menus.ListPageSource):
    def __init__(self, entries):
        super().__init__(entries=entries, per_page=4)

    async def format_page(self, menu, entries):
        
        maximum = self.get_max_pages()
        embed=discord.Embed()
        embed.description='\n'.join(f"{i}\n**ID:** {i.id}\n**GUILD:** {i.guild}" for i in entries)

        embed.set_footer(text=f'[{menu.current_page + 1}/{maximum}]')
        return embed

class CustomPermissions:
    pass

class utility(commands.Cog, description="Get utilities like prefixes, serverinfo, source, etc."):
    def __init__(self, bot : MetroBot):
        self.bot = bot
        self._req_lock = asyncio.Lock(loop=self.bot.loop)
        self._have_data = asyncio.Event(loop=bot.loop)
        self._current_timer = None
        self._task = bot.loop.create_task(self.dispatch_timers())

        self.highlight = {}

        bot.loop.create_task(self.load_highlight())

        self.regex_pattern = re.compile('([^\s\w]|_)+')
        self.website_regex = re.compile("https?:\/\/[^\s]*")

    def cog_unload(self):
        self._task.cancel()

    @property
    def emoji(self) -> str:
        return 'ℹ️'

    async def from_permission(self, permission : int):

        allowed, denied = [], []
        for name, value in discord.Permissions(permission):
            name = name.replace("_", " ").replace('guild', 'server').title()
            if value:
                allowed.append(name)
            else:
                denied.append(name)
        permission = CustomPermissions()
        permission.allowed = allowed
        permission.denied = denied
        return permission
        

    async def say_permissions(self, ctx : MyContext, member : discord.Member, channel : discord.TextChannel):
        permissions = channel.permissions_for(member)
        e = discord.Embed(colour=member.colour)
        avatar = member.display_avatar.url

        if avatar is None:
            e.set_author(name=str(member))
        else:
            e.set_author(name=str(member), url=avatar)
        allowed, denied = [], []
        for name, value in permissions:
            name = name.replace('_', ' ').replace('guild', 'server').title()
            if value:
                allowed.append(name)
            else:
                denied.append(name)

        e.add_field(name='Allowed', value='\n'.join(allowed))
        e.add_field(name='Denied', value='\n'.join(denied))
        await ctx.send(embed=e)

    async def post_mystbin(self, data : str, encoding : str = 'utf-8'):
        to_post = bytes(data, encoding)

        async with self.bot.session.post(f"https://mystb.in/documents", data=data) as s:
            res = await s.json()
            url_key = res['key']
        
        return f"https://mystb.in/{url_key}"

    @commands.command(name='mystbin')
    @commands.check(Cooldown(2, 10, 2, 8, commands.BucketType.user))
    async def mystbin(self, ctx: MyContext, *, content : str):
        """Create and post a mystbin online."""

        start = time.perf_counter()
        link = await self.post_mystbin(content)
        end = time.perf_counter()

        post_time = (end - start) * 1000

        e = Embed()
        e.colour = discord.Colour.yellow()
        e.description = f"Output: {link}"
        e.set_footer(text=f'Post time: {round(post_time, 3)}')
        return await ctx.send(embed=e)

        

    @commands.command(name='permissions',brief="Shows a member's permissions in a specific channel.")
    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    async def member_perms(self, ctx, member : Optional[discord.Member], channel : Optional[discord.TextChannel]):
        """Shows a member's permissions in a specific channel.

        If no channel is given then it uses the current one.

        You cannot use this in private messages. If no member is given then
        the info returned will be yours.
        """

        channel = channel or ctx.channel
        if member is None:
            member = ctx.author

        await self.say_permissions(ctx, member, channel)

    @commands.command()
    @commands.bot_has_permissions(send_messages=True)
    async def charinfo(self, ctx, *, characters: str):
        """Shows you information about a number of characters.
        Only up to 25 characters at a time.
        """

        def to_string(c):
            digit = f'{ord(c):x}'
            name = unicodedata.name(c, 'Name not found.')
            return f'`\\U{digit:>08}`: {name} - {c} \N{EM DASH} <http://www.fileformat.info/info/unicode/char/{digit}>'

        msg = '\n'.join(map(to_string, characters))
        if len(msg) > 2000:
            return await ctx.send('Output too long to display.')
        await ctx.send(msg)

    @commands.group(
        name='prefix',
        case_insensitive=True,
        invoke_without_command=True
    )
    @commands.has_permissions(manage_guild=True)
    @commands.bot_has_permissions(send_messages=True)
    async def prefix(self, ctx : MyContext):
        """
        Manage prefixes for the bot.
        """
        return await ctx.help()


    @prefix.command(
        name='add'
    )
    @commands.has_permissions(manage_guild=True)
    async def prefix_add(self, ctx : MyContext, prefix : str) -> discord.Message:
        """
        Add a prefix to the guild's prefixes.
        Use quotes to add spaces to your prefix.
        """
        query = """
                INSERT INTO prefixes(guild_id, prefix) VALUES ($1, $2)
                """

        try:
            await self.bot.db.execute(query, ctx.guild.id, prefix)
            self.bot.prefixes[ctx.guild.id] = await self.bot.fetch_prefixes(ctx.message)
            
            embed = Embed()
            embed.colour = discord.Colour.green()
            embed.description = f'{self.bot.check} **|** Added `{prefix}` to the guild\'s prefixes.'
            await ctx.send(embed=embed)

        except asyncpg.exceptions.UniqueViolationError:
            embed = Embed()
            embed.colour = discord.Colour.red()
            embed.description = f'{self.bot.cross} **|** That is already a prefix in this guild.'
            await ctx.send(embed=embed)


    @prefix.command(name='list')
    async def prefix_list(self, ctx : MyContext) -> discord.Message:
        """List all the bot's prefixes."""

        prefixes = await self.bot.get_pre(self.bot, ctx.message, raw_prefix=True)

        embed = Embed()
        embed.title = 'My prefixes'
        embed.description = (ctx.me.mention + '\n' + '\n'.join(prefixes)
        )
        embed.set_footer(text=f'{len(prefixes) + 1} prefixes')

        await ctx.send(embed=embed)

    
    @prefix.command(name='remove')
    @commands.has_permissions(manage_guild=True)
    async def prefix_remove(self, ctx : MyContext, prefix : str) -> discord.Message:
        """Remove a prefix from the bot's prefixes."""

        old = list(await self.bot.get_pre(self.bot, ctx.message, raw_prefix=True))
        if prefix in old:
            embed = Embed()
            embed.description = f'{self.bot.check} **|** Removed `{prefix}` from my prefixes.'
            embed.colour = discord.Colour.green()
            await ctx.send(embed=embed)
        else:
            embed = Embed()
            embed.description = f'{self.bot.cross} **|** That is not one of my prefixes.'
            embed.colour = discord.Colour.red()
            return await ctx.send(embed=embed)

        await self.bot.db.execute('DELETE FROM prefixes WHERE (guild_id, prefix) = ($1, $2)', ctx.guild.id, prefix)
        self.bot.prefixes[ctx.guild.id] = await self.bot.fetch_prefixes(ctx.message)

    @prefix.command(name='clear')
    @commands.has_permissions(manage_guild=True)
    async def prefix_clear(self, ctx : MyContext):
        """Clears all my prefixes and resets to default."""

        confirm = await ctx.confirm('Are you sure you want to clear all your prefixes?', timeout=30)
        if confirm is None:
            return await ctx.send('Timed out.')
        if confirm is False:
            return await ctx.send('Canceled.')

        await self.bot.db.execute('DELETE FROM prefixes WHERE guild_id = $1', ctx.guild.id)
        self.bot.prefixes[ctx.guild.id] = self.bot.PRE

        embed = Embed()
        embed.description = f'{self.bot.check} **|** Reset all my prefixes!'
        embed.colour = discord.Colour.green()
        return await ctx.send(embed=embed)

    @commands.command(aliases=['sourcecode', 'code'])
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def source(self, ctx, *, command: str = None):
        """
        Links to the bot's source code, or a specific command's
        """
        
        source_url = 'https://github.com/dartmern/metro'
        license_url = 'https://github.com/dartmern/metro/blob/master/LICENSE'
        branch = 'master'

        if command is None:
            embed = Embed()
            embed.colour = discord.Colour.yellow()
            embed.set_author(name='Here is my source code:')
            embed.description = str(f"My code is under the [**MPL**]({license_url}) license\n → {source_url}")
            return await ctx.send(embed=embed, view=StopView(ctx))

        if command == 'help':
            src = type(self.bot.help_command)
            module = src.__module__
            filename = inspect.getsourcefile(src)
            obj = 'help'
        else:
            obj = self.bot.get_command(command.replace('.', ' '))
            if obj is None:
                embed = Embed(description=f"Take the [**entire reposoitory**]({source_url})")
                embed.set_footer(text='Please make sure you follow the license.')
                return await ctx.send(embed=embed)

            src = obj.callback.__code__
            module = obj.callback.__module__
            filename = src.co_filename

        lines, firstlineno = inspect.getsourcelines(src)
        code_lines = inspect.getsource(src)
        if not module.startswith('discord'):
            # not a built-in command
            location = os.path.relpath(filename).replace('\\', '/')
        else:
            location = module.replace('.', '/') + '.py'
            source_url = 'https://github.com/Rapptz/discord.py'
            branch = 'master'

        
        final_url = f'<{source_url}/blob/{branch}/{location}#L{firstlineno}-L{firstlineno + len(lines) - 1}>'
        embed = Embed()
        embed.colour = discord.Colour.purple()
        embed.description = f"**__My source code for `{str(obj)}` is located at:__**\n{final_url}"\
                f"\n\nMy code is under licensed under the [**Mozilla Public License**]({license_url})."

        await ctx.send(embed=embed, view=SourceView(ctx, code_lines))

    async def github_request(self, method, url, *, params=None, data=None, headers=None):
        hdrs = {
            'Accept': 'application/vnd.github.inertia-preview+json',
            'User-Agent': 'RoboDanny DPYExclusive Cog',
            'Authorization': f'token {github_token}'
        }

        req_url = yarl.URL('https://api.github.com') / url

        if headers is not None and isinstance(headers, dict):
            hdrs.update(headers)

        await self._req_lock.acquire()
        try:
            async with self.bot.session.request(method, req_url, params=params, json=data, headers=hdrs) as r:
                remaining = r.headers.get('X-Ratelimit-Remaining')
                js = await r.json()
                if r.status == 429 or remaining == '0':
                    # wait before we release the lock
                    delta = discord.utils._parse_ratelimit_header(r)
                    await asyncio.sleep(delta)
                    self._req_lock.release()
                    return await self.github_request(method, url, params=params, data=data, headers=headers)
                elif 300 > r.status >= 200:
                    return js
                else:
                    raise GithubError(js['message'])
        finally:
            if self._req_lock.locked():
                self._req_lock.release()

    async def create_gist(self, content, *, description=None, filename=None, public=True):
        headers = {
            'Accept': 'application/vnd.github.v3+json',
        }

        filename = filename or 'output.txt'
        data = {
            'public': public,
            'files': {
                filename: {
                    'content': content
                }
            }
        }

        if description:
            data['description'] = description

        js = await self.github_request('POST', 'gists', data=data, headers=headers)
        return js['html_url']


    @commands.command()
    @commands.check(Cooldown(1, 30, 1, 15, commands.cooldowns.BucketType.user))
    async def gist(self, ctx : MyContext, filename : str, *, content : str):
        """Create and post a gist online."""

        link = await self.create_gist(content, filename=filename)
        await ctx.send(f"Created new gist.\n<{link}>")



    @commands.group(
        case_insensitive=True,
        invoke_without_command=True,
        slash_command=True,
        message_command=True
    )
    async def todo(self, ctx : MyContext):
        """Manage your todo lists."""

        await ctx.send_help('todo')

    @todo.command(
        name='add',
        slash_command=True
    )
    async def add(self, ctx : MyContext, *, item : commands.clean_content):
        """Add an item to your todo list"""

        data = await self.bot.db.fetchrow(
            "INSERT INTO todo (user_id, text, jump_url, added_time) VALUES ($1, $2, $3, $4) "
            "ON CONFLICT (user_id, text) WHERE ((user_id)::bigint = $1)"
            "DO UPDATE SET user_id = $1 RETURNING jump_url",
            ctx.author.id, item[0:4000], ctx.message.jump_url, ctx.message.created_at
        )
        
        if data['jump_url'] != ctx.message.jump_url:
            
            embed = Embed(color=discord.Colour.red())
            embed.description = "__**That item is already in your todo list.**__"
            return await ctx.send(embed=embed)

        else:
            embed = Embed(color=discord.Color.green())
            embed.description = "__**Added to your todo list**__\n"\
                "> %s" % item[0:200]
            await ctx.send(embed=embed)


    @todo.command(
        name='remove',
        slash_command=True
    )
    async def todo_remove(self, ctx : MyContext, index : int):
        """Remove one of your todo list entries."""

        entries = await self.bot.db.fetch(
            "SELECT text, added_time FROM todo WHERE user_id = $1 ORDER BY added_time ASC", ctx.author.id
        )
        try:
            to_del = entries[index - 1]
        except:
            embed = Embed(color=discord.Color.red())
            embed.description = "__**You do not have a task with that index**__ \n"\
                f"> Use `{ctx.clean_prefix}todo list` to check your todo list"
            return await ctx.send(embed=embed)

        await self.bot.db.execute("DELETE FROM todo WHERE (user_id, text) = ($1, $2)", ctx.author.id, to_del['text'])
        embed = Embed(color=discord.Colour.orange())
        embed.description = "__**Removed from your todo list**__ \n"\
            f"> {to_del['text'][0:250]}"
        return await ctx.send(embed=embed)
        

    @todo.command(
        name='clear',
        slash_command=True
    )
    async def todo_clear(self, ctx : MyContext):
        """Clear all your todo entries."""

        confirm = await ctx.confirm('Are you sure you want to clear your entire todo list?',delete_after=True, timeout=30)

        if confirm is None:
            return await ctx.send('Timed out.')

        if confirm is False:
            return await ctx.send('Canceled.')

        count = await self.bot.db.fetchval(
            "WITH deleted AS (DELETE FROM todo WHERE user_id = $1 RETURNING *) SELECT count(*) FROM deleted;", ctx.author.id
        )
        embed = Embed()
        embed.description = f"__**Cleared {count} entries from your todo list.**__"
        return await ctx.send(embed=embed)
    
    @todo.command(name='edit')
    async def todo_edit(self, ctx: MyContext, index: int, *, text: commands.clean_content) -> discord.Message:
        """Edit an exisiting todo list entry."""

        data = await self.bot.db.fetch("SELECT (text, added_time) FROM todo WHERE user_id = $1 ORDER BY added_time ASC", ctx.author.id)
        if not data:
            return await ctx.send("Your todo list is empty.")

        try:
            to_del = data[index - 1] # Since indexing starts at 0
        except KeyError:
            embed = Embed(color=discord.Color.yellow())
            embed.description = f"__**You do not have a task with the index {index}**__\n"\
                f"> Use `{ctx.clean_prefix}todo list` to check your todo list"
            return await ctx.send(embed=embed)

        await self.bot.db.execute("UPDATE todo SET text = $4, jump_url = $3 WHERE user_id = $1 AND text = $2", ctx.author.id, to_del['row'][0], ctx.message.jump_url, text)
        
        embed = Embed(color=0x90EE90)
        embed.description = f"__**Edited todo list entry {index}**__\n"\
            "> %s" % text[0:200]
        return await ctx.send(embed=embed)

    @todo.command(name='list')
    async def todo_list(self, ctx : MyContext):
        """Show your todo list."""

        data = await self.bot.db.fetch(
            "SELECT text, added_time, jump_url FROM todo WHERE user_id = $1 ORDER BY added_time ASC", ctx.author.id
        )
        if not data:
            return await ctx.send(f"Your todo list is empty.")

        menu = SimplePages(source=TodoListSource(entries=data, ctx=ctx), ctx=ctx, hide=True)
        await menu.start()
        
    @commands.command(aliases=['save'])
    @commands.bot_has_permissions(send_messages=True, read_message_history=True)
    async def archive(self, ctx, *, message : Optional[discord.Message]):
        """
        Archive a message by replying or passing in a message link / message id.
        I will pin the message content in our dms for later reference.
        """

        if not message:
            message = getattr(ctx.message.reference, "resolved", None)

        if not message:
            raise commands.BadArgument(f"You must either reply to a message, or pass in a message ID/jump url")

        # Resort message
        content = message.content or "_No content_"
        em = Embed(title="You archived a message!", url=message.jump_url, description=content, timestamp=discord.utils.utcnow())
        em.set_author(name=message.author, icon_url=message.author.display_avatar.url)
        try:
            msg = await ctx.author.send(embed=em)
            await msg.pin()
            await ctx.send(f"Archived the message in your DMs!\n{msg.jump_url}")
        except discord.Forbidden:
            await ctx.send("Oops! I couldn't send you a message. Are you sure your DMs are on?")

    async def get_active_timer(self, *, connection=None, days=7):
        query = "SELECT * FROM reminders WHERE expires < (CURRENT_DATE + $1::interval) ORDER BY expires LIMIT 1;"
        con = connection or self.bot.db

        record = await con.fetchrow(query, timedelta(days=days))
        if record:
            if type(record["extra"]) is dict:
                extra = record["extra"]
            else:
                extra = json.loads(record["extra"])
            record_dict = {
                "id": record["id"],
                "extra": extra,
                "event": record["event"],
                "created": record["created"],
                "expires": record["expires"],
            }
        return Timer(record=record_dict) if record else None

    async def wait_for_active_timers(self, *, connection=None, days=7):

        timer = await self.get_active_timer(connection=connection, days=days)
        
        if timer is not None:
            self._have_data.set()
            return timer

        self._have_data.clear()
        self._current_timer = None
        await self._have_data.wait()
        return await self.get_active_timer(connection=connection, days=days)

    async def call_timer(self, timer):
        
        # delete the timer
        query = "DELETE FROM reminders WHERE id=$1;"
        await self.bot.db.execute(query, timer.id)

        # dispatch the event
        event_name = f"{timer.event}_timer_complete"
        self.bot.dispatch(event_name, timer)

    async def dispatch_timers(self):

        try:            
            while not self.bot.is_closed():
                
                # can only asyncio.sleep for up to ~48 days reliably
                # so we're gonna cap it off at 40 days
                # see: http://bugs.python.org/issue20493
                timer = self._current_timer = await self.wait_for_active_timers(days=40)
                
                now = datetime.datetime.utcnow()
                if timer.expires >= now:
                    to_sleep = (timer.expires - now).total_seconds()
                    await asyncio.sleep(to_sleep)

                await self.call_timer(timer)
        except asyncio.CancelledError:
            raise
        except (OSError, discord.ConnectionClosed, asyncpg.PostgresConnectionError):
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.dispatch_timers())
        except Exception as e:
            raise e

    async def short_timer_optimisation(self, seconds, timer):
        await asyncio.sleep(seconds)
        event_name = f"{timer.event}_timer_complete"
        self.bot.dispatch(event_name, timer)


    async def create_timer(self, *args, **kwargs):
        """Creates a timer.
        Parameters
        -----------
        when: datetime.datetime
            When the timer should fire.
        event: str
            The name of the event to trigger.
            Will transform to 'on_{event}_timer_complete'.
        \*args
            Arguments to pass to the event
        \*\*kwargs
            Keyword arguments to pass to the event
        connection: asyncpg.Connection
            Special keyword-only argument to use a specific connection
            for the DB request.
        created: datetime.datetime
            Special keyword-only argument to use as the creation time.
            Should make the timedeltas a bit more consistent.
        Note
        ------
        Arguments and keyword arguments must be JSON serialisable.
        Returns
        --------
        :class:`Timer`
        """
        when, event, *args = args

        if not when or not event:
            raise commands.BadArgument('Invalid time provided, try e.g. "tomorrow" or "3 days"')

        try:
            connection = kwargs.pop('connection')
        except KeyError:
            connection = self.bot.db

        try:
            now = kwargs.pop('created')
        except KeyError:
            now = discord.utils.utcnow()

        # Remove timezone information since the database does not deal with it
        when = when.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        now = now.astimezone(datetime.timezone.utc).replace(tzinfo=None)

        timer = Timer.temporary(event=event, args=args, kwargs=kwargs, expires=when, created=now)
        delta = (when - now).total_seconds()
        if delta <= 30:
            # a shortcut for small timers
            self.bot.loop.create_task(self.short_timer_optimisation(delta, timer))
            return timer

        next_id_query = """SELECT MAX(id) FROM reminders;"""
        id = await connection.fetch(next_id_query)

        if id[0].get('max') is None:
            id = 1
        else:
            id = int(id[0].get('max')) + 1


        query = """INSERT INTO reminders (id, event, extra, expires, created)
                   VALUES ($1, $2, $3::jsonb, $4, $5)
                   RETURNING id;
                """

        jsonb = json.dumps({"args": args, "kwargs": kwargs}, default=str)

        row = await connection.fetchrow(query, id, event, jsonb, when, now)
        timer.id = row[0]

        # only set the data check if it can be waited on
        if delta <= (86400 * 40): # 40 days
            self._have_data.set()

        # check if this timer is earlier than our currently run timer
        if self._current_timer and when < self._current_timer.expires:
            # cancel the task and re-run it
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.dispatch_timers())

        return timer

    @commands.group(aliases=['remind','rm'], usage="<when>", invoke_without_command=True, slash_command=True)
    @commands.bot_has_permissions(send_messages=True)
    async def reminder(self, ctx, *, when : UserFriendlyTime(commands.clean_content, default='\u2026')):
        """Reminds you of something after a certain amount of time.

        The input can be any direct date (e.g. YYYY-MM-DD) or a human
        readable offset. Examples:

        - "next thursday at 3pm do something funny"
        - "do the dishes tomorrow"
        - "in 3 days do the thing"
        - "2d unmute someone"

        Times are in UTC.
        """
        try:
            await self.create_timer(
            when.dt,
            "reminder",
            ctx.author.id,
            ctx.channel.id,
            when.arg,
            connection=self.bot.db,
            created=ctx.message.created_at,
            message_id=ctx.message.id
            )
        except Exception as e:
            return await ctx.send(str(e))

        delta = discord.utils.format_dt(when.dt, 'R')
        await ctx.send(f'Alright, {ctx.author.mention} I will remind you {delta} about: \n> {when.arg}')

    @reminder.command(
        name='list',
        aliases=['show'],
        slash_command=True
    )
    async def reminders_list(self, ctx):
        """
        Display all your current reminders.
        """

        query = """
                SELECT id, expires, extra #>> '{args,2}'
                FROM reminders
                WHERE event = 'reminder'
                AND extra #>> '{args,0}' = $1
                ORDER BY expires;
                """

        records = await self.bot.db.fetch(query, str(ctx.author.id))

        if not records:
            return await ctx.send('You have no reminders.')

        menu = ExtraPages(source=MySource(records))
        
        await menu.start(ctx)

    
    @reminder.command(
        name='delete',
        aliases=['cancel','remove'],
        slash_command=True
    )
    async def reminder_remove(self, ctx, *, id : int):
        """
        Deletes a reminder by it's id
        """        

        query = """
                DELETE FROM reminders
                WHERE id=$1
                AND event = 'reminder'
                AND extra #>> '{args,0}' = $2;
                """

        status = await self.bot.db.execute(query, id, str(ctx.author.id))
        if status == "DELETE 0":
            return await ctx.send('Could not delete any reminders with that ID')

        # if the current timer is being deleted
        if self._current_timer and self._current_timer.id == id:
            # cancel the task and re-run it
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.dispatch_timers())

        await ctx.send("Successfully deleted reminder.")


    @reminder.command(
        name='clear',
        aliases=['wipe'],
        slash_command=True
    )
    async def reminder_clear(self, ctx):
        """
        Clear all reminders you set.
        """

        query = """
                SELECT COUNT(*)
                FROM reminders
                WHERE event = 'reminder'
                AND extra #>> '{args,0}' = $1;
                """

        author_id = str(ctx.author.id)
        total = await self.bot.db.fetchrow(query, author_id)
        total = total[0]

        if total == 0:
            return await ctx.send("You have no reminders to clear.")

        confirm = await ctx.confirm(f'Are you sure you want to clear **{total}** reminder(s)', timeout=30)

        if confirm is None:
            return await ctx.send('Timed out.')

        if confirm is False:
            return await ctx.send('Canceled.')

        query = """DELETE FROM reminders WHERE event = 'reminder' AND extra #>> '{args,0}' = $1;"""

        await self.bot.db.execute(query, author_id)

        if self._current_timer and self._current_timer.author_id == ctx.author.id:
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.dispatch_timers())

        await ctx.send(f'Successfully deleted **{total}** reminder(s)')
        
    
    @commands.Cog.listener()
    async def on_reminder_timer_complete(self, timer):
        author_id, channel_id, message = timer.args
 
        await self.bot.wait_until_ready()

        try:
            channel = self.bot.get_channel(int(channel_id)) or (
                await self.bot.fetch_channel(int(channel_id))
            )
        except (discord.HTTPException, discord.NotFound):
            return

        msg = f"<@{author_id}>, {discord.utils.format_dt(timer.created_at.replace(tzinfo=datetime.timezone.utc), 'R')}, you wanted me to remind you about: \n> {message}"

        try:
            await channel.send(msg)
        except discord.HTTPException:
            return

    @commands.group(name='giveaway', aliases=['gaw', 'g'], invoke_without_command=True, case_insensitive=True)
    @commands.bot_has_permissions(send_messages=True, add_reactions=True)
    @commands.has_guild_permissions(manage_guild=True)
    async def giveaway(self, ctx : MyContext):
        """Manage and create giveaways for your server."""
        await ctx.help()

    @giveaway.command(name='start', usage="<duration> [winners='1'] <prize> [flags]")
    @commands.check(Cooldown(8, 8, 12, 8, commands.BucketType.member))
    @commands.bot_has_permissions(send_messages=True, add_reactions=True)
    @commands.has_guild_permissions(manage_guild=True)
    async def giveaway_start(self, ctx : MyContext, duration : FutureTime, winners : Optional[WinnerConverter] = 1, *, prize : str):
        """
        Start a giveaway!
        
        If the winners argument is no provided there will be 1 winner.
        """
        await ctx.defer()

        message = ""
        to_send = ""

        flags = prize.partition("--")[2]
        prize = prize.split('--')[0]
        if flags:
            convertered = await Flags().convert(ctx, "--%s" % flags)
            if convertered.ping:
                to_send += convertered.ping.mention
            if convertered.message:
                message += convertered.message[0:1950]
        
        if duration.dt < (ctx.message.created_at + datetime.timedelta(seconds=5)):
            return await ctx.send("Duration is too short. Must be at least 5 seconds.")

        e = Embed()
        e.colour = 0xe91e63
        e.set_author(name=prize[0:40])
        e.description = f"\n React with \U0001f389 to enter!"\
                        f"\n Ends {discord.utils.format_dt(duration.dt, 'R')} ({discord.utils.format_dt(duration.dt, 'f')})"\
                        f"\n Hosted by: {ctx.author.mention}"
        e.set_footer(text=f'{winners} winner{"s" if winners > 1 else ""}')

        if message:
            embeds = [Embed(color=discord.Color.blue(), description=message), e]
        else:
            embeds = [e]

        giveaway_message = await ctx.send(f":tada: **GIVEAWAY!** :tada: \n{to_send}",embeds=embeds, allowed_mentions=discord.AllowedMentions(roles=True))
        await giveaway_message.add_reaction('\U0001f389')

        try:
            timer = await self.create_timer(
                duration.dt,
                "giveaway",
                ctx.guild.id,
                ctx.author.id,
                ctx.channel.id,
                giveaway_message.id,
                winners=winners,
                prize=prize
            )
        except Exception as e:
            traceback_string = "".join(traceback.format_exception(
                    etype=None, value=e, tb=e.__traceback__)
            )
            await ctx.send(str(traceback_string))
            return
        e.set_footer(text=f'{winners} winner{"s" if winners > 1 else ""} | Giveaway ID: {timer.id}')
        if message:
            embeds = [Embed(color=discord.Color.blue(), description=message), e]
        else:
            embeds = [e]

        await giveaway_message.edit(f":tada: **GIVEAWAY!** :tada:\n{to_send}",embeds=embeds, allowed_mentions=discord.AllowedMentions(roles=True))
        return

    @giveaway.command(name='list')
    @commands.check(Cooldown(4, 8, 6, 8, commands.BucketType.member))
    @commands.bot_has_permissions(send_messages=True, add_reactions=True)
    @commands.has_guild_permissions(manage_guild=True)
    async def giveaway_list(self, ctx: MyContext):
        """List all the active giveaways."""

        cog = self.bot.get_cog("utility")
        if not cog:
            raise commands.BadArgument("This feature is currectly unavailable. Please try again later.")

        embed = Embed()
        embed.colour = discord.Colour.yellow()

        query = """
                SELECT (id, expires, extra, created)
                FROM reminders
                WHERE event = 'giveaway'
                AND extra #>> '{args,0}' = $1
                ORDER BY expires;
                """
        records = await self.bot.db.fetch(query, str(ctx.guild.id))
        if not records:
            return await ctx.send("There are no active giveaways in this guild.")

        to_append = []
        for record in records:
            _id : int = record['row'][0]
            expires : datetime.datetime = pytz.utc.localize(record['row'][1])
            extra : Dict = json.loads(record['row'][2])
            created = pytz.utc.localize(record['row'][3])
            args = extra['args']
            kwargs = extra['kwargs']

            guild_id, host_id, channel_id, giveaway_id = args
            winners = kwargs['winners']
            prize = kwargs['prize']

            to_append.append(
                f"\n\n**{prize}** - {winners} winner{'s' if winners > 1 else ''} - [jump url](https://discord.com/channels/{guild_id}/{channel_id}/{giveaway_id}) - ID: {_id}" # save an api call
                f"\n Created: {discord.utils.format_dt(created, 'R')}"
                f"\n Ends: {discord.utils.format_dt(expires, 'R')}"
                f"\n Host: <@{host_id}>"
            )

        await ctx.paginate(to_append)
            
    @giveaway.command(name='end')
    @commands.check(Cooldown(4, 8, 6, 8, commands.BucketType.member))
    @commands.bot_has_permissions(send_messages=True, add_reactions=True)
    @commands.has_guild_permissions(manage_guild=True)
    async def giveaway_end(self, ctx : MyContext, id : int):
        """
        End a giveaway early.
        
        This is different from canceling it as I will roll the winners.
        
        You can find the giveaway's id in the footer of the giveaway's embed.
        
        You cannot end giveaways that have `None` as their id.
        This is due to them being too short.
        """
        
        query = """
                SELECT extra FROM reminders
                WHERE id = $1
                AND event = 'giveaway'
                """
        data = await self.bot.db.fetchrow(query, id) # Kinda have to do 2 queries to get the jump_url and proper data
        if not data:
            return await ctx.send(f"Could not delete any giveaways with that ID.\nUse `{ctx.prefix}g list` to list all the running giveaways.")

        extra = json.loads(data['extra'])

        guild_id = extra['args'][0]
        host_id = extra['args'][1]
        channel_id = extra['args'][2]
        message_id = extra['args'][3]
        winners = extra['kwargs']['winners']
        prize = extra['kwargs']['prize']

        query = """
                DELETE FROM reminders
                WHERE id=$1
                AND event = 'giveaway'
                AND extra #>> '{args,1}' = $2;
                """
        status = await self.bot.db.execute(query, id, str(ctx.author.id))

        if self._current_timer and self._current_timer.id == id:
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.dispatch_timers())

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return await ctx.send("I'm having trouble ending this giveaway. Issue: `guild_id from select is None`\nThe giveaway has been deleted from my database.")
        
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            return await ctx.send("I'm having trouble ending this giveaway. Issue: `channel_id from select is None`\nThe giveaway has been deleted from my database.")

        message = discord.utils.get(self.bot.cached_messages, id=message_id)
        if message is None:
            try:
                message = await channel.fetch_message(message_id)
            except discord.NotFound:
                return await ctx.send("I'm having trouble ending this giveaway. Issue: `message could not be fetched`\nThe giveaway has been deleted from my database.") # At this found we can't find it in the cache or fetch it, it's deleted.
        
        reactions = await message.reactions[0].users().flatten()
        reactions.remove(guild.me)
        if len(reactions) < 1:
            e = Embed()
            e.set_author(name=prize[0:40])
            e.colour = discord.Colour(3553599)
            e.description = f"\n Not enough entrants to determine a winner!"\
                            f"\n Ended {discord.utils.format_dt(discord.utils.utcnow(), 'R')}"\
                            f"\n Hosted by: <@{host_id}>" # No API call needed here
            e.set_footer(text=f'{winners} winner{"s" if winners > 1 else ""}')

            await message.edit(embed=e, content=f"\U0001f389\U0001f389 **GIVEAWAY ENDED** \U0001f389\U0001f389")
            await ctx.check()
            return # No need to choose winners as there is nothing to choose from
                    
        else:
            winners_string = [] 
            winners_list = reactions

            for _ in range(winners):
                winner = random.choice(winners_list)
                winners_list.pop(winners_list.index(winner))
                        
                member = guild.get_member(winner.id)

                em = Embed()
                em.colour = discord.Colour.green()
                em.description = f"You won the giveaway for [{prize}]({message.jump_url}) in **{guild}**"

                try:
                    await member.send(embed=em)
                except discord.HTTPException:
                    pass

                winners_string.append(winner.id)

            e = discord.Embed()
            e.set_author(name=prize[0:40])
            e.colour = discord.Colour.green()
            e.description = f"\n Winner{'s: ' if len(winners_string) > 1 else ':'} {', '.join(f'<@{users}>' for i, users in enumerate(winners_string))}"\
                                    f"\n Ended {discord.utils.format_dt(discord.utils.utcnow(), 'R')}"\
                                    f"\n Hosted by: <@{host_id}>" # No API call needed here
            e.set_footer(text=f'{winners} winner{"s" if winners > 1 else ""}')
            await message.edit(embed=e, content=f"\U0001f389\U0001f389 **GIVEAWAY ENDED** \U0001f389\U0001f389")
            await message.reply(f'{", ".join(f"<@{users}>" for i, users in enumerate(winners_string))} {"have" if len(winners_string) > 1 else "has"} won the giveaway for **{prize}**\n{message.jump_url}')
            await ctx.check()
            return


    @commands.Cog.listener('on_giveaway_timer_complete')
    async def giveaway_end_event(self, timer):
        guild_id, host_id, channel_id, giveaway_id = timer.args
        winners = timer.kwargs.get("winners")
        prize = timer.kwargs.get("prize")

        await self.bot.wait_until_ready()

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return # If we can't even find the guild we can't proceed

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            return # Channel can't be found

        message = discord.utils.get(self.bot.cached_messages, id=giveaway_id)
        if message is None:
            try:
                message = await channel.fetch_message(giveaway_id)
            except discord.NotFound:
                return # At this found we can't find it in the cache or fetch it, it's deleted.
        
        reactions = await message.reactions[0].users().flatten()
        reactions.remove(guild.me)
        if len(reactions) < 1:
            e = Embed()
            e.set_author(name=prize[0:40])
            e.colour = discord.Colour(3553599)
            e.description = f"\n Not enough entrants to determine a winner!"\
                            f"\n Ended {discord.utils.format_dt(discord.utils.utcnow(), 'R')}"\
                            f"\n Hosted by: <@{host_id}>" # No API call needed here
            e.set_footer(text=f'{winners} winner{"s" if winners > 1 else ""}')

            await message.edit(embed=e, content=f"\U0001f389\U0001f389 **GIVEAWAY ENDED** \U0001f389\U0001f389")
            return # No need to choose winners as there is nothing to choose from
                    
        else:
            winners_string = [] 
            winners_list = reactions

            for _ in range(winners):
                winner = random.choice(winners_list)
                winners_list.pop(winners_list.index(winner))
                        
                member = guild.get_member(winner.id)

                em = Embed()
                em.colour = discord.Colour.green()
                em.description = f"You won the giveaway for [{prize}]({message.jump_url}) in **{guild}**"

                try:
                    await member.send(embed=em)
                except discord.HTTPException:
                    pass

                winners_string.append(winner.id)

            e = discord.Embed()
            e.set_author(name=prize[0:40])
            e.colour = discord.Colour.green()
            e.description = f"\n Winner{'s: ' if len(winners_string) > 1 else ':'} {', '.join(f'<@{users}>' for i, users in enumerate(winners_string))}"\
                                    f"\n Ended {discord.utils.format_dt(discord.utils.utcnow(), 'R')}"\
                                    f"\n Hosted by: <@{host_id}>" # No API call needed here
            e.set_footer(text=f'{winners} winner{"s" if winners > 1 else ""}')
            await message.edit(embed=e, content=f"\U0001f389\U0001f389 **GIVEAWAY ENDED** \U0001f389\U0001f389")
            await message.reply(f'{", ".join(f"<@{users}>" for i, users in enumerate(winners_string))} {"have" if len(winners_string) > 1 else "has"} won the giveaway for **{prize}**\n{message.jump_url}')
            return

    @commands.command(name='raw-message', aliases=['rmsg', 'raw'])
    @commands.check(Cooldown(1, 30, 1, 15, commands.BucketType.user))
    async def raw_message(self, ctx: MyContext, message: Optional[discord.Message]):
        async with ctx.typing():
            message: discord.Message = getattr(ctx.message.reference, 'resolved', message)
            if not message:
                raise commands.BadArgument("Please specify a message or reply to one.")

            try:
                message = await self.bot.http.get_message(message.channel.id, message.id)
            except discord.HTTPException:
                raise commands.BadArgument("There was an issue fetching that message.")

            data = json.dumps(message, indent=4)
            if len(data) > 1950:
                link = await self.post_mystbin(data)
                to_send = f"__**Output was too long:**__\n<{link}.python>"
            else:
                to_send = f"```json\n{data}\n```"
            await ctx.send(to_send)


    @commands.command(name='first-message', aliases=['firstmsg'])
    @commands.check(Cooldown(1, 3, 1, 2, commands.BucketType.user))
    async def first_message(self, ctx: MyContext, *, channel: Optional[discord.TextChannel]) -> discord.Message:
        """Get the first message in this channel."""
        channel = channel or ctx.channel

        first_message : discord.Message = (await channel.history(limit=1, oldest_first=True).flatten())[0]

        embed = Embed(color=discord.Color.blue())
        embed.title = f"First message in #{channel.name[0:40]}"
        embed.description = f"__**Message**__"\
            f"\nAuthor: {first_message.author.mention} (ID: {first_message.author.id})"\
            f"\n Sent at: {discord.utils.format_dt(first_message.created_at, 'F')} ({discord.utils.format_dt(first_message.created_at, 'R')})"\
            f"\n Jump URL: [Click here]({first_message.jump_url} \"Click here to jump to message\")"
        await ctx.send(embed=embed)

    async def load_highlight(self):
        await self.bot.wait_until_ready()
        self.highlight = {}

        query = """
                SELECT * FROM highlight
                """
        records = await self.bot.db.fetch(query)
        if records:
            for record in records:
                self.highlight[record['text']] = (record['guild_id'], record['author_id'])

    @commands.group(name='highlight', invoke_without_command=True, case_insensitive=True, aliases=['hl'])
    @commands.guild_only()
    async def highlight(self, ctx: MyContext):
        """Highlight word notifications."""
        await ctx.help()

    @highlight.command(name='add', aliases=['+'])
    @commands.guild_only()
    async def highlight_add(self, ctx: MyContext, *, word: commands.clean_content):
        """
        Add a word to your highlight list.
        
        For the best experience delete your message so people don't know your highlights.
        """
        word = word.lower() # remove the pain in the ass of highlight

        if len(word) < 2:
            raise commands.BadArgument("Word needs to be at least 2 characters long.")
        if len(word) > 50:
            raise commands.BadArgument("Word needs to be less than 50 characters long.")
        
        data = await self.bot.db.fetchval("SELECT highlight FROM highlight WHERE author_id = $1 AND guild_id = $2 AND text = $3", ctx.author.id, ctx.guild.id, word)
        if data:
            raise commands.BadArgument(f'"{word}" is already in your highlights list.')
        
        await self.bot.db.execute("INSERT INTO highlight (author_id, text, guild_id) VALUES ($1, $2, $3)", ctx.author.id, word, ctx.guild.id)
        self.highlight[word] = (ctx.guild.id, ctx.author.id)

        await ctx.send(f"{self.bot.emotes['check']} Added \"{word}\" to your highlights.", delete_after=5)
        await asyncio.sleep(4)
        await ctx.message.delete(silent=True)

    @highlight.command(name='remove', aliases=['-'])
    @commands.guild_only()
    async def highlight_remove(self, ctx: MyContext, *, word: commands.clean_content):
        """Remove a word from your highlight list."""
        word = word.lower()

        status = await self.bot.db.execute("DELETE FROM highlight WHERE author_id = $1 AND text = $2 AND guild_id = $3", ctx.author.id, word, ctx.guild.id)
        if status != 'DELETE 1':
            raise commands.BadArgument(f"{self.bot.emotes['cross']} The word \"{word}\" is not in your highlight list.")
        
        del self.highlight[word]
        await ctx.send(f"{self.bot.emotes['check']} Removed \"{word}\" from your highlight list.")

    @highlight.command(name='list', aliases=['show', 'display'])
    @commands.guild_only()
    async def highlight_list(self, ctx: MyContext):
        """
        Show your highlight list.
        
        This list will be removed after 7 seconds for your privacy.
        """
        data = await self.bot.db.fetch("SELECT text FROM highlight WHERE author_id = $1 AND guild_id = $2", ctx.author.id, ctx.guild.id)
        
        embed = discord.Embed(color=discord.Color.yellow())
        embed.set_author(name=f'{ctx.author}\'s highlights', icon_url=ctx.author.display_avatar.url)
        embed.description = "\n".join([x['text'] for x in data])
        embed.set_footer(text=f'This message will get deleted in 7 seconds so people don\'t know your highlights.')
        await ctx.send(embed=embed, delete_after=7)
        await asyncio.sleep(6)
        await ctx.message.delete(silent=True)

    @highlight.command(name='clear', aliases=['wipe'])
    @commands.guild_only()
    async def highlight_clear(self, ctx: MyContext):
        """Clear your highlights."""

        data = await self.bot.db.fetch("SELECT * FROM highlight WHERE author_id = $1 AND guild_id = $2", ctx.author.id, ctx.guild.id)
        if not data:
            raise commands.BadArgument(f"{self.bot.emotes['cross']} You have no highlights to clear...")

        confirm = await ctx.confirm("Are you sure you want to clear your highlight list?")
        if confirm is False:
            return await ctx.send("Canceled.")
        if confirm is None:
            return await ctx.send("Timed out.")
        
        await self.bot.db.execute("DELETE FROM highlight WHERE author_id = $1 AND guild_id = $2", ctx.author.id, ctx.guild.id)
        await self.load_highlight() # whatever

        await ctx.send(f"{self.bot.emotes['check']} Cleared all your highlights.")

    async def generate_context(self, msg, hl):
        fmt = []
        async for m in msg.channel.history(limit=5):
            time = m.created_at.strftime("%H:%M:%S")
            fmt.append(f"**[{time}] {m.author.name}:** {m.content[:200]}")
        e = discord.Embed(title=f"**{hl}**", description='\n'.join(fmt[::-1]))
        e.add_field(name='Jump to', value=f"[Jump!]({m.jump_url})")
        return e

    @commands.Cog.listener("on_message")
    async def highlight_core(self, message: discord.Message):
        """The core of highlight."""

        if message.guild is None:
            return
        if message.author.bot:
            return

        final_message = self.website_regex.sub('', message.content.lower())
        final_message = self.regex_pattern.sub('', final_message)

        if self.highlight:
            try:
                for key, value in self.highlight.items(): 
                    if message.guild.id != value[0]:
                        return
                    if str(key).lower() in final_message: #and message.author.id != value[1]:
                        e = await self.generate_context(message, key)
                        user = message.guild.get_member(value[1])
                        if user is not None and message.channel.permissions_for(user).read_messages:
                            ctx = await self.bot.get_context(message)
                            if ctx.prefix is not None:
                                continue
                            await user.send(f"In {message.channel.mention}, you were mentioned with the highlighted word \"{key}\"", embed=e)
            except RuntimeError:
                pass # Can't do shit really

        
    
        

def setup(bot):
    bot.add_cog(utility(bot))