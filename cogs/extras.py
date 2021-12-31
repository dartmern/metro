import discord
from discord.ext import commands

import time

from bot import MetroBot
from utils.custom_context import MyContext
from utils.converters import DiscordCommand
from utils.useful import Cooldown, Embed, chunkIt
from utils.calc_tils import NumericStringParser
from utils.json_loader import get_path


def setup(bot: MetroBot):
    bot.add_cog(extras(bot))

class extras(commands.Cog, description='Extra commands for your use.'):
    def __init__(self, bot: MetroBot):
        self.bot = bot

    @property
    def emoji(self) -> str:
        return '<:mplus:904450883633426553>'

    @commands.command()
    async def whatcog(self, ctx: MyContext, *, command: DiscordCommand) -> discord.Message:
        """Show what cog a command belongs to."""
        return await ctx.send(f"`{command.qualified_name}` belongs to the `{command.cog.qualified_name.capitalize() if command.cog else 'No Category'}` category")

    @commands.command()
    async def length(self, ctx: MyContext, *, object: str) -> discord.Message:
        """Get the length of a string."""
        return await ctx.send(f"That string is `{len(object)}` characters long.")

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


    def read_tags(self, ctx : MyContext):
        ids, tags = [], []

        DPY_GUILD = ctx.bot.get_guild(336642139381301249)
        for member in DPY_GUILD.humans:
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
    async def tags(self, ctx : MyContext, per_page : int = 10):
        await ctx.check()
        result = await self.bot.loop.run_in_executor(None, self.read_tags, ctx)
        await ctx.paginate(result, per_page=per_page)
        return
        m = chunkIt(result, 20)

        for i in m:
            e = Embed()
            e.description = ', '.join(i)
            
            #await ctx.author.send(embed=e)


    @commands.command(name='shorten_url', aliases=['shorten'])
    @commands.check(Cooldown(2, 5, 3, 5, commands.BucketType.user))
    async def shorten_url(self, ctx: MyContext, *, url: str):
        """
        Shorten a long url.
        
        Powered by [Bitly API](https://dev.bitly.com/)
        """
        if not re.fullmatch(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', url):
            raise commands.BadArgument("That is not a vaild url.")

        await ctx.defer()

        params = {"access_token" : bitly_token, "longUrl" : url}
        async with self.bot.session.get("https://api-ssl.bitly.com/v3/shorten", params=params) as response:
            if response.status != 200:
                raise commands.BucketType("Bitly API returned a bad response. Please try again later.")

            data = await response.json()

        embed = Embed()
        embed.colour = discord.Colour.orange()
        embed.description = f'Your shortened url: {data["data"]["url"]}\nOriginal url: {url}'
        embed.set_author(name='URL Shortner')
        return await ctx.send(embed=embed)