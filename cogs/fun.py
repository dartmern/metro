from typing import Any, List, Optional, Union
import discord
from discord.emoji import Emoji

from discord.ext import commands
from discord.partial_emoji import PartialEmoji
from bot import MetroBot
from utils.checks import SUPPORT_GUILD, TESTER_ROLE

from utils.useful import Embed

import random
import asyncio

from utils.custom_context import MyContext

class GameButton(discord.ui.Button):
    def __init__(self, *, style: discord.ButtonStyle = discord.ButtonStyle.gray, label: Optional[str] = None, disabled: bool = False, custom_id: Optional[str] = None, url: Optional[Any] = None, emoji: Optional[Union[str, Emoji, PartialEmoji]] = None, row: Optional[int] = None, my_id: int):
        super().__init__(style=style, label=label, disabled=disabled, custom_id=custom_id, url=url, emoji=emoji, row=row)
        self.my_id = my_id

    async def callback(self, interaction: discord.Interaction):
        self.view.button_data.append(self.my_id)
        #await interaction.response.send_message(self.my_id, ephemeral=True)
        

class Game(discord.ui.View):
    def __init__(self, ctx: MyContext):
        super().__init__(timeout=180)
        self.ctx: MyContext = ctx
        self.round: int = 1
        self.game_data: List = []
        self.message: Optional[discord.Message] = None # will get something in start function
        self.button_data: List = []

        self.a = {}

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message("This is not your game...", ephemeral=True)
        else:
            return True

    async def start(self):
        for _ in range(1, 26):
            self.add_item(GameButton(label='\u200b', disabled=True, my_id=_))#, custom_id=_))
        
        embed = discord.Embed(color=self.ctx.color)
        embed.description = "**Click everything I show in order when the embed turns green.**"
        embed.set_author(name='Credit: dartmern')
        self.message = await self.ctx.send(view=self, embed=embed)

        await self.start_game()    

    async def start_game(self):
        await asyncio.sleep(1) # Giving a little grace period to the bitch that's playin

        while True:
            outcome = await self.run_once()
            if outcome is False:
                for item in self.children:
                    if isinstance(item, GameButton):
                        item.disabled = True
                emb = discord.Embed(color=discord.Colour.red())
                emb.set_author(name=f"You got to round: {self.round}")
                emb.description = "__**You lost!**__ Try again and actually think..."
                return await self.message.edit(embed=emb, view=self)
            else:
                self.round += 1
                self.button_data = []
                await asyncio.sleep(2)
                embed = discord.Embed(color=self.ctx.color)
                embed.description = "Click the 0's in the order they were in the past round **and** the new 1."
                embed.set_author(name=f'Round: {self.round}')
                await self.message.edit(embed=embed, view=self)


    async def run_once(self):
        for item in self.children:
            if isinstance(item, GameButton):
                item.disabled = True
        await self.message.edit(view=self)
        while True:
            ran = random.randint(1, 25)
            if ran not in self.game_data:
                self.game_data.append(ran)
                break
            else:
                continue
        on = 0
        for item in self.children:
            if isinstance(item, GameButton):
                try:
                    item.label = self.a[item.my_id]
                except KeyError:
                    if item.my_id in self.game_data:
                        item.label = on + 1
                        on += 1
                        self.a[item.my_id] = on-1
                    else:
                        continue
        await self.message.edit(view=self)
        await asyncio.sleep(self.round + 2)

        em = discord.Embed(color=discord.Colour.green())
        em.description = "__**Go!**__ Press if 0's in the order they were in the past (if there are any 0's) and then press the newly appearing 1..."
        em.set_footer(text='Don\'t click any extra buttons, you will lose.')

        for item in self.children:
            if isinstance(item, GameButton):
                item.disabled = False
                item.label = '\u200b'
        await self.message.edit(view=self, embed=em)
        await asyncio.sleep(self.round + 5)

        print(self.game_data)
        print(self.button_data)
        if self.game_data != self.button_data:
            return False
        return True



class fun(commands.Cog, description="Fun commands!"):
    def __init__(self, bot : MetroBot):
        self.bot = bot

    @property
    def emoji(self) -> str:
        return '😄'

    @commands.command()
    async def test(self, ctx: MyContext):
        """Test your memory with a simple game"""
        view = Game(ctx)
        await view.start()

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


def setup(bot):
    bot.add_cog(fun(bot))























