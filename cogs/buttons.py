
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

import datetime
from utils.remind_utils import format_relative
from dateutil.relativedelta import relativedelta
class plural:
    def __init__(self, value):
        self.value = value

    def __format__(self, format_spec):
        v = self.value
        singular, sep, plural = format_spec.partition("|")
        plural = plural or f"{singular}s"
        if abs(v) != 1:
            return f"{v} {plural}"
        return f"{v} {singular}"

def human_timedelta(dt, *, source=None, accuracy=3, brief=False, suffix=True):
    now = source or discord.utils.utcnow()
    # Microsecond free zone
    now = now.replace(microsecond=0, tzinfo=datetime.timezone.utc)
    dt = dt.replace(microsecond=0, tzinfo=datetime.timezone.utc)

    # This implementation uses relativedelta instead of the much more obvious
    # divmod approach with seconds because the seconds approach is not entirely
    # accurate once you go over 1 week in terms of accuracy since you have to
    # hardcode a month as 30 or 31 days.
    # A query like "11 months" can be interpreted as "!1 months and 6 days"
    if dt > now:
        delta = relativedelta(dt, now)
        suffix = ""
    else:
        delta = relativedelta(now, dt)
        suffix = " ago" if suffix else ""

    attrs = [
        ("year", "y"),
        ("month", "mo"),
        ("day", "d"),
        ("hour", "h"),
        ("minute", "m"),
        ("second", "s"),
    ]

    output = []
    for attr, brief_attr in attrs:
        elem = getattr(delta, attr + "s")
        if not elem:
            continue

        if attr == "day":
            weeks = delta.weeks
            if weeks:
                elem -= weeks * 7
                if not brief:
                    output.append(format(plural(weeks), "week"))
                else:
                    output.append(f"{weeks}w")

        if elem <= 0:
            continue

        if brief:
            output.append(f"{elem}{brief_attr}")
        else:
            output.append(format(plural(elem), attr))

    if accuracy is not None:
        output = output[:accuracy]

    if len(output) == 0:
        return "now"
    else:
        if not brief:
            return human_join(output, final="and") + suffix
        else:
            return " ".join(output) + suffix


def human_join(seq, delim=", ", final="or"):
    size = len(seq)
    if size == 0:
        return ""

    if size == 1:
        return seq[0]

    if size == 2:
        return f"{seq[0]} {final} {seq[1]}"

    return delim.join(seq[:-1]) + f" {final} {seq[-1]}"

class Arguments(argparse.ArgumentParser):
    def error(self, message):
        raise RuntimeError(message)






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

from utils.pages import ExtraPages
from discord.ext import menus

class MenuSource(menus.ListPageSource):
    def __init__(self, entries, *, per_page : int = 10):
        super().__init__(entries=entries, per_page=per_page)

    async def format_page(self, menu, entries):
        maximum = self.get_max_pages()

        new_e = []
        for x in entries:
            new_e.append(str(x))

        embed = discord.Embed(description="\n".join(new_e))
        embed.set_footer(text=f'Page [{menu.current_page + 1}/{maximum}]')
        return embed

class buttons(commands.Cog, description='Button related stuff. (and some secret testing...)'):
    def __init__(self, bot):
        self.bot = bot



    @commands.command()
    async def saydd(self, ctx, *, message : str):
        """
        A more advanced echo/say command with variables. Run `[p]help sayd` for more info.
        """
        pass



    


    










        
        







        











        




def setup(bot):
    bot.add_cog(buttons(bot))

