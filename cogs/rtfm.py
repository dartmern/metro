import inspect
import sys
import discord
from discord.ext import commands
from discord import app_commands

from typing import Callable, Dict, List, Literal, Optional
import io
import re
import os
import zlib
import yarl
import lxml.etree as etree

from bot import MetroBot
from utils.useful import Embed, dynamic_cooldown
from utils.custom_context import MyContext
from utils.json_loader import read_json
from utils.embeds import create_embed
import utils.fuzzy as fuzzy_
from utils.formats import to_codeblock

data = read_json('info')
id_token = data['id_token']

# Parts of rtfs code is from BOB
# https://github.com/IAmTomahawkx/bob/blob/7f97c7b5d502cbb476f838c1ca9fb46cc46c4b03/extensions/idevision.py

# Most of rtfm code is from R. Danny
# https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/api.py#L308-L316

# credit:
# https://github.com/AbstractUmbra/Kukiko-archive/blob/main/cogs/rtfx.py

RTFS = (
    "discord",
    "discord.ext.commands",
    "discord.ext.tasks",
    "discord.ext.menus",
    "cogs",
    "utils"
)

class SourceConverter(commands.Converter):
    async def convert(self, ctx: MyContext, argument: str) -> Optional[str]:
        args = argument.split(".")
        top_level = args[0]
        if top_level in ("commands", "menus", "tasks"):
            top_level = f"discord.ext.{top_level}"

        if top_level not in RTFS:
            raise commands.BadArgument(f"`{top_level}` is not an allowed sourceable module.")

        recur = sys.modules[top_level]

        if len(args) == 1:
            return inspect.getsource(recur)

        for item in args[1:]:
            if item == "":
                raise commands.BadArgument("Don't even try.")

            recur = inspect.getattr_static(recur, item, None)

            if recur is None:
                raise commands.BadArgument(f"{argument} is not a valid module path.")

        if isinstance(recur, property):
            recur: Callable[..., None] = recur.fget

        return inspect.getsource(recur)

class LibraryConverter(commands.Converter):
    async def convert(self, _, param):
        if param.lower() in ("dpy", "discordpy", "discord.py", "dpy2"):
            return "discord.py"
        elif param.lower() in ("tio", "twitch", "twitchio"):
            return "twitchio"
        elif param.lower() in ("wl", "wave", "link", "wavelink"):
            return "wavelink"
        elif param.lower() in ("ahttp", "aiohttp"):
            return "aiohttp"
        else:
            raise commands.UserInputError("Library must be one of `discord.py`, `twitchio`, `wavelink`, or `aiohttp`")

class RTFMConverter(commands.Converter):
    async def convert(self, _, param):
        if param.lower() in ("edpy", "enhanced-discord.py"):
            return "enhanced-discord.py"
        if param.lower() in ("dpy", "discordpy", "discord.py"):
            return "discord.py"
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
        self.page_types = {
            'discord.py': 'https://discordpy.readthedocs.io/en/stable',
            'discord.py (master)': 'https://discordpy.readthedocs.io/en/latest',
            'python': 'https://docs.python.org/3',
            'aiohttp' : 'https://docs.aiohttp.org/en/stable/',
            'twitchio': 'https://twitchio.dev/en/latest',
            'mystbin.py': 'https://mystbinpy.readthedocs.io/en/latest/',
            'pomice': 'https://pomice.readthedocs.io/en/latest/',
            'topgg.py': 'https://topggpy.readthedocs.io/en/stable/'
        }

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


    async def build_rtfm_lookup_table(self):
        cache: dict[str, dict[str, str]] = {}
        for key, page in self.page_types.items():
            cache[key] = {}
            async with self.bot.session.get(page + '/objects.inv') as resp:
                if resp.status != 200:
                    raise RuntimeError('Cannot build rtfm lookup table, try again later.')

                stream = SphinxObjectFileReader(await resp.read())
                cache[key] = self.parse_object_inv(stream, page)

        self._rtfm_cache = cache

    async def do_slash_rtfm(
        self, 
        interaction: discord.Interaction, 
        key: str, 
        obj: str,
        search: bool = True # weather this is a search or execution
    ):
        await interaction.response.defer()

        if not hasattr(self, '_rtfm_cache'):
            await self.build_rtfm_lookup_table()

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

        matches = fuzzy_.finder(obj, cache, key=lambda t: t[0], lazy=False)[:8]

        if search:
            return [key for key, url in matches]

        e = Embed()
        if len(matches) == 0:
            return await interaction.followup.send('No matches were found. Sorry.', ephemeral=True)


        e.description = '\n'.join(f'[`{key}`]({url})' for key, url in matches)
        await interaction.followup.send(embed=e)


    async def do_rtfm(self, ctx : MyContext, key: str, obj: str):
        page_types = self.page_types

        if obj is None:
            await ctx.typing()
            await ctx.send(page_types[key], hide=True)
            return


        if not hasattr(self, '_rtfm_cache'):
            await ctx.typing()
            await self.build_rtfm_lookup_table()

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

        matches = fuzzy_.finder(obj, cache, key=lambda t: t[0], lazy=False)[:8]

        e = Embed()
        if len(matches) == 0:
            return await ctx.send('No matches were found. Try again with a different keyword.')


        e.description = '\n'.join(f'[`{key}`]({url})' for key, url in matches)
        await ctx.send(embed=e, hide=True)

    @app_commands.command(name='rtfm')
    @app_commands.describe(library='The library you would like to search in.')
    @app_commands.describe(object='The entity you want to search for.')
    async def rtfm_slash(
        self, 
        interaction: discord.Interaction,
        library: Optional[str] = 'discord.py',
        object: Optional[str] = None
    ):
        """Search through documentation. Defaults to discord.py"""

        if library not in list(self.page_types):
            return await interaction.response.send_message(f'That is not a valid library.', ephemeral=True)

        if not object:
            return await interaction.response.send_message(self.page_types[library])

        await self.do_slash_rtfm(interaction, library, object, search=False)

    @rtfm_slash.autocomplete('object')
    async def rtfm_slash_object_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:
    
        library = interaction.namespace.library or list(self.page_types.items())[0][0] # default is d.py stable
        items = await self.do_slash_rtfm(interaction, library, current)

        return [
            app_commands.Choice(name=item, value=item)
            for item in items if current.lower() in item.lower()
        ]

    @rtfm_slash.autocomplete('library')
    async def rtfm_slash_library_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> List[app_commands.Choice[str]]:

        return [
            app_commands.Choice(name=item, value=item)
            for item in list(self.page_types.keys()) if current.lower() in item.lower()
        ]

    @commands.group(name="rtfm",invoke_without_command=True, case_insensitive=True, aliases=['rtfd'])
    @commands.bot_has_permissions(send_messages=True)
    async def rtfm(self, ctx, *, object : str = None):
        """Gives you a documentation link for a discord.py entity. (stable branch)

        Events, objects, and functions are all supported through a
        a cruddy fuzzy algorithm.

        It is recommended that you use the slash command version
        of this command if it's possible. Autocomplete can give
        you more assistance when searching.
        """

        await self.do_rtfm(ctx, 'discord.py', object)

    @rtfm.command(name="python",aliases=["py"])
    @commands.bot_has_permissions(send_messages=True)
    async def rtfm_py(self, ctx, *, object : str = None):
        """Returns documentation for a Python object."""

        await self.do_rtfm(ctx, "python", object)

    @rtfm.command(name='aiohttp')
    @commands.bot_has_guild_permissions(send_messages=True)
    async def rtfm_aiohttp(self, ctx: MyContext, *, object: str = None):
        """Returns documentation for a aiohttp object."""

        await self.do_rtfm(ctx, 'aiohttp', object)

    @rtfm.command(name='twitchio')
    async def rtfm_twitchio(self, ctx: MyContext, *, object: str = None):
        """Returns documentation for a twitchio object."""

        await self.do_rtfm(ctx, 'twitchio', object)

    @rtfm.command(name='mystbin', aliases=['mystbin.py'])
    async def rtfm_mystbin(self, ctx: MyContext, *, object: str = None):
        """Returns documentation for a mystbin.py object."""

        await self.do_rtfm(ctx, 'mystbin.py', object)

    @rtfm.command(name='master', aliases=['latest'])
    async def rtfm_master(self, ctx: MyContext, *, object: str = None):
        """Returns documentation for a discord.py object. (master)"""

        await self.do_rtfm(ctx, 'discord.py (master)', object)

    @rtfm.command(name='pomice')
    async def rtfm_pomice(self, ctx: MyContext, *, object: str = None):
        """Returns documentation for a pomice object."""

        await self.do_rtfm(ctx, 'pomice', object)

    @rtfm.command(name='refresh', aliases=['reload'])
    @commands.is_owner()
    async def rtfm_refresh(self, ctx: MyContext):
        """Refresh the RTFM lookup cache."""

        async with ctx.typing():
            await self.build_rtfm_lookup_table()

        await ctx.check()

    async def do_rtfs(
        self, 
        library: Literal['discord.py-2', 'twitchio', 'wavelink', 'aiohttp'],
        query: str):

        url = yarl.URL("https://idevision.net/api/public/rtfs").with_query({'query' : query, 'library' : library, 'format' : 'links'})
        headers = {"User-Agent" : 'metrodiscordbot', 'Authorization' : id_token}

        async with self.bot.session.get(url, headers=headers) as response:
            if response.status != 200:
                return create_embed(f"IDevision API returned a bad response: {response.status} ({response.reason})")

            data = await response.json()

        nodes : Dict = data['nodes']
        query_time = float(data['query_time'])

        if not nodes:
            return create_embed('Could not find anything matching that query.', color=discord.Color.yellow())

        to_send = [f"[{name}]({url})" for name, url in nodes.items()]
        
        e = Embed(title='API result', color=discord.Color.green())
        e.description = '\n'.join(to_send)
        e.url = 'https://idevision.net/static/redoc.html'
        e.set_footer(text=f'Powered by iDevision API • Query time: {round(query_time, 3)}')
        return e

    @commands.command(name='rtfs')
    @commands.dynamic_cooldown(dynamic_cooldown, type=commands.BucketType.user)
    async def rtfm_github(self, ctx : MyContext, library : Optional[LibraryConverter], *, query : str):
        """
        Get source code from a library for items matching the query.
        Vaild libraries:  `discord.py`, `twitchio`, `wavelink`, or `aiohttp`

        This command is powered by [IDevision API](https://idevision.net/static/redoc.html)
        """
        await ctx.typing()

        if library is None or library == 'discord.py':
            library = "discord.py-2"

        resp = await self.do_rtfs(library, query)
        await ctx.send(embed=resp)

    @app_commands.command(name='rtfs')
    @app_commands.describe(library='The library you would like to search in.')
    @app_commands.describe(query='The query/method you want to search for.')
    async def rtfm_github_slash(
        self, interaction: discord.Interaction,
        query: str, library: Optional[Literal['discord.py', 'twitchio', 'wavelink', 'aiohttp']] = 'discord.py',
        ):
        """Get source code from a library for items matching the query. (With API)"""

        await interaction.response.defer()

        if library is None or library == 'discord.py':
            library = 'discord.py-2'

        resp = await self.do_rtfs(library, query)
        await interaction.followup.send(embed=resp)

    @commands.command(name='rtfs-source')
    @commands.is_owner()
    async def _rtfs(self, ctx: MyContext, *, target: Optional[SourceConverter] = None):
        if not target:
            joined = "\n".join(RTFS)
            await ctx.send(f'Here\'s a list of valid libraries for this command:\n{joined}')
            return
        
        from textwrap import dedent
        target = dedent(target)

        if len(target) < 4000:
            fmt = to_codeblock(target, language='py', escape_md=False)
            await ctx.send(fmt)
        else:
            file = discord.File(io.StringIO(target), filename='source.py')
            await ctx.send(file=file)

async def setup(bot: MetroBot):
    await bot.add_cog(docs(bot))
