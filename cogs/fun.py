from code import InteractiveConsole
from typing import Any, List, Optional, Union
import discord
from discord.emoji import Emoji

from discord.ext import commands
from discord.partial_emoji import PartialEmoji
from bot import MetroBot

from utils.useful import Embed

import random
import asyncio

from utils.custom_context import MyContext


class MyButton(discord.ui.Button):
    async def callback(self, interaction: discord.Interaction):
        self.view.score += 1
        await interaction.response.defer()
        self.disabled = True
        self.style = discord.ButtonStyle.gray
        await self.view.message.edit(view=self.view)
        await interaction.response.defer()

class LostButton(discord.ui.Button):
    async def callback(self, interaction: discord.Interaction):
        for item in self.view.children:
            if isinstance(item, (MyButton, EndButton)):
                item.disabled = True
        self.disabled = True
        await self.view.message.edit(view=self.view)
        await interaction.response.send_message(f"You lost!!! Your score was **{self.view.score}**")

class EndButton(discord.ui.Button):
    async def callback(self, interaction: discord.Interaction):
        for item in self.view.children:
            if isinstance(item, MyButton):
                item.disabled = True
        self.disabled = True
        await self.view.message.edit(view=self.view)
        await interaction.response.send_message(f"Your score was **{self.view.score}**")

class StressView(discord.ui.View):
    def __init__(self, ctx):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.message: Optional[discord.Message] = None
        self.score: int = 0

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(f"This is not your interaction!", ephemeral=True)
        else:
            return True

    async def start(self):
        bomb = random.randint(0, 24)
        for _ in range(25):
            if _ == bomb:
                self.add_item(LostButton(label='\u200b', style=discord.ButtonStyle.blurple))
            elif _ == 12:
                self.add_item(EndButton(emoji='\U0001f5d1'))
            else:
                self.add_item(MyButton(label='\u200b', style=discord.ButtonStyle.blurple))
        self.message = await self.ctx.send('\u200b', view=self)

class fun(commands.Cog, description="Fun commands!"):
    def __init__(self, bot : MetroBot):
        self.bot = bot

    @property
    def emoji(self) -> str:
        return '😄'

    @commands.command()
    async def stress(self, ctx: MyContext):
        """Release your stress."""
        view = StressView(ctx)
        await view.start()

    @commands.command(name="8ball",aliases=['8'])
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def _8ball(self, ctx, *, question):
        """
        Ask the 8-ball a question!

        This was the first ever command created
        and will not be maintained to keep the vibe.
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
            description=f"> {question}\n\🎱: {random.choice(answers)}",
            colour=ctx.color,
        )
        await ctx.send(embed=em)


async def setup(bot):
    await bot.add_cog(fun(bot))
    