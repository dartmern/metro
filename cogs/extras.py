import asyncio
import io
from typing import NamedTuple
import discord
from discord.ext import commands
from discord import app_commands

import json
import time
import re
from collections import Counter, defaultdict

from bot import MetroBot
from utils.constants import DPY_GUILD_ID, SUPPORT_GUILD
from utils.custom_context import MyContext
from utils.useful import Embed, dynamic_cooldown
from utils.calc_tils import NumericStringParser
from utils.json_loader import get_path, read_json

data = read_json("info")
or_api_token = data['openrobot_api_key']
google_token = data['google_token']
hypixel_api_key = data['hypixel_api_key']

class Tag(NamedTuple):
    tag: str
    owner_id: int
    uses: int
    can_delete: bool
    is_alias: bool
    match: str

TAG_FILE_REGEX = re.compile(
    r"^\|\s*\d+\s*\|\s*(?P<tag>.*)\s*\|\s*(?P<owner_id>\d+)\s*\|\s*(?P<uses>\d+)\s*\|\s*(?P<can_delete>(?:True)|(?:False))\s*\|\s*(?P<is_alias>(?:True)|(?:False))\s*\|$",
    re.MULTILINE,
)

class WebhookConverter(commands.Converter):
  async def convert(self, ctx: commands.Context, argument: str) -> discord.Webhook:
    check = re.match(r"https://discord(?:app)?.com/api/webhooks/(?P<id>[0-9]{17,21})/(?P<token>[A-Za-z0-9\.\-\_]{60,68})", argument)
    if not check:
      raise commands.BadArgument("Webhook not found.")
    else:
        return check

class CodeBlock:
    missing_error = 'Missing code block. Please use the following markdown\n\\`\\`\\`language\ncode here\n\\`\\`\\`'
    def __init__(self, argument: str):
        try:
            block, code = argument.split('\n', 1)
        except ValueError:
            raise commands.BadArgument(self.missing_error)

        if not block.startswith('```') and not code.endswith('```'):
            raise commands.BadArgument(self.missing_error)

        language = block[3:]
        self.command = self.get_command_from_language(language.lower())
        self.source = code.rstrip('`').replace('```', '')

    def get_command_from_language(self, language):
        cmds = {
            'cpp': 'g++ -std=c++1z -O2 -Wall -Wextra -pedantic -pthread main.cpp -lstdc++fs && ./a.out',
            'c': 'mv main.cpp main.c && gcc -std=c11 -O2 -Wall -Wextra -pedantic main.c && ./a.out',
            'py': 'python3 main.cpp',
            'python': 'python3 main.cpp',
            'haskell': 'runhaskell main.cpp'
        }

        cpp = cmds['cpp']
        for alias in ('cc', 'h', 'c++', 'h++', 'hpp'):
            cmds[alias] = cpp
        try:
            return cmds[language]
        except KeyError as e:
            if language:
                fmt = f'Unknown language to compile for: {language}'
            else:
                fmt = 'Could not find a language to compile with.'
            raise commands.BadArgument(fmt) from e

info = read_json('info')
bitly_token = info['bitly_token']

@app_commands.context_menu(name='Calculator')
async def calculator_context_menu(interaction: discord.Interaction, message: discord.Message):
    formula = message.content
    if not formula:
        return await interaction.response.send_message("No content to calculate!", ephemeral=True)

    await interaction.response.defer(ephemeral=True)

    formula = formula.replace('*','x')
    try:
        answer = NumericStringParser().eval(formula)
    except Exception as e:
        return await interaction.followup.send(f"Could not turn [that message's content]({message.jump_url}) into an equation.", ephemeral=True)

    content = f"Calculated [{formula}]({message.jump_url}) = {answer}"
    await interaction.followup.send(content=content, ephemeral=False)

async def setup(bot: MetroBot):
    bot.tree.add_command(calculator_context_menu)
    await bot.add_cog(extras(bot))

class extras(commands.Cog, description='Extra commands for your use.'):
    def __init__(self, bot: MetroBot):
        self.bot = bot

    @property
    def emoji(self) -> str:
        return '<:mplus:904450883633426553>'

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

        formula = formula.lower().replace('k', '000').replace('m','000000')
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
        embed.description = f'Input: `{formula}`\nOutput: `{answer:,}`'
        embed.set_footer(text=f'Calculated in {round(ping, 1)}ms')
        await ctx.send(embed=embed)


    @commands.command()
    @commands.bot_has_permissions(send_messages=True)
    async def cleanup(self, ctx: MyContext, amount: int = 5):
        """
        Cleans up the bot's messages. 
        Defaults to 25 messages. If you or the bot does not have the Manage Messages permission, the search will be limited to 25 messages.
        """
        if amount > 25:
            if not ctx.channel.permissions_for(ctx.author).manage_messages:
                await ctx.send("You must have `manage_messages` permission to perform a search greater than 25")
                return
            if not ctx.channel.permissions_for(ctx.me).manage_messages:
                await ctx.send("I need the `manage_messages` permission to perform a search greater than 25")
                return

        def check(msg):
            return msg.author == ctx.me
        if ctx.channel.permissions_for(ctx.me).manage_messages:
            deleted = await ctx.channel.purge(limit=amount, check=check)
        else:
            deleted = await ctx.channel.purge(limit=amount, check=check, bulk = False)
        spammers = Counter(m.author.display_name for m in deleted)
        deleted = len(deleted)
        messages = [f'{deleted} message{" was" if deleted == 1 else "s were"} removed.']
        if deleted:
            messages.append('')
            spammers = sorted(spammers.items(), key=lambda t: t[1], reverse=True)
            messages.extend(f'**{name}**: {count}' for name, count in spammers)

        to_send = '\n'.join(messages)
        if len(to_send) > 2000:
            await ctx.send(f'Successfully removed {deleted} messages.', delete_after=5)
        else:
            await ctx.send(to_send, delete_after=10)

    @commands.command(name='tag_check')
    @commands.is_owner()
    async def tags(self, ctx: MyContext, *, claim: bool):
        """Owner reserved command."""

        def check(message: discord.Message):
            if message.guild.id != SUPPORT_GUILD:
                return False
            if len(message.attachments) != 1 or message.attachments[0].filename != "tags.txt":
                return False
            return True

        m = await ctx.send('Input a file to parse.')
        try:
            message = await self.bot.wait_for('message', check=check, timeout=60)
        except asyncio.TimeoutError:
            try:
                await m.delete()
            except discord.HTTPException:
                pass
        
        await m.edit(content='Parsing...')

        async with ctx.typing():
            contents = await message.attachments[0].read()
            contents = contents.decode("utf-8")
            sep, contents = contents.split("\n", 1)
            key, contents = contents.split("\n", 1)

            all_tags: dict[str, Tag] = {}
            tag_owners: dict[int, list[str]] = defaultdict(list)

            for match in TAG_FILE_REGEX.finditer(contents):
                tag, owner_id, uses, can_delete, is_alias = match.groups()
                tag = tag.rstrip()
                owner_id = int(owner_id)
                uses = int(uses)
                can_delete = can_delete == "True"
                is_alias = is_alias == "True"

                all_tags[tag] = Tag(tag, owner_id, uses, can_delete, is_alias, match.group())
                tag_owners[owner_id].append(tag)

            orphaned_tags: list[str] = []

            guild = self.bot.get_guild(DPY_GUILD_ID)
            if not guild:
                await m.edit(content='Guild wasn\'t found...')
                return

            for user_id, tags in tag_owners.items():
                if guild.get_member(user_id) is None:
                    orphaned_tags.extend(tags)

            tag_file = io.BytesIO()

            if claim:
                for tag in sorted(orphaned_tags, key=lambda t: all_tags[t].uses, reverse=True):
                    tag_file.write((f"?tag claim {tag}\n").encode("utf-8"))
            else:
                tag_file.write((sep + "\n").encode("utf-8"))
                tag_file.write((key + "\n").encode("utf-8"))
                tag_file.write((sep + "\n").encode("utf-8"))

                for tag in sorted(orphaned_tags, key=lambda t: all_tags[t].uses, reverse=True):
                    tag_file.write((all_tags[tag].match + "\n").encode("utf-8"))

                tag_file.write((sep + "\n").encode("utf-8"))
            tag_file.seek(0)

        await m.edit(content='Sending file...')
        await ctx.author.send(file=discord.File(tag_file, "available_tags.txt"))
            
    @commands.command(name='repl', aliases=['coliru'])
    @commands.dynamic_cooldown(dynamic_cooldown, type=commands.BucketType.user)
    async def coliru(self, ctx: MyContext, *, code: CodeBlock):
        """Compile code through coliru."""

        payload = {
            'cmd' : code.command,
            'src' : code.source
        }

        data = json.dumps(payload)

        async with ctx.typing():
            async with self.bot.session.post('http://coliru.stacked-crooked.com/compile', data=data) as response:
                if response.status != 200:
                    return await ctx.send("Coliru did not response in time.")

                output = await response.text(encoding='utf-8')

                if len(output) < 1992:
                    return await ctx.send(f'```\n{output}\n```')

                url = await self.bot.mystbin_client.post(output)
                return await ctx.send("Output was too long: %s" % url)

    @commands.command()
    @commands.dynamic_cooldown(dynamic_cooldown, type=commands.BucketType.user)
    async def google(self, ctx: MyContext, *, query: str):
        """Search google using it's API."""

        async with ctx.typing():
            start = time.perf_counter()
            results = await self.bot.google_client.search(query, safesearch=False)
            end = time.perf_counter()

            ping = (end - start) * 1000

            embed = discord.Embed(color=ctx.color)
            embed.set_author(name=f'Google search: {query}')
            for result in results[:5]:
                embed.add_field(name=result.title, value=f'{result.url}\n{result.description}', inline=False)
            embed.set_footer(text=f'Queried in {round(ping, 2)} milliseconds. | Safe Search: Disabled')
            return await ctx.send(embed=embed)
