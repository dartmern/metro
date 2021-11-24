
import discord
from discord.ext import commands, menus

from typing import Optional, Union

from utils.calc_tils import NumericStringParser
from utils.checks import check_dev
from utils.json_loader import read_json
from utils.custom_context import MyContext
from utils.useful import Cooldown, Embed, get_bot_uptime
from utils.useful import Embed
from utils.new_pages import SimplePages

import asyncio
import time
import os
import asyncpg
import yarl
from pathlib import Path
import inspect
import unicodedata

class GithubError(commands.CommandError):
    pass

info_file = read_json('info')
github_token = info_file["github_token"]

class TodoListSource(menus.ListPageSource):
    def __init__(self, entries, ctx : MyContext):
        super().__init__(entries, per_page=8)
        self.ctx = ctx

    async def format_page(self, menu, entries):
        maximum = self.get_max_pages()

        embed = Embed()
        embed.set_author(name=self.ctx.author, icon_url=self.ctx.author.avatar.url)

        todo_list = []
        
        for page in [
            f'**[{i + 1}]({entries[i]["jump_url"]} \"Jump to message\").** {entries[i]["text"]}'
            for i in range(len(entries))]:
            todo_list.append(page[0:4098])

        embed.description = '\n'.join(todo_list)
        return embed


def get_path():
    """
    A function to get the current path to bot.py
    Returns:
     - cwd (string) : Path to bot.py directory
    """
    cwd = Path(__file__).parents[1]
    cwd = str(cwd)
    return cwd


def chunkIt(seq, num):
    avg = len(seq) / float(num)
    out = []
    last = 0.0

    while last < len(seq):
        out.append(seq[int(last):int(last + avg)])
        last += avg

    return out


class Source(menus.ListPageSource):
    def __init__(self, entries):
        super().__init__(entries=entries, per_page=4)

    async def format_page(self, menu, entries):
        
        maximum = self.get_max_pages()
        embed=discord.Embed()
        embed.description='\n'.join(f"{i}\n**ID:** {i.id}\n**GUILD:** {i.guild}" for i in entries)

        embed.set_footer(text=f'[{menu.current_page + 1}/{maximum}]')
        return embed
        

class utility(commands.Cog, description=":information_source: Get utilities like prefixes, serverinfo, source, etc."):
    def __init__(self, bot):
        self.bot = bot
        self._req_lock = asyncio.Lock(loop=self.bot.loop)

    async def say_permissions(self, ctx, member, channel):
        permissions = channel.permissions_for(member)
        e = discord.Embed(colour=member.colour)
        avatar = member.avatar.url

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


    @commands.command(aliases=['ui','whois','info'])
    @commands.bot_has_permissions(send_messages=True)
    async def userinfo(self, ctx, member : Union[discord.Member, discord.User, None]):
        """
        Shows all the information about the specified user.
        If user isn't specified, it defaults to the author.
        """

        if isinstance(member, discord.User):

            member = member or ctx.author   

            embed = discord.Embed(
                description=member.mention,
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(
                name='Joined at',
                value='N/A',
                inline=True
            )
            embed.add_field(
                name='Created at',
                value=f"{discord.utils.format_dt(member.created_at)}\n({discord.utils.format_dt(member.created_at, 'R')})",
                inline=False
            )
            embed.set_thumbnail(url=member.avatar.url)
            embed.set_author(name=member, icon_url=member.avatar.url)
            embed.set_footer(text=f'User ID: {member.id}')

            return await ctx.send(embed=embed)



        member = member or ctx.author

        embed = discord.Embed(
            description=member.mention,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(
            name="Joined at",
            value=f"{discord.utils.format_dt(member.joined_at)}\n({discord.utils.format_dt(member.joined_at, 'R')})",
            inline=True
        )
        embed.add_field(
            name="Created at",
            value=f"{discord.utils.format_dt(member.created_at)}\n({discord.utils.format_dt(member.created_at, 'R')})",
            inline=True

        )
        embed.set_thumbnail(url=member.avatar.url)
        embed.set_author(name=member, icon_url=member.avatar.url)
        embed.set_footer(text=f'User ID: {member.id}')

        roles = member.roles[1:30]

        if roles:
            embed.add_field(
                name=f"Roles [{len(member.roles) - 1}]",
                value=" ".join(f"{role.mention}" for role in roles),
                inline=False,
            )
        else:
            embed.add_field(
                name=f"Roles [{len(member.roles) - 1}]",
                value="This member has no roles",
                inline=False,
            )

        await ctx.send(embed=embed)


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

    @commands.command()
    async def prefixes(self, ctx):
        """Alias for `prefix list` (list all my prefixes)"""
        await ctx.invoke(self.prefix_list)

        
    def read_tags(self, ctx : MyContext):
        DPY_GUILD = ctx.bot.get_guild(336642139381301249)

        ids = []
        tags = []

        for member in DPY_GUILD.humans:
            ids.append(member.id)
        
        cwd = get_path()
        with open(cwd+'/config/'+'tags.txt', 'r', encoding='utf8') as file:
            for line in file.read().split("\n"):
    
                id = line[-51:]
                id = id[:18]

                try:
                    if int(id) not in ids:
                        tag = line[10:112]
                        tag = tag.strip()
                        tags.append(str(tag))
                except:
                    pass
        
        return tags


    @commands.command(hidden=True)
    @commands.is_owner()  
    @commands.bot_has_permissions(send_messages=True)  
    async def tags(self, ctx : MyContext, per_page : int = 10):
        await ctx.check()
        result = await self.bot.loop.run_in_executor(None, self.read_tags, ctx)
        await ctx.paginate(result, per_page=per_page)
        

    @commands.command(aliases=['sourcecode', 'code'],
                      )
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def source(self, ctx, command: str = None, *, args : str = None):
        """
        Links to the bot's source code, or a specific command's
        """
        if check_dev(self.bot, ctx.author):
            pass
        else:
            return await ctx.send(
                f"I am close sourced."
            )
        
        if args is None:

            source_url = 'https://github.com/dartmern/metro'
            branch = 'master'

            if command is None:
                embed = Embed(description=f"Take the [**entire reposoitory**]({source_url})")
                embed.set_footer(text='Please make sure you follow the license.')
                return await ctx.send(embed=embed)

            if command == 'help':
                src = type(self.bot.help_command)
                module = src.__module__
                filename = inspect.getsourcefile(src)
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
            if not module.startswith('discord'):
                # not a built-in command
                location = os.path.relpath(filename).replace('\\', '/')
            else:
                location = module.replace('.', '/') + '.py'
                source_url = 'https://github.com/Rapptz/discord.py'
                branch = 'master'

            final_url = f'<{source_url}/blob/{branch}/{location}#L{firstlineno}-L{firstlineno + len(lines) - 1}>'
            embed = Embed(color=ctx.me.color,
                                description=f"Source code for [`{obj.qualified_name}`]({final_url})")
            embed.set_footer(text='Please make sure you follow the license.')
            await ctx.send(embed=embed)

        else:
            parser = inspect.Arguments


    @commands.command(slash_command=True)
    @commands.bot_has_permissions(send_messages=True)
    async def uptime(self, ctx):
        """Get the bot's uptime."""

        await ctx.send(f'I have an uptime of: **{get_bot_uptime(self.bot, brief=False)}**',hide=True)


    @commands.command(aliases=['lc'])
    @commands.bot_has_permissions(send_messages=True)
    async def linecount(self, ctx):
        """
        Get the linecount + code stats for Metro.
        """

        import pathlib

        p = pathlib.Path('./')
        cm = cr = fn = cl = ls = fc = 0
        for f in p.rglob('*.py'):
            if str(f).startswith("venv"):
                continue
            fc += 1
            with f.open(encoding='utf8',errors='ignore') as of:
                for l in of.readlines():
                    l = l.strip()
                    if l.startswith('class'):
                        cl += 1
                    if l.startswith('def'):
                        fn += 1
                    if l.startswith('async def'):
                        cr += 1
                    if '#' in l:
                        cm += 1
                    ls += 1

        await ctx.send(f"Files: {fc}\nLines: {ls:,}\nClasses: {cl}\nFunctions: {fn}\nCoroutines: {cr}\nComments: {cm:,}")


    @commands.command()
    async def ping(self, ctx):
        """Show the bot's latency in milliseconds.
        Useful to see if the bot is lagging out."""

        start = time.perf_counter()
        message = await ctx.send('Pinging...')
        end = time.perf_counter()

        typing_ping = (end - start) * 1000

        start = time.perf_counter()
        await self.bot.db.execute('SELECT 1')
        end = time.perf_counter()

        database_ping = (end - start) * 1000

        typing_emoji = self.bot.get_emoji(904156199967158293)

        if ctx.guild is None:
            mess = "`Note that my messages are on shard 0 so it isn't guaranteed your server is online.`" 
            shard = self.bot.get_shard(0)
        else:
            mess = ""
            shard = self.bot.get_shard(ctx.guild.shard_id)

        await message.edit(
            content=f'{typing_emoji} **Typing:** | {round(typing_ping, 1)} ms'
                    f'\n<:msql:904157158608867409> **Database:** | {round(database_ping, 1)} ms'
                    f'\n<:mdiscord:904157585266049104> **Websocket:** | {round(self.bot.latency*1000)} ms'
                    f'\n:infinity: **Shard Latency:** | {round(shard.latency *1000)} ms \n{mess}')



    @commands.command(aliases=['calc'])
    async def calculate(self, ctx, *, formula : str):
        """
        Calculate an equation.

        **Keys:**
            exponentiation: `^`
            multiplication: `x` | `*`
            division: `/`
            addition: `+` | `-`
            integer: `+` | `-` `0 .. 9+`
            constants: `PI` | `E`

        **Functions:**
            sqrt, log, sin, cos, tan, arcsin, arccos,
            arctan, sinh, cosh, tanh, arcsinh, arccosh,
            arctanh, abs, trunc, round, sgn
        """

        formula = formula.replace('*','x')
        try:
            start = time.perf_counter()
            answer = NumericStringParser().eval(formula)
            end = time.perf_counter()
            await ctx.check()
        except Exception as e:
            return await ctx.send(str(e))

        if int(answer) == answer:
            answer = int(answer)

        ping = (end - start) * 1000

        embed = Embed()
        embed.description = f'Input: `{formula}`\nOutput: `{answer}`'
        embed.set_footer(text=f'Calculated in {round(ping, 1)}ms')
        await ctx.send(embed=embed)


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

            embed = Embed()
            embed.colour = discord.Colour.red()
            embed.description = (':warning: **That item is already in your todo list:**'
            f'\n\u200b\u200b\u200b   → [added here]({data["jump_url"]}) ←'
            
            )
            return await ctx.send(embed=embed, hide=True)

        else:

            await ctx.send(
            '**Added to todo list:**'
            f'\n\u200b  → {item[0:200]}{"..." if len(item) > 200 else ""}', hide=True
            )


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
            embed = Embed()
            embed.colour = discord.Colour.red()
            embed.description = (f":warning: **You do not have a task with the index:** `{index}`"
            f"\n\n\u200b  → use `{ctx.prefix}todo list` to check your todo list"
            )
            return await ctx.send(embed=embed, hide=True)

        await self.bot.db.execute("DELETE FROM todo WHERE (user_id, text) = ($1, $2)", ctx.author.id, to_del['text'])
        return await ctx.send(
            f'**Deleted task {index}**!'
            f'\n\u200b  → {to_del["text"][0:1900]}{"..." if len(to_del["text"]) > 1900 else ""}', hide=True
        )
        

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
        return await ctx.send(
            f'{self.bot.check} **|** Removed **{count}** entries.', hide=True
        )

    @todo.command(
        name='list',
        slash_command=True
    )
    async def todo_list(self, ctx : MyContext):
        """Show your todo list."""

        data = await self.bot.db.fetch(
            "SELECT text, added_time, jump_url FROM todo WHERE user_id = $1 ORDER BY added_time ASC", ctx.author.id
        )
        if not data:
            embed = Embed()
            embed.color = discord.Colour.red()
            embed.description = (":warning: **Your todo-list is empty**"
                f"\n\n\u200b  → use `{ctx.prefix}todo add <item>` to add to your todo list"
            )
            return await ctx.send(embed=embed)

        menu = SimplePages(source=TodoListSource(entries=data, ctx=ctx), ctx=ctx, hide=True)
        await menu.start()
        


        



def setup(bot):
    bot.add_cog(utility(bot))



















