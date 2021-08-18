
from typing import Optional, Union
import discord
from discord.ext import commands

import re
import time
import datetime
from discord.ext.commands.cooldowns import BucketType
from discord.ext.commands.errors import MissingPermissions
from humanize.time import precisedelta


from utils.useful import Embed, RoboPages

from discord.ext import menus
from discord.ext.menus.views import ViewMenuPages

import asyncio
import argparse, shlex
from typing import Optional


class Arguments(argparse.ArgumentParser):
    def error(self, message):
        raise RuntimeError(message)

class View(discord.ui.View):
    def __init__(self, author):
        super().__init__(timeout=60)
        self.user = author


    async def on_timeout(self) -> None:
        self.foo.disabled = True
        self.boo.disabled = True
        await self.message.edit(view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.user == interaction.user:
            return True
        await interaction.response.send_message(f"Only {self.user} can use this menu. AKA stop pressing other people's buttons",
                                                ephemeral=True)
        return False

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def foo(self, _, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(content='Task confirmed.')

        for item in self.children:
            item.disabled = True

        await interaction.message.edit(view=self)


    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.gray)
    async def boo(self, _, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(content="Task canceled.")

        for item in self.children:
            item.disabled = True

        await interaction.message.edit(view=self)



    @classmethod
    async def start(cls, ctx):
        self = cls(ctx.author)
        self.message = await ctx.channel.send('Are you sure you would like to continue?', view=self)
        return self




time_regex = re.compile(r"(\d{1,5}(?:[.,]?\d{1,5})?)([smhd])")
time_dict = {"h":3600, "s":1, "m":60, "d":86400}

class TimeConverter(commands.Converter):
    async def convert(self, ctx, argument):
        matches = time_regex.findall(argument.lower())
        time = 0
        for v, k in matches:
            try:
                time += time_dict[k]*float(v)
            except KeyError:
                raise commands.BadArgument("{} is an invalid time-key! h/m/s/d are valid!".format(k))
            except ValueError:
                raise commands.BadArgument("{} is not a number!".format(v))
        return time


class ButtonMenuSource(menus.ListPageSource):
    def __init__(self, data):
        super().__init__(data, per_page=4)

    async def format_page(self, menu, entries):
        offset = menu.current_page * self.per_page
        return '\n'.join(f'{i}. {v}' for i, v in enumerate(entries, start=offset))


class NormalMenuPages(RoboPages):
    def __init__(self, source):
        super().__init__(source)

    @menus.button("\N{WHITE QUESTION MARK ORNAMENT}", position=menus.Last(5))
    async def show_bot_help(self, payload):
        """Shows how to use the bot"""

        embed = Embed(title="Argument Help Menu")

        entries = (
            ("<argument>", "This means the argument is __**required**__."),
            ("[argument]", "This means the argument is __**optional**__."),
            ("[A|B]", "This means that it can be __**either A or B**__."),
            (
                "[argument...]",
                "This means you can have multiple arguments.\n"
                "Now that you know the basics, it should be noted that...\n"
                "__**You do not type in the brackets!**__",
            ),
        )

        embed.add_field(
            name="How do I use this bot?",
            value="Reading the bot signature is pretty simple.",
        )

        for name, value in entries:
            embed.add_field(name=name, value=value, inline=False)

        embed.set_footer(
            text=f"We were on page {self.current_page + 1} before this message."
        )

        await self.message.edit(embed=embed)

        async def go_back_to_current_page():
            await asyncio.sleep(30.0)
            await self.show_page(self.current_page)

        self.bot.loop.create_task(go_back_to_current_page())



class buttons(commands.Cog):
    def __init__(self, bot):
        self.bot = bot



    @commands.command()
    async def login(self, ctx):
        """
        Simple confirmations with buttons
        """
        await View.start(ctx)


    @commands.command(name='gstart')
    async def giveaway_start(self, ctx, time : TimeConverter, *, prize : str):
        """
        Start a new giveaway.

        :warning: This is a new command in beta. Issues will arise.
        """

        delta = datetime.timedelta(seconds=time)
        timeconverter = precisedelta(
            delta, minimum_unit="seconds", suppress=["microseconds"]
        )

        embed = Embed(
            title="Giveaway!",
            description=f"**Time Left:** {timeconverter}\n**Prize:** {prize}",
            
        )

        item = discord.ui.Button(
            style=discord.ButtonStyle.green,
            label='Enter Giveaway',
            emoji='\U0001f389'
        )

        view = discord.ui.View()
        view.add_item(item=item)

        await ctx.send(embed=embed, view=view)


    @commands.command()
    @commands.max_concurrency(number=1, per=BucketType.user, wait=True)
    async def ping(self, ctx):

        start = time.perf_counter()
        m = await ctx.send('Pinging...')
        end = time.perf_counter()

        typing_ping = (end - start) * 1000

        start = time.perf_counter()
        await self.bot.info.upsert({"_id" : ctx.author.id, "info" : f"Ping command issued by {ctx.author}"})
        end = time.perf_counter()

        database_ping = (end - start) * 1000

        await self.bot.info.delete(ctx.author.id)

        await m.edit(content=f'Typing: {round(typing_ping, 1)} ms\nWebsocket: {round(self.bot.latency*1000)} ms\nDatabase: {round(database_ping, 1)} ms')


    @commands.command()
    async def menu(self, ctx):
        pages = ViewMenuPages(source=ButtonMenuSource(range(1, 100)), clear_reactions_after=True)
        await pages.start(ctx)



        
        







        











        




def setup(bot):
    bot.add_cog(buttons(bot))

