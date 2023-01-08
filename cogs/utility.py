import discord
from discord.ext import commands, menus
from discord import app_commands

from typing import List, Optional, Union
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
import logging
import re
import traceback

from bot import MetroBot
from utils.pages import StopView
from utils.embeds import create_embed
from utils.json_loader import read_json
from utils.custom_context import MyContext
from utils.remind_utils import human_timedelta
from utils.useful import Embed, dynamic_cooldown
from utils.useful import Embed
from utils.pages import SimplePages
from utils.remind_utils import UserFriendlyTime

class UserSelect(discord.ui.UserSelect):
    def __init__(self) -> None:
        super().__init__(
            min_values=1, max_values=25, 
            placeholder='Select the users you want to block.')

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

class ChannelSelect(discord.ui.ChannelSelect):
    def __init__(self) -> None:
        super().__init__(
            min_values=1, max_values=25, 
            placeholder='Select the channels you want to block.', 
            channel_types=[discord.ChannelType.text, discord.ChannelType.public_thread, discord.ChannelType.voice])

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

class UnignoreSelect(discord.ui.Select):
    def __init__(self, *, options: List[discord.SelectOption], ctx: MyContext) -> None:
        super().__init__(options=options, max_values=len(options))
        self.ctx = ctx
        self.bot: MetroBot = ctx.bot

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

        to_join: list[Union[discord.TextChannel, discord.User]] = []
        for item in self.values:   
            await self.bot.db.execute('DELETE FROM highlight_ignored WHERE (user_id, guild_id, entity_id) = ($1, $2, $3)',
            self.ctx.author.id, self.ctx.guild.id, int(item))
        
            object = self.bot.get_channel(int(item)) or self.bot.get_user(int(item))
            to_join.append(object)
       
        ops = ', '.join(map(lambda x: x.mention, to_join))
        em = create_embed(f'{self.bot._check} Removed {ops} from your ignored list.', color=discord.Color.green())
        await interaction.edit_original_response(embed=em, view=None)

class HighlightUnIgnoreView(discord.ui.View):
    def __init__(self, ctx: MyContext):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.bot: MetroBot = ctx.bot
        self.message: discord.Message

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

        await self.message.edit(view=self)

    def embed(self):
        return create_embed(
            'Select the **users/channels** you want to unignore.', 
            color=discord.Color.red())

    def get_channel_or_member(
        self, 
        object: int, *, ctx: MyContext) -> Union[discord.TextChannel, discord.VoiceChannel, discord.User, discord.Member]:
        """Get a channel or member."""

        to_return = self.bot.get_channel(object) or self.bot.get_user(object) or ctx.guild.get_member(object)
        return to_return

    async def start(self):
        rows = await self.bot.db.fetch('SELECT entity_id FROM highlight_ignored WHERE user_id = $1 AND guild_id = $2',
        self.ctx.author.id, self.ctx.guild.id)

        if not rows:
            await self.ctx.send('You have no ignored entities that you have blocked.', hide=True)
            return 

        options = []
        for row in rows:
            object = self.get_channel_or_member(row['entity_id'], ctx=self.ctx)
            smb = '@' if isinstance(object, (discord.User, discord.Member, discord.ClientUser)) else '#'
            label = f'{smb}{str(object)}'
            options.append(discord.SelectOption(label=label, value=row['entity_id']))
        
        select = UnignoreSelect(options=options, ctx=self.ctx)
        self.add_item(select)

        self.message = await self.ctx.send(embed=self.embed(), view=self)

class HighlightIgnoreUnignoreView(discord.ui.View):
    def __init__(self, ctx: MyContext):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.bot: MetroBot = ctx.bot
        self.message: discord.Message

        self.user_select = UserSelect()
        self.channel_select = ChannelSelect()
        self.add_item(self.user_select)
        self.add_item(self.channel_select)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

        await self.message.edit(content='Canceled due to timeout. Run the command again.', view=None, embed=None)  

    def embed(self):
        """Generate the embed for starter message."""
        return create_embed(
            'Select the **users/channels** you want to block then click **Confirm**', 
            color=discord.Color.green())

    async def interaction_check(self, interaction: discord.Interaction):
        if self.ctx.author.id == interaction.user.id:
            return True
        else:
            await interaction.response.send_message(
                "Only the command invoker can use this button.", ephemeral=True
            )

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Confirm the selected items."""

        await interaction.response.defer()

        blocked = self.user_select.values + self.channel_select.values
        for user in blocked:
            # for ux reasons I feel like this is the best option
            # to do this task and is better to take this inefficiency

            returned = await self.bot.db.fetchval(
                'SELECT 1 FROM highlight_ignored WHERE user_id = $1 AND guild_id = $2 AND entity_id = $3',
                interaction.user.id, interaction.guild_id, user.id)
            
            if returned:
                blocked.remove(user)
                continue

            try:
                await self.bot.db.execute(
                    'INSERT INTO highlight_ignored (user_id, guild_id, entity_id) VALUES ($1, $2, $3)',
                    interaction.user.id, interaction.guild_id, user.id)
            except Exception as e:
                traceback.print_exception(e)
                logging.error('Error in highlight ignore unignore view.')
                return 

        joined = '\n'.join(map(lambda x: x.mention, blocked))
        if not joined:
            await interaction.followup.send('Select some users/channels before confirming.', ephemeral=True)
            return 

        em = discord.Embed(color=discord.Color.green())
        em.add_field(name='Added to your block list.', value=joined)

        response = await interaction.original_response()
        await response.edit(embed=em, view=None)
        if not self.ctx.interaction:
            try:
                await response.delete(delay=8)
            except discord.HTTPException:
                pass

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the ignore request."""

        await interaction.response.defer()
        await interaction.edit_original_response(content='Canceled.', embed=None, view=None)

class AddPrefixModal(discord.ui.Modal):
    def __init__(self, ctx: MyContext):
        super().__init__(title='Add a prefix.')
        self.ctx = ctx
        self.bot: MetroBot = ctx.bot

    prefix = discord.ui.TextInput(label='Prefix', max_length=10, min_length=1)

    async def on_submit(self, interaction: discord.Interaction):
        query = "INSERT INTO prefixes (guild_id, prefix) VALUES ($1, $2)"

        try:
            await self.bot.db.execute(query, self.ctx.guild.id, self.prefix.value)
            self.bot.prefixes[self.ctx.guild.id] = await self.bot.fetch_prefixes(self.ctx.guild.id)

            prefixes = ['`%s`' % prefix for prefix in self.bot.prefixes[self.ctx.guild.id]] if not None else self.bot.PRE
            embed = create_embed(f'Your current prefixes: {", ".join(prefixes)}', title='Prefix Configuration')

            await interaction.message.edit(embed=embed)
            await interaction.response.send_message(f'{self.bot._check} **|** Added `{self.prefix.value}` to the guild\'s prefixes.', ephemeral=True)
        except asyncpg.exceptions.UniqueViolationError:
            await interaction.response.send_message(f'{self.bot.cross} **|** That is already a prefix in this guild.', ephemeral=True)

class RemovePrefixSelect(discord.ui.Select):
    def __init__(self, ctx: MyContext, *, options: List[discord.SelectOption], message: discord.Message) -> None:
        super().__init__(options=options, max_values=len(options) - 1)
        self.ctx = ctx
        self.bot: MetroBot = ctx.bot
        self.message = message

    async def callback(self, interaction: discord.Interaction):
        
        old = list(await self.bot.fetch_prefixes(self.ctx.guild.id))
        new = [x for x in old if x not in self.values]

        for prefix in self.values:
            query = "DELETE FROM prefixes WHERE (guild_id, prefix) = ($1, $2)"
            await self.bot.db.execute(query, self.ctx.guild.id, prefix)
        self.bot.prefixes[self.ctx.guild.id] = new

        prefixes = ['`%s`' % prefix for prefix in self.bot.prefixes[self.ctx.guild.id]] if not None else self.bot.PRE
        embed = create_embed(f'Your current prefixes: {", ".join(prefixes)}', title='Prefix Configuration')

        removed = ['`%s`' % prefix for prefix in self.values]
        await self.message.edit(embed=embed)
        await interaction.response.send_message(f'{self.bot._check} **|** Removed {", ".join(removed)} from my prefixes.', ephemeral=True)


class RemovePrefixView(discord.ui.View):
    def __init__(self, ctx: MyContext, *, options: List[discord.SelectOption], message: discord.Message):
        super().__init__(timeout=300)

        self.add_item(RemovePrefixSelect(ctx, options=options, message=message))

class PrefixView(discord.ui.View):
    def __init__(self, ctx: MyContext):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.bot: MetroBot = ctx.bot
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction):
        if self.ctx.author.id == interaction.user.id:
            return True
        else:
            await interaction.response.send_message(
                "Only the command invoker can use this button.", ephemeral=True
            )

    @discord.ui.button(
        label='Add prefix', 
        style=discord.ButtonStyle.green, 
        emoji='<:mplus:904450883633426553>')
    async def add_prefix_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Add a prefix prompt."""

        await interaction.response.send_modal(AddPrefixModal(self.ctx))

    @discord.ui.button(
        label='Remove prefix',
        style=discord.ButtonStyle.red,
        emoji='<:mminus:904450883587276870>')
    async def remove_prefix(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Remove a prefix prompt."""

        options = [discord.SelectOption(label=prefix) for prefix in self.bot.prefixes[self.ctx.guild.id]]
        embed = create_embed('Select the prefixes that you want to remove.', color=discord.Color.red())
        await interaction.response.send_message(
            embed=embed, 
            view=RemovePrefixView(self.ctx, options=options, message=self.message), 
            ephemeral=True)

    @discord.ui.button(
        label='Clear prefixes',
        style=discord.ButtonStyle.blurple,
        emoji='<:slash:819254444445270056>')
    async def clear_prefixes(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Clear prefixes prompt."""

        confirm = await self.ctx.confirm(
            'Are you sure you want to clear the prefixes?', 
            interaction=interaction)
        if not confirm.value:
            return

        await self.bot.db.execute('DELETE FROM prefixes WHERE guild_id = $1', self.ctx.guild.id)
        self.bot.prefixes[self.ctx.guild.id] = self.bot.PRE
        
        prefixes = ['`%s`' % prefix for prefix in self.bot.prefixes[self.ctx.guild.id]] if not None else self.bot.PRE
        embed = create_embed(f'Your current prefixes: {", ".join(prefixes)}', title='Prefix Configuration')

        await self.message.edit(embed=embed)
        await confirm.message.edit(content=f'{self.bot._check} **|** Reset all my prefixes!', view=None)
    

class SourceView(discord.ui.View):
    def __init__(self, ctx : MyContext, code : str):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.code = code
        self.url: str = None

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
            await interaction.followup.send(file=file, view=StopView(self.ctx), ephemeral=True)
        else:
            await interaction.response.send_message(f"```py\n{self.code}\n```", view=StopView(self.ctx), ephemeral=True)

    @discord.ui.button(label='Post Source', emoji='\U0001f587', style=discord.ButtonStyle.blurple)
    async def bar(self, interaction : discord.Interaction, button : discord.ui.Button):

        await interaction.response.defer()
        
        if not self.url:
            paste = await self.ctx.bot.mystbin_client.create_paste(content=self.code, filename='code.py')
            self.url = f'https://mystb.in/{paste.id}'
        await interaction.followup.send(f"Output: {self.url}", view=StopView(self.ctx))

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
        embed.set_author(name=self.ctx.author, icon_url=self.ctx.author.display_avatar.url)

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

        self.highlight_cache: dict[tuple[int, int], list[str]] = {}

        self.regex_pattern = re.compile('([^\s\w]|_)+')
        self.website_regex = re.compile("https?:\/\/[^\s]*")

        self.last_seen = {}


    def cog_unload(self):
        self._task.cancel()

    @property
    def emoji(self) -> str:
        return 'ℹ️'

    async def from_permission(self, permission : int) -> CustomPermissions:

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

    async def post_mystbin(self, content: str, *, name: str = None):
        paste = await self.bot.mystbin_client.create_paste(filename='paste', content=content)
        
        return f"https://mystb.in/{paste.id}"

    @commands.command(name='mystbin', aliases=['paste'])
    @commands.dynamic_cooldown(dynamic_cooldown, type=commands.BucketType.user)
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

    @commands.hybrid_command()
    @commands.has_permissions(manage_guild=True)
    async def prefix(self, ctx: MyContext):
        """Manage custom prefixes."""

        prefixes = ['`%s`' % prefix for prefix in self.bot.prefixes[ctx.guild.id]] if not None else self.bot.PRE
        embed = create_embed(f'Your current prefixes: {", ".join(prefixes)}', title='Prefix Configuration')
        
        view = PrefixView(ctx)
        view.message = await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(aliases=['sourcecode', 'code', 'src'])
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    @app_commands.describe(command='The command\'s source you want to view.')
    async def source(self, ctx: MyContext, *, command: str = None):
        """
        Links to the bot's source code, or a specific command's
        """
        
        source_url = 'https://github.com/dartmern/metro/'
        license_url = source_url + 'blob/master/LICENSE'
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

    @source.autocomplete('command')
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
            timeout=30,
            interaction=ctx.interaction if ctx.interaction else None)

        if not confirm.value:
            return

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

        if not confirm.value:
            await confirm.message.delete()
            return

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
    @commands.dynamic_cooldown(dynamic_cooldown, type=commands.BucketType.user)
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
    @commands.dynamic_cooldown(dynamic_cooldown, type=commands.BucketType.user)
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

    @commands.hybrid_group(name='highlight', invoke_without_command=True, case_insensitive=True, aliases=['hl'], fallback='help')
    @commands.guild_only()
    async def highlight(self, ctx: MyContext):
        """Highlight word notifications."""
        await ctx.help()

    @highlight.command(name='add', aliases=['+'])
    @app_commands.describe(word='The word you want added to your highlights.')
    @commands.guild_only()
    async def highlight_add(self, ctx: MyContext, *, word: commands.Range[str, 2]):
        """Add a word to your highlight list."""
        
        
        word = await commands.clean_content().convert(ctx, word.lower()) # remove the pain in the ass of highlight

        if len(word) < 2:
            return await ctx.send("Word needs to be at least 2 characters long.", hide=True, delete_after=6)
        if len(word) > 50:
            return await ctx.send("Word needs to be less than 50 characters long.", hide=True, delete_after=6)
        
        data = await self.bot.db.fetchval("SELECT highlight FROM highlight WHERE author_id = $1 AND guild_id = $2 AND text = $3", ctx.author.id, ctx.guild.id, word)
        if not data:  
            await self.bot.db.execute("INSERT INTO highlight (author_id, text, guild_id) VALUES ($1, $2, $3)", ctx.author.id, word, ctx.guild.id)
            if self.highlight_cache.get((ctx.guild.id, ctx.author.id)):
                self.highlight_cache[(ctx.guild.id, ctx.author.id)].append(word)
            else:
                self.highlight_cache[(ctx.guild.id, ctx.author.id)] = [word]

        await ctx.send(f"{self.bot.emotes['check']} Updated your highlight list.", hide=True, delete_after=6)
        try:
            await ctx.message.delete(delay=4)
        except discord.HTTPException:
            pass

    @highlight.command(name='remove', aliases=['-'])
    @app_commands.describe(word='The word you want to remove.')
    @commands.guild_only()
    async def highlight_remove(self, ctx: MyContext, *, word: str):
        """Remove a word from your highlight list."""

        word = word.lower()
        
        await self.bot.db.execute("DELETE FROM highlight WHERE author_id = $1 AND text = $2 AND guild_id = $3", ctx.author.id, word, ctx.guild.id)

        try:
            self.highlight_cache[(ctx.guild.id, ctx.author.id)].remove(word)
        except KeyError:
            pass
        await ctx.send(f"{self.bot.emotes['check']} Updated your highlight list.", hide=True, delete_after=6)

        try:
            await ctx.message.delete(delay=4)
        except discord.HTTPException:
            pass

    @highlight_remove.autocomplete('word')
    async def highlight_remove_word_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:

        data = await self.bot.db.fetch("SELECT text FROM highlight WHERE author_id = $1 AND guild_id = $2", interaction.user.id, interaction.guild_id)
        return [
            app_commands.Choice(name=item, value=item)
            for item in [x['text'] for x in data] if current.lower() in item.lower()
        ]

    @highlight.command(name='list', aliases=['show', 'display'])
    @commands.guild_only()
    async def highlight_list(self, ctx: MyContext):
        """Show your highlight list."""
        
        data = await self.bot.db.fetch("SELECT text FROM highlight WHERE author_id = $1 AND guild_id = $2", ctx.author.id, ctx.guild.id)
        
        if not data:
            await ctx.send("You do not have any highlights.", hide=True, delete_after=6)
        else:
            embed = discord.Embed(color=discord.Color.yellow())
            embed.set_author(name=f'{ctx.author}\'s highlights', icon_url=ctx.author.display_avatar.url)
            embed.description = "\n".join([x['text'] for x in data])
            embed.set_footer(text=f'{len(data)} highlight{"s" if len(data) > 1 else ""}')
            
            await ctx.send(embed=embed, hide=True, delete_after=6)

        try:
            await ctx.message.delete(delay=4)
        except discord.HTTPException:
            pass

    @highlight.command(name='clear', aliases=['wipe'])
    @commands.guild_only()
    async def highlight_clear(self, ctx: MyContext):
        """Clear your highlights."""
        
        data = await self.bot.db.fetch("SELECT * FROM highlight WHERE author_id = $1 AND guild_id = $2", ctx.author.id, ctx.guild.id)
        if not data:
            await ctx.send(f"{self.bot.emotes['cross']} You have no highlights to clear.", hide=True, delete_after=6)
            return await ctx.message.delete(delay=4)

        confirm = await ctx.confirm('Are you sure you want to clear your highlights?', interaction=ctx.interaction if ctx.interaction else None, delete_after=False)
        if confirm.value is False:
            await confirm.message.edit(content='Canceled.', view=None, delete_after=6)
        elif confirm.value is None:
            await confirm.message.edit(content='Timed out.', view=None, delete_after=6)
        else:
            await self.bot.db.execute("DELETE FROM highlight WHERE author_id = $1 AND guild_id = $2", ctx.author.id, ctx.guild.id)
            self.highlight_cache.pop((ctx.guild.id, ctx.author.id), None)
                
            await confirm.message.edit(content=f"{self.bot.emotes['check']} Cleared all your highlights.", delete_after=6, view=None)   
            
        try:
            await ctx.message.delete(delay=4)
        except discord.HTTPException:
            pass

    @highlight.group(name='ignore', aliases=['block'], fallback='add')
    @commands.guild_only()
    async def highlight_ignore(self, ctx: MyContext):
        """Ignore and entity from highlighting you."""

        view = HighlightIgnoreUnignoreView(ctx)
        em = view.embed()
        view.message = await ctx.send(embed=em, view=view, hide=True)

    @highlight_ignore.command(name='list', aliases=['show'])
    @commands.guild_only()
    async def highlight_ignore_list(self, ctx: MyContext):
        """List the entities you have on your highlight ignore list."""

        rows = await self.bot.db.fetch('SELECT entity_id FROM highlight_ignored WHERE user_id = $1 AND guild_id = $2',
        ctx.author.id, ctx.guild.id)
        if not rows:
            await ctx.send('You have no ignored entities that you have blocked.', hide=True)
            return 

        to_paginate = []
        for row in rows:
            entity = self.bot.get_channel(row['entity_id'])
            if not entity:
                entity = ctx.guild.get_member(row['entity_id'])
            if not entity:
                # still not valid so doesn't exist i guess
                continue
            to_paginate.append(entity.mention)

        await ctx.paginate(to_paginate, compact=True, delete_after=8)

    @highlight_ignore.command(name='remove')
    @commands.guild_only()
    async def highlight_ignore_remove(self, ctx: MyContext):
        """Remove an entity from your highlight ignore list."""

        view = HighlightUnIgnoreView(ctx)
        await view.start()

    async def generate_context(self, msg: discord.Message, hl: str) -> discord.Embed:
        fmt = []
        async for m in msg.channel.history(limit=5):
            time_fmt = discord.utils.format_dt(m.created_at, style='t')
            fmt.append(f"**[{time_fmt}] {m.author.name}:** {m.content[:100]}")
        e = discord.Embed(title=f"**{hl}**", description='\n'.join(fmt[::-1]))
        return e

    @commands.Cog.listener("on_message")
    async def highlight_core(self, message: discord.Message):
        """The core of highlight."""
        self.last_seen[message.author.id] = discord.utils.utcnow()
        
        if message.guild is None:
            return
        if message.author.bot:
            return

        final_message = self.website_regex.sub('', message.content.lower())
        final_message = self.regex_pattern.sub('', final_message)
        
        if self.highlight_cache:
            try:
                for key, value in self.highlight_cache.items(): 
                    #local_last_seen = self.last_seen.get(int(value[1]))
                    #if not local_last_seen or ((discord.utils.utcnow() - local_last_seen).total_seconds() < 300):
                        #continue
                    if message.guild.id != key[0]:
                        continue
                    for word in value:
                        if str(word).lower() in final_message and message.author.id != key[1]:

                            check = await self.bot.db.fetchval('SELECT 1 FROM highlight_ignored WHERE user_id = $1 AND guild_id = $2 AND entity_id = $3',
                            key[1], message.guild.id, message.author.id)
                            if check:
                                continue # ignore list

                            embed = await self.generate_context(message, word)

                            view = discord.ui.View()
                            view.add_item(discord.ui.Button(label='Jump to message', url=message.jump_url))
                            
                            user = message.guild.get_member(key[1])
                            if user is not None and user in message.mentions:
                                continue

                            if user is not None and message.channel.permissions_for(user).read_messages:
                                ctx = await self.bot.get_context(message)
                                if ctx.prefix is not None:
                                    continue

                                await user.send(
                                    f"In {message.channel.mention}, you were mentioned with the highlighted word \"{word}\"", 
                                    embed=embed, view=view)
                                break
                        continue

            except RuntimeError:
                pass # Can't do shit really 

async def setup(bot: MetroBot):
    await bot.add_cog(utility(bot))