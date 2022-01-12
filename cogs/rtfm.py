from typing import Dict, Literal, Optional
import discord
from discord.ext import commands
from bot import MetroBot

from utils.useful import Cooldown, Embed, fuzzy

import io
import re
import os
import zlib
import yarl

from utils.custom_context import MyContext
from utils.json_loader import read_json

data = read_json('info')
id_token = data['id_token']

# Parts of rtfs code is from BOB
# https://github.com/IAmTomahawkx/bob/blob/7f97c7b5d502cbb476f838c1ca9fb46cc46c4b03/extensions/idevision.py

# Most of rtfm code is from R. Danny
# https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/api.py#L308-L316


class LibraryConverter(commands.Converter):
    async def convert(self, _, param):
        if param.lower() in ("edpy", "enhanced-discord.py"):
            return "enhanced-discord.py"
        if param.lower() in ("dpy", "discordpy", "discord.py"):
            return "discord.py"
        elif param.lower() in ("dpy2", "discord.py2", "discordpy2"):
            return "discord.py-2"
        elif param.lower() in ("tio", "twitch", "twitchio"):
            return "twitchio"
        elif param.lower() in ("wl", "wave", "link", "wavelink"):
            return "wavelink"
        elif param.lower() in ("ahttp", "aiohttp"):
            return "aiohttp"
        else:
            raise commands.UserInputError("Must be one of `enhanced-discord.py`, `discord.py`, `discord.py-2.0`, `twitchio`, `wavelink`, or `aiohttp`")

class RTFMConverter(commands.Converter):
    async def convert(self, _, param):
        if param.lower() in ("edpy", "enhanced-discord.py"):
            return "enhanced-discord.py"
        if param.lower() in ("dpy", "discordpy", "discord.py"):
            return "discord.py"
        elif param.lower() in ("dpy2", "discord.py2", "discordpy2"):
            return "discord.py-2.0"
        elif param.lower() in ("ahttp", "aiohttp"):
            return "aiohttp"
        elif param.lower() in ("python", "py", "python.org"):
            return "python"
        elif param.lower() in ("aiohttp", "ahttp"):
            return "aiohttp"
        else:
            return None


class SphinxObjectFileReader:
    # Inspired by Sphinx's InventoryFileReader
    BUFSIZE = 16 * 1024

    def __init__(self, buffer):
        self.stream = io.BytesIO(buffer)

    def readline(self):
        return self.stream.readline().decode('utf-8')

    def skipline(self):
        self.stream.readline()

    def read_compressed_chunks(self):
        decompressor = zlib.decompressobj()
        while True:
            chunk = self.stream.read(self.BUFSIZE)
            if len(chunk) == 0:
                break
            yield decompressor.decompress(chunk)
        yield decompressor.flush()

    def read_compressed_lines(self):
        buf = b''
        for chunk in self.read_compressed_chunks():
            buf += chunk
            pos = buf.find(b'\n')
            while pos != -1:
                yield buf[:pos].decode('utf-8')
                buf = buf[pos + 1:]
                pos = buf.find(b'\n')


class docs(commands.Cog, description="Fuzzy search through documentations."):
    def __init__(self, bot : MetroBot):
        self.bot = bot

    @property
    def emoji(self) -> str:
        return '📚'

    def parse_object_inv(self, stream, url):
        # key: URL
        # n.b.: key doesn't have `discord` or `discord.ext.commands` namespaces
        result = {}

        # first line is version info
        inv_version = stream.readline().rstrip()

        if inv_version != '# Sphinx inventory version 2':
            raise RuntimeError('Invalid objects.inv file version.')

        # next line is "# Project: <name>"
        # then after that is "# Version: <version>"
        projname = stream.readline().rstrip()[11:]
        version = stream.readline().rstrip()[11:]

        # next line says if it's a zlib header
        line = stream.readline()
        if 'zlib' not in line:
            raise RuntimeError('Invalid objects.inv file, not z-lib compatible.')

        # This code mostly comes from the Sphinx repository.
        entry_regex = re.compile(r'(?x)(.+?)\s+(\S*:\S*)\s+(-?\d+)\s+(\S+)\s+(.*)')
        for line in stream.read_compressed_lines():
            match = entry_regex.match(line.rstrip())
            if not match:
                continue

            name, directive, prio, location, dispname = match.groups()
            domain, _, subdirective = directive.partition(':')
            if directive == 'py:module' and name in result:
                # From the Sphinx Repository:
                # due to a bug in 1.1 and below,
                # two inventory entries are created
                # for Python modules, and the first
                # one is correct
                continue

            # Most documentation pages have a label
            if directive == 'std:doc':
                subdirective = 'label'

            if location.endswith('$'):
                location = location[:-1] + name

            key = name if dispname == '-' else dispname
            prefix = f'{subdirective}:' if domain == 'std' else ''

            if projname == 'discord.py':
                key = key.replace('discord.ext.commands.', '').replace('discord.', '')

            result[f'{prefix}{key}'] = os.path.join(url, location)

        return result


    async def build_rtfm_lookup_table(self, page_types):
        cache = {}
        for key, page in page_types.items():
            sub = cache[key] = {}
            async with self.bot.session.get(page + '/objects.inv') as resp:
                if resp.status != 200:
                    raise RuntimeError('Cannot build rtfm lookup table, try again later.')

                stream = SphinxObjectFileReader(await resp.read())
                cache[key] = self.parse_object_inv(stream, page)

        self._rtfm_cache = cache


    async def do_rtfm(self, ctx : MyContext, key, obj):
        page_types = {
            'discord.py': 'https://discordpy.readthedocs.io/en/latest',
            'python': 'https://docs.python.org/3',
            'discord.py-2.0': 'https://discordpy.readthedocs.io/en/master',
            'enhanced-discord.py' : 'https://enhanced-dpy.readthedocs.io/en/latest',
            'aiohttp' : 'https://docs.aiohttp.org/en/stable/'  
        }

        if obj is None:
            await ctx.defer(ephemeral=True)
            await ctx.send(page_types[key], hide=True)
            return


        if not hasattr(self, '_rtfm_cache'):
            await ctx.defer(ephemeral=True)
            await self.build_rtfm_lookup_table(page_types)

        obj = re.sub(r'^(?:discord\.(?:ext\.)?)?(?:commands\.)?(.+)', r'\1', obj)

        if key.startswith('latest'):
            # point the abc.Messageable types properly:
            q = obj.lower()
            for name in dir(discord.abc.Messageable):
                if name[0] == '_':
                    continue
                if q == name:
                    obj = f'abc.Messageable.{name}'
                    break

        cache = list(self._rtfm_cache[key].items())

        def transform(tup):
            return tup[0]

        matches = fuzzy.finder(obj, cache, key=lambda t: t[0], lazy=False)[:8]

        e = Embed()
        if len(matches) == 0:
            return await ctx.send('No matches were found. Try again with a different keyword.')


        e.description = '\n'.join(f'[`{key}`]({url})' for key, url in matches)
        await ctx.send(embed=e, hide=True)


    @commands.group(name="rtfm",invoke_without_command=True, case_insensitive=True, slash_command=True, aliases=['rtfd'])
    @commands.bot_has_permissions(send_messages=True)
    async def rtfm(self, ctx, *, obj : str = None):
        """Gives you a documentation link for a enhanced-discord.py entity.
        Events, objects, and functions are all supported through a
        a cruddy fuzzy algorithm.
        """

        await self.do_rtfm(ctx, 'enhanced-discord.py', obj)

    @rtfm.command(name="python",aliases=["py"],slash_command=True)
    @commands.bot_has_permissions(send_messages=True)
    async def rtfm_py(self, ctx, *, object : str = commands.Option(default=None,description='Object to search for')):
        """Gives you a documentation link for a Python entity."""

        await self.do_rtfm(ctx, "python", object)

    @rtfm.command(name="master",aliases=["2.0"],slash_command=True)
    @commands.bot_has_permissions(send_messages=True)
    async def rtfm_master(self, ctx, *, object : str = commands.Option(default=None,description='Object to search for')):
        """Gives you a documentation link for a discord.py entity. (master branch)"""

        await self.do_rtfm(ctx, "discord.py-2.0", object)


    @rtfm.command(name='dpy',aliases=['discordpy', 'discord.py'],slash_command=True)
    @commands.bot_has_permissions(send_messages=True)
    async def rtfm_dpy(self, ctx, *, object : str = commands.Option(default=None,description='Object to search for')):
        """Gives you a documentation link for a discord.py entity."""

        await self.do_rtfm(ctx, "discord.py", object)


    @rtfm.command(name='edpy',slash_command=True)
    @commands.bot_has_permissions(send_messages=True)
    async def rtfm_edpy(self, ctx, *, object : str = commands.Option(default=None,description='Object to search for')):
        """Gives you a documentation link for a ed-py entity."""

        await self.do_rtfm(ctx, 'enhanced-discord.py', object)

    @rtfm.command(name='aiohttp')
    @commands.bot_has_guild_permissions(send_messages=True)
    async def rtfm_aiohttp(self, ctx: MyContext, *, object: str= None):
        """Gives you a documentation ilnk for a aiohttp entity"""

        await self.do_rtfm(ctx, 'aiohttp', object)
        

    @commands.command(name='rtfs')
    @commands.check(Cooldown(3, 8, 4, 8, commands.BucketType.user))
    async def rtfm_github(self, ctx : MyContext, library : Optional[LibraryConverter], *, query : str):
        """
        Get source code from a library for items matching the query.
        Vaild libraries: `enhanced-discord.py`, `discord.py`, `discord.py-2.0`, `twitchio`, `wavelink`, or `aiohttp`

        This command is powered by [IDevision API](https://idevision.net/static/redoc.html)
        """
        await ctx.defer()

        if library is None:
            library = "enhanced-discord.py"

        url = yarl.URL("https://idevision.net/api/public/rtfs").with_query({'query' : query, 'library' : library, 'format' : 'links'})
        headers = {"User-Agent" : 'metrodiscordbot', 'Authorization' : id_token}

        async with self.bot.session.get(url, headers=headers) as response:
            if response.status != 200:
                return await ctx.send(f"IDevision API returned a bad response: {response.status} ({response.reason})")

            data = await response.json()

        nodes : Dict = data['nodes']
        query_time = float(data['query_time'])

        if not nodes:
            e = Embed()
            e.color = discord.Colour.yellow()
            e.description = 'Could not find anything matching that query.'
            e.set_footer(text=f'Query time: {round(query_time, 3)}')
            return await ctx.send(embed=e)

        to_send = [f"[{name}]({url})" for name, url in nodes.items()]
        
        e = Embed()
        e.color = discord.Colour.green()
        e.description = '\n'.join(to_send)
        e.url = 'https://idevision.net/static/redoc.html'
        e.title = 'API result'
        e.set_footer(text=f'Powered by iDevision API • Query time: {round(query_time, 3)}')
        await ctx.send(embed=e)


def setup(bot):
    bot.add_cog(docs(bot))

