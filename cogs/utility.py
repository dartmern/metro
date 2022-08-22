from collections import defaultdict
import re
import discord
from discord.ext import commands, menus
from discord import app_commands

from typing import Dict, List, Literal, Optional

from bot import MetroBot
from utils.constants import TESTING_GUILD

from utils.json_loader import read_json
from utils.custom_context import MyContext
from utils.remind_utils import human_timedelta
from utils.useful import Cooldown, Embed, delete_silent
from utils.useful import Embed
from utils.new_pages import SimplePages
from utils.remind_utils import UserFriendlyTime

from datetime import timedelta
import json
import io
import asyncio
import datetime
import time
import os
import asyncpg
import yarl
import inspect
import unicodedata

from utils.pages import StopView

class SourceView(discord.ui.View):
    def __init__(self, ctx : MyContext, code : str):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.code = code

    async def interaction_check(self, interaction: discord.Interaction):
        if self.ctx.author.id == interaction.user.id:
            return True
        else:
            await interaction.response.send_message(
                "Only the command invoker can use this button.", ephemeral=True
            )

    @discord.ui.button(label='Source File', emoji='\U0001f4c1', style=discord.ButtonStyle.blurple)
    async def foo(self, interaction : discord.Interaction, button : discord.ui.Button):
        
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
    async def bar(self, interaction : discord.Interaction, button : discord.ui.Button):

        async with self.ctx.bot.session.post(f"https://mystb.in/documents", data=self.code) as s:
            res = await s.json()
            url_key = res['key']
        
        await interaction.response.send_message(f"Output: https://mystb.in/{url_key}.python", view=StopView(self.ctx))

        button.style = discord.ButtonStyle.gray
        button.disabled = True
        await interaction.message.edit(view=self)

    @discord.ui.button(emoji='\U0001f5d1', style=discord.ButtonStyle.red)
    async def stop_view(self, interaction : discord.Interaction, button : discord.ui.Button):
        """
        Stop the pagination session. 
        Unless this pagination menu was invoked with a slash command
        """

        await self.ctx.check()
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.stop()


class MySource(menus.ListPageSource):
    def __init__(self, data, amount: int):
        super().__init__(data, per_page=5)
        self.amount = amount

    async def format_page(self, menu, entries):

        embed= Embed()

        for i in entries:
            embed.add_field(name=f'ID: {i.get("id")}: {discord.utils.format_dt((i.get("expires")).replace(tzinfo=datetime.timezone.utc), "R")}',value=i.get("?column?"),inline=False)

        embed.set_footer(text=f'{self.amount} reminder{"s" if self.amount > 1 else ""}')

        return embed

    
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
        super().__init__(entries, per_page=16)
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
        self._req_lock = asyncio.Lock()
        self._have_data = asyncio.Event()
        self._current_timer = None
        self._task = bot.loop.create_task(self.dispatch_timers())

        self.highlight = defaultdict(list)

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
        paste = await self.bot.mystbin_client.create_paste(filename='paste', content=data)
        
        return f"https://mystb.in/{paste.id}"

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

    @commands.hybrid_command(name='permissions',brief="Shows a member's permissions in a specific channel.")
    @app_commands.describe(member='The member\'s permissions you want to view.')
    @app_commands.describe(channel='The channel you want to view the member\'s permissions.')
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

    @commands.hybrid_command()
    @app_commands.describe(characters='The characters you want information on.')
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

    @commands.hybrid_group(name='prefix', case_insensitive=True, invoke_without_command=True, fallback='help')
    @commands.has_permissions(manage_guild=True)
    @commands.bot_has_permissions(send_messages=True)
    async def prefix(self, ctx : MyContext):
        """
        Manage prefixes for the bot.
        """
        return await ctx.help()


    @prefix.command(name='add')
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(prefix='The prefix you want to add.')
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
    @app_commands.describe(prefix='The prefix you want to remove.')
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

        confirm = await ctx.confirm('Are you sure you want to clear all your prefixes?', timeout=30, delete_after=False)
        if confirm.value is None:
            return await confirm.message.edit(content='Timed out.', view=None)
        if confirm.value is False:
            return await confirm.message.edit(content='Canceled.', view=None)

        await self.bot.db.execute('DELETE FROM prefixes WHERE guild_id = $1', ctx.guild.id)
        self.bot.prefixes[ctx.guild.id] = self.bot.PRE

        embed = Embed()
        embed.description = f'{self.bot.check} **|** Reset all my prefixes!'
        embed.colour = discord.Colour.green()
        return await confirm.message.edit(content="", embed=embed, view=None)

    @app_commands.command(name='source')
    @app_commands.describe(command='The command\'s source you wish to search for.')
    async def source_app_command(self, interaction: discord.Interaction, command: Optional[str]):
        """Get the bot's source code or a specific command's."""

        source_url = 'https://github.com/dartmern/metro'
        license_url = 'https://github.com/dartmern/metro/blob/master/LICENSE'
        branch = 'master'

        if command is None:
            embed = Embed(color=interaction.client.user.color)
            embed.set_author(name='Here is my source code:')
            embed.description = str(f"My code is under the [**MPL**]({license_url}) license\n → {source_url}")
            return await interaction.response.send_message(embed=embed, view=StopView(interaction))

        if command == 'help':
            src = type(self.bot.help_command)
            module = src.__module__
            filename = inspect.getsourcefile(src)
            obj = 'help'
        else:
            obj = self.bot.get_command(command.replace('.', ' '))
            if obj is None:
                embed = Embed(description=f"Could not find that command. Take the [**entire reposoitory**]({source_url})", color=interaction.client.user.color)
                embed.set_footer(text='Please make sure you follow the license.')
                return await interaction.response.send_message(embed=embed, view=StopView(interaction))

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
        embed = Embed(color=interaction.client.user.color)
        embed.description = f"**__My source code for `{str(obj)}` is located at:__**\n{final_url}"\
                f"\n\nMy code is under licensed under the [**Mozilla Public License**]({license_url})."

        await interaction.response.send_message(embed=embed, view=StopView(interaction))#, view=SourceView(ctx, code_lines))

    @source_app_command.autocomplete('command')
    async def source_app_command_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:
            
        new = []
        for command in interaction.client.commands:
            if isinstance(command, commands.Group):
                new.append(command.name)
                for subcommand in command.commands:
                    new.append(command.name + " " + subcommand.name)
            else:
                new.append(command.name)

        return [
            app_commands.Choice(name=item, value=item)
            for item in new if current.lower() in item.lower()
        ][:8]

    @commands.command(aliases=['sourcecode', 'code', 'src'])
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def source(self, ctx, *, command: str = None):
        """
        Links to the bot's source code, or a specific command's
        """
        
        source_url = 'https://github.com/dartmern/metro'
        license_url = 'https://github.com/dartmern/metro/blob/master/LICENSE'
        branch = 'master'

        if command is None:
            embed = Embed(color=ctx.color)
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
                embed = Embed(description=f"Take the [**entire reposoitory**]({source_url})", color=ctx.color)
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
        embed = Embed(color=ctx.color)
        embed.description = f"**__My source code for `{str(obj)}` is located at:__**\n{final_url}"\
                f"\n\nMy code is under licensed under the [**Mozilla Public License**]({license_url})."

        await ctx.send(embed=embed, view=SourceView(ctx, code_lines))

    async def github_request(self, method, url, *, params=None, data=None, headers=None):
        hdrs = {
            'Accept': 'application/vnd.github.inertia-preview+json',
            'User-Agent': 'MetroDiscordBot Utilties Cog',
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


    @commands.hybrid_group(case_insensitive=True, invoke_without_command=True, fallback='help')
    async def todo(self, ctx : MyContext):
        """Manage your todo lists."""

        await ctx.help()

    @todo.command(name='add')
    @app_commands.describe(item='The item you want added to your todo list.')
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


    @todo.command(name='remove')
    @app_commands.describe(index='The index of the item you want to remove. See /todo list')
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
        

    @todo.command(name='clear')
    async def todo_clear(self, ctx : MyContext):
        """Clear all your todo entries."""

        confirm = await ctx.confirm(
            'Are you sure you want to clear your entire todo list?', 
            delete_after=False, 
            timeout=30,
            interaction=ctx.interaction if ctx.interaction else None)

        if confirm.value is None:
            return await confirm.message.edit(content='Timed out.', view=None)

        if confirm.value is False:
            return await confirm.message.edit(content='Canceled.', view=None)

        count = await self.bot.db.fetchval(
            "WITH deleted AS (DELETE FROM todo WHERE user_id = $1 RETURNING *) SELECT count(*) FROM deleted;", ctx.author.id
        )
        embed = Embed()
        embed.description = f"__**Cleared {count} entries from your todo list.**__"
        return await confirm.message.edit(content='', embed=embed, view=None)
    
    @todo.command(name='edit')
    @app_commands.describe(index='The index of the item you want to edit. See /todo list')
    @app_commands.describe(text='The new text for that todo item.')
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

        menu = SimplePages(source=TodoListSource(entries=data, ctx=ctx), ctx=ctx, compact=True)
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

        blacklist = ['giveaway', 'new_giveaway']
        if event not in blacklist:
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

    @commands.hybrid_group(aliases=['remind','rm'], usage="<when>", invoke_without_command=True, fallback='create')
    @commands.bot_has_permissions(send_messages=True)
    @app_commands.describe(when='The duration and what you want to be reminded of.')
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
        if not when:
            raise commands.BadArgument('Invalid time provided, try e.g. "tomorrow" or "3 days"')
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
        aliases=['show']
    )
    async def reminders_list(self, ctx: MyContext):
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
        
        menu = SimplePages(source=MySource(records, len(records)), compact=True, ctx=ctx)
        await menu.start()
    
    @reminder.command(
        name='delete',
        aliases=['cancel','remove']
    )
    @app_commands.describe(id='The ID of the reminder you want to delete.')
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
        aliases=['wipe']
    )
    async def reminder_clear(self, ctx: MyContext):
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

        confirm = await ctx.confirm(f'Are you sure you want to clear **{total}** reminder(s)', timeout=30, delete_after=False)

        if confirm.value is None:
            return await confirm.message.edit(content='Timed out.', view=None)

        if confirm.value is False:
            return await confirm.message.edit(content='Canceled.', view=None)

        query = """DELETE FROM reminders WHERE event = 'reminder' AND extra #>> '{args,0}' = $1;"""

        await self.bot.db.execute(query, author_id)

        if self._current_timer and self._current_timer.author_id == ctx.author.id:
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.dispatch_timers())

        await confirm.message.edit(content=f'Successfully deleted **{total}** reminder(s)', view=None)
        
    
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

        guild_id = channel.guild.id if isinstance(channel, (discord.TextChannel, discord.Thread)) else '@me'
        message_id = timer.kwargs.get("message_id")

        jump_url = f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"
        view = discord.ui.View()
        view.add_item(discord.ui.Button(url=jump_url, label='Jump to original message'))
        try:
            await channel.send(msg, view=view)
        except discord.HTTPException:
            pass 
        
    @commands.command(name='raw-message', aliases=['rmsg', 'raw', 'rawmessage'])
    @commands.check(Cooldown(1, 30, 1, 15, commands.BucketType.user))
    async def raw_message(self, ctx: MyContext, message: Optional[discord.Message]):
        """
        Get the raw json format of a message.

        Pass in a message or reply to work this.
        """
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


    @commands.hybrid_command(name='first-message', aliases=['firstmsg', 'firstmessage'])
    @commands.check(Cooldown(1, 3, 1, 2, commands.BucketType.user))
    @app_commands.describe(channel='The channel you want to see the first message.')
    async def first_message(self, ctx: MyContext, *, channel: Optional[discord.TextChannel]) -> discord.Message:
        """Get the first message in a channel."""
        channel = channel or ctx.channel

        first_message = [message async for message in channel.history(oldest_first=True, limit=1)][0]

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

    @commands.hybrid_group(name='highlight', invoke_without_command=True, case_insensitive=True, aliases=['hl'], fallback='help')
    @commands.guild_only()
    async def highlight(self, ctx: MyContext):
        """Highlight word notifications."""
        await ctx.help()

    @highlight.command(name='add', aliases=['+'])
    @app_commands.describe(word='The word you want added to your highlights.')
    @commands.guild_only()
    async def highlight_add(self, ctx: MyContext, *, word: commands.clean_content):
        """
        Add a word to your highlight list.
        """
        word = word.lower() # remove the pain in the ass of highlight

        if len(word) < 2:
            return await ctx.send("Word needs to be at least 2 characters long.", hide=True)
        if len(word) > 50:
            return await ctx.send("Word needs to be less than 50 characters long.", hide=True)
        
        data = await self.bot.db.fetchval("SELECT highlight FROM highlight WHERE author_id = $1 AND guild_id = $2 AND text = $3", ctx.author.id, ctx.guild.id, word)
        if not data:  
            await self.bot.db.execute("INSERT INTO highlight (author_id, text, guild_id) VALUES ($1, $2, $3)", ctx.author.id, word, ctx.guild.id)
            self.highlight[word] = (ctx.guild.id, ctx.author.id)

        message = await ctx.send(f"{self.bot.emotes['check']} Updated your highlight list.", hide=True)
        await delete_silent(ctx.message, delay=4) # deleted after 4 seconds
        await delete_silent(message, delay=6) # deleted after 6 seconds


    @highlight.command(name='remove', aliases=['-'])
    @commands.guild_only()
    async def highlight_remove(self, ctx: MyContext, *, word: commands.clean_content):
        """Remove a word from your highlight list."""
        word = word.lower()
        
        await self.bot.db.execute("DELETE FROM highlight WHERE author_id = $1 AND text = $2 AND guild_id = $3", ctx.author.id, word, ctx.guild.id)

        try:
            del self.highlight[word]
        except KeyError:
            pass
        await ctx.send(f"{self.bot.emotes['check']} Updated your highlight list.", hide=True)

    @highlight.command(name='list', aliases=['show', 'display'])
    @commands.guild_only()
    async def highlight_list(self, ctx: MyContext):
        """
        Show your highlight list.
        
        This list will be removed after 7 seconds for your privacy.
        """
        data = await self.bot.db.fetch("SELECT text FROM highlight WHERE author_id = $1 AND guild_id = $2", ctx.author.id, ctx.guild.id)
        
        if not data:
            message = await ctx.send("You do not have any highlights.", hide=True)
        else:
            embed = discord.Embed(color=discord.Color.yellow())
            embed.set_author(name=f'{ctx.author}\'s highlights', icon_url=ctx.author.display_avatar.url)
            embed.description = "\n".join([x['text'] for x in data])
            embed.set_footer(text=f'{len(data)} highlight{"s" if len(data) > 1 else ""}')
            
            message = await ctx.send(embed=embed, hide=True)

        await delete_silent(ctx.message, delay=4) # deleted after 4 seconds
        await delete_silent(message, delay=6) # deleted after 6 seconds


    @highlight.command(name='clear', aliases=['wipe'])
    @commands.guild_only()
    async def highlight_clear(self, ctx: MyContext):
        """Clear your highlights."""

        data = await self.bot.db.fetch("SELECT * FROM highlight WHERE author_id = $1 AND guild_id = $2", ctx.author.id, ctx.guild.id)
        if not data:
            message = await ctx.send(f"{self.bot.emotes['cross']} You have no highlights to clear.", hide=True)
        else:
            await self.bot.db.execute("DELETE FROM highlight WHERE author_id = $1 AND guild_id = $2", ctx.author.id, ctx.guild.id)
            await self.load_highlight() # whatever

            message = await ctx.send(f"{self.bot.emotes['check']} Cleared all your highlights.", hide=True)

        await delete_silent(ctx.message, delay=4) # deleted after 4 seconds
        await delete_silent(message, delay=6) # deleted after 6 seconds


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

        # If you wanna call this inefficient idc. it works fine for me

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
                    if str(key).lower() in final_message and message.author.id != value[1]:
                        e = await self.generate_context(message, key)
                        user = message.guild.get_member(value[1])
                        if user is not None and user in message.mentions:
                            continue
                        if user is not None and message.channel.permissions_for(user).read_messages:
                            ctx = await self.bot.get_context(message)
                            if ctx.prefix is not None:
                                continue
                            await user.send(f"In {message.channel.mention}, you were mentioned with the highlighted word \"{key}\"", embed=e)
            except RuntimeError:
                pass # Can't do shit really 
  
async def setup(bot):
    await bot.add_cog(utility(bot))