# R. Danny's help command paginator (menu).
# https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/meta.py

# Credits to Danny for making this



import discord
from discord.ext import commands, menus

from utils.useful import RoboPages


class SimplePages(RoboPages):
    """A simple pagination session reminiscent of the old Pages interface.
    Basically an embed with some normal formatting.
    """

    def __init__(self, source : menus.ListPageSource, *, ctx: commands.Context):
        super().__init__(source, ctx=ctx)
        self.embed = discord.Embed(colour=discord.Colour.blurple())


class SimplePageSource(menus.ListPageSource):
    async def format_page(self, menu, entries):
        pages = []
        for index, entry in enumerate(entries, start=menu.current_page * self.per_page):
            pages.append(str(entry))

        maximum = self.get_max_pages()
        if maximum > 1:
            footer = f'Page {menu.current_page + 1}/{maximum} ({len(self.entries)} entries)'
            menu.embed.set_footer(text=footer)

        menu.embed.description = '\n'.join(pages)
        return menu.embed

