import discord
from discord.ext import commands

from utils.useful import Embed, fuzzy

import aiohttp
import re

from typing import Optional

import random

class detect(aiohttp.ClientSession):
    async def find(self, url):
        source = str(await (await super().get(url)).content.read()).lower()
        phrases = ["rickroll", "rick roll", "rick astley", "never gonna give you up"]
        await super().close()
        return bool(re.findall("|".join(phrases), source, re.MULTILINE))


class fun(commands.Cog, description="Fun commands!"):
    def __init__(self, bot):
        self.bot = bot


    @commands.command()
    async def rickroll(self, ctx, *, link):
        """
        Detects if a link is a rickroll
        (Must start with https://)
        """

        i = link.replace("<", "").replace(">", "")
        if "https://" in link:
            if await detect().find(i):
                await ctx.reply("Rickroll detected :eyes:")
            else:
                await ctx.reply("That website is safe :)")
        else:
            await ctx.send(link + " is not a valid URL...")


    @commands.command(aliases=["echo"])
    @commands.has_guild_permissions(manage_messages=True)
    async def say(self, ctx, channel : Optional[discord.TextChannel], * , message):
        """Send a message to a channel as the bot"""

        channel = channel or ctx.channel
        await channel.send(message)
        await ctx.check()

    @commands.command(aliases=["echod"])
    @commands.has_guild_permissions(manage_messages=True)
    async def sayd(self, ctx, channel: Optional[discord.TextChannel], *, message):
        """Send a message to a channel as the bot then deletes your message"""

        channel = channel or ctx.channel
        await channel.send(message)
        await ctx.message.delete()


    @commands.command()
    async def random(self, ctx, minimum = 0, maximum = 100):
        """Displays a random number within an optional range.

        The minimum must be smaller than the maximum and the maximum number accepted is 1000.
        """

        maximum = min(maximum, 1000)
        if minimum >= maximum:
            await ctx.send('Maximum is smaller than minimum.')
            return

        await ctx.send(random.randint(minimum, maximum))


    @commands.command(name="8ball",aliases=['8'])
    async def _8ball(self, ctx, *, question):
        """
        Ask the 8-ball a question!
        """

        answers = [
            "It is certain.",
            "It is decidedly so.",
            "Without a doubt.",
            "Is Trump's skin orange?",
            "Definitely",
            "Why don't you go ask your mom smh.",
            "What? No!",
            "Unscramble `esy`",
            "Doubtful...",
            "I'm lazy rn, don't want to answer it.",
            "Ok, no",
            "Possibly so!",
            "Yes. Yes. Yes.",
        ]

        em = Embed(
            title="Magic 8-ball",
            description=f"You: {question}\n🎱: {random.choice(answers)}",
            colour=discord.Color.random(),
        )
        await ctx.send(embed=em)









def setup(bot):
    bot.add_cog(fun(bot))























