from asyncore import write
import json
import random
from typing import Dict, Optional
import aiohttp
import discord
from discord.ext import commands
from discord import app_commands

import time
import re
import async_cse
import yarl # google

from bot import MetroBot
from utils.constants import TESTING_GUILD
from utils.custom_context import MyContext
from utils.converters import DiscordCommand, ImageConverter
from utils.useful import Embed, chunkIt, dynamic_cooldown
from utils.calc_tils import NumericStringParser
from utils.json_loader import get_path, read_json, write_json

data = read_json("info")
or_api_token = data['openrobot_api_key']
google_token = data['google_token']
hypixel_api_key = data['hypixel_api_key']

class WebhookConverter(commands.Converter):
  async def convert(self, ctx: commands.Context, argument: str) -> discord.Webhook:
    check = re.match(r"https://discord(?:app)?.com/api/webhooks/(?P<id>[0-9]{17,21})/(?P<token>[A-Za-z0-9\.\-\_]{60,68})", argument)
    if not check:
      raise commands.BadArgument("Webhook not found.")
    else:
        return check

class CodeBlock:
    missing_error = 'Missing code block. Please use the following markdown\n\\`\\`\\`language\ncode here\n\\`\\`\\`'
    def __init__(self, argument):
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


    def read_tags(self, ctx : MyContext):
        ids, tags = [], []
        
        guild = ctx.bot.get_guild(336642139381301249)
        humans = [hum for hum in guild.members if not hum.bot]

        for member in humans:
            ids.append(member.id)
        
        cwd = get_path()
        with open(cwd+'/config/'+'tags.txt', 'r', encoding='utf8') as file:
            for line in file.read().split("\n"):
    
                id = line[-52:-32]
  
                try:
                    if int(id) not in ids:
                        tag = line[10:112]
                        
                        tags.append(str(tag))
                except:
                    continue
        
        return tags

    @commands.command(hidden=True)
    @commands.is_owner()  
    @commands.bot_has_permissions(send_messages=True)  
    async def tags(self, ctx : MyContext, per_page : int = 16):
        await ctx.check()
        result = await self.bot.loop.run_in_executor(None, self.read_tags, ctx)
        await ctx.paginate(result, per_page=per_page)

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

