import discord
from discord.ext import commands

from utils.useful import Embed, fuzzy

import io
import re
import os
import zlib


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


class docs(commands.Cog, description="Read docs about discord.py or python"):
    def __init__(self, bot):
        self.bot = bot


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


    async def do_rtfm(self, ctx, key, obj):
        page_types = {
            'latest': 'https://discordpy.readthedocs.io/en/latest',
            'python': 'https://docs.python.org/3',
            'master': 'https://discordpy.readthedocs.io/en/master',
            'edpy' : 'https://enhanced-dpy.readthedocs.io/en/latest',
            'aiohttp' : 'https://docs.aiohttp.org/en/stable/'
            
        }

        if obj is None:
            await ctx.send(page_types[key])
            return


        if not hasattr(self, '_rtfm_cache'):
            await ctx.trigger_typing()
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
        await ctx.reply(embed=e)



    @commands.group(name="rtfm",invoke_without_command=True, case_insensitive=True, slash_command=True, aliases=['rtfd'])
    @commands.bot_has_permissions(send_messages=True)
    async def rtfm(self, ctx, *, obj : str = None):
        """Gives you a documentation link for a enhanced-discord.py entity.
        Events, objects, and functions are all supported through a
        a cruddy fuzzy algorithm.
        """

        await self.do_rtfm(ctx, 'edpy', obj)



    @rtfm.command(name="python",aliases=["py"],slash_command=True)
    @commands.bot_has_permissions(send_messages=True)
    async def rtfm_py(self, ctx, *, object : str = commands.Option(default=None,description='Object to search for')):
        """Gives you a documentation link for a Python entity."""

        await self.do_rtfm(ctx, "python", object)

    @rtfm.command(name="master",aliases=["2.0"],slash_command=True)
    @commands.bot_has_permissions(send_messages=True)
    async def rtfm_master(self, ctx, *, object : str = commands.Option(default=None,description='Object to search for')):
        """Gives you a documentation link for a discord.py entity. (master branch)"""

        await self.do_rtfm(ctx, "master", object)


    @rtfm.command(name='dpy',aliases=['discordpy', 'discord.py'],slash_command=True)
    @commands.bot_has_permissions(send_messages=True)
    async def rtfm_dpy(self, ctx, *, object : str = commands.Option(default=None,description='Object to search for')):
        """Gives you a documentation link for a discord.py entity."""

        await self.do_rtfm(ctx, "latest", object)


    @rtfm.command(name='edpy',slash_command=True)
    @commands.bot_has_permissions(send_messages=True)
    async def rtfm_edpy(self, ctx, *, object : str = commands.Option(default=None,description='Object to search for')):
        """Gives you a documentation link for a ed-py entity."""

        await self.do_rtfm(ctx, 'edpy', object)

    @rtfm.command(name='aiohttp',slash_command=True)
    @commands.bot_has_permissions(send_messages=True)
    async def rtfm_aiohttp(self, ctx, *, object : str = commands.Option(default=None, description='Object to search for')):
        """Gives you documentation link for a aiohttp entity."""

        await self.do_rtfm(ctx, 'aiohttp', object)


def setup(bot):
    bot.add_cog(docs(bot))

