import discord
from discord.ext import commands, menus

from typing import Optional
import re
import asyncio

from utils.custom_context import MyContext

PAGE_REGEX = r'(Page)?(\s)?((\[)?((?P<current>\d+)/(?P<last>\d+))(\])?)'

async def delete_silent(message: discord.Message, *, delay: Optional[float] = None):
    """Replaces the `silent` kwarg in edpy."""
    try:
        await message.delete(delay=delay)
    except discord.HTTPException:
        pass

class Embed(discord.Embed):
    def __init__(self, color=0x1ABC9C, fields=(), field_inline=False, **kwargs):
        super().__init__(color=color, **kwargs)
        for n, v in fields:
            self.add_field(name=n, value=v, inline=field_inline)

def dynamic_cooldown(ctx: MyContext):
    """Dyanmic cooldown for premium users."""

    if ctx.bot.premium_guilds.get(ctx.guild.id) or ctx.bot.premium_users.get(ctx.author.id):
        return commands.Cooldown(3, 6)
    return commands.Cooldown(3, 8)

