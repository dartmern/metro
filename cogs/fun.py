from typing import Optional
import discord
from discord.ext import commands
from bot import MetroBot

from utils.useful import Embed

import random

from utils.custom_context import MyContext


class fun(commands.Cog, description=":smile: Fun commands!"):
    def __init__(self, bot : MetroBot):
        self.bot = bot

    @commands.command()
    @commands.bot_has_permissions(send_messages=True)
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
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def _8ball(self, ctx, *, question):
        """
        Ask the 8-ball a question!
        """

        answers = [
            "It is certain.",
            "It is decidedly so.",
            "Without a doubt.",
            "Definitely",
            "Why don't you go ask your mom smh.",
            "What? No!",
            "Unscramble `esy`",
            "Doubtful...",
            "I'm lazy rn, don't want to answer it.",
            "Ok, no",
            "Possibly so!",
            "Yes. Yes. Yes.",
            "100% No."
        ]

        em = Embed(
            title="Magic 8-ball",
            description=f"You: {question}\n\🎱: {random.choice(answers)}",
            colour=discord.Color.random(),
        )
        await ctx.send(embed=em)

    @commands.command(name='google')
    async def google(self, ctx : MyContext, *, query : str):
        await ctx.send(f"https://www.google.com/search?q={query.replace(' ','+')}")


def setup(bot):
    bot.add_cog(fun(bot))























