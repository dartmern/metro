import discord
from discord import message
from discord.ext import commands, menus

from utils.custom_context import MyContext
from utils.useful import Embed
from utils.new_pages import SimplePages
from utils.json_loader import read_json

import yarl
import asyncio

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


class lists(commands.Cog, description=':notepad_spiral: Manage and create notes and todo lists.'):

    def __init__(self, bot):
        self.bot = bot
        self._req_lock = asyncio.Lock(loop=self.bot.loop)

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

    @commands.command()
    @commands.cooldown(1, 30, commands.cooldowns.BucketType.user)
    async def gist(self, ctx : MyContext, *, content : str):
        """Create and post a gist online."""

        link = await self.create_gist(content=content)
        await ctx.send(f"Created new gist.\n<{link}>")

    @commands.command(aliases=['mtl'])
    async def metrotodolist(self, ctx : MyContext):
        """View my developer's todo list and upcoming updates."""

        query = """
                SELECT text, added_time, jump_url FROM todo WHERE user_id = $1 ORDER BY added_time ASC
                """

        data = await self.bot.db.fetch(query, 525843819850104842)
        if not data:
            return await ctx.send(
                f"My developer's todo list is empty."
            )

        menu = SimplePages(TodoListSource(entries=data, ctx=ctx), ctx=ctx)
        await menu.start()
        





def setup(bot):
    bot.add_cog(lists(bot))