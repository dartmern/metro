import typing

import discord
from bot import MetroBot

from mee6_py_api import API

async def validate_entry(
    bot: MetroBot,
    entry: typing.Any,
    role_req: typing.List[discord.Role],
    bypass_req: typing.List[discord.Role],
    blacklist_req: typing.List[discord.Role],
    mee6_level: int,
    guild: discord.Guild
    ):
    """Validate an entry."""

    author = guild.get_member(entry['author_id'])
    mee6api = API(guild.id)
    
    level = await mee6api.levels.get_user_level(author.id)
    if level >= mee6_level:
        pass
    else:
        return False

    if set(role_req).issubset(map(lambda x: x.id, author.roles)):
        pass
    else:
        if any(item in bypass_req for item in author.roles):
            pass # req passed by bypass role
        else:
            return False

    if any(item in blacklist_req for item in map(lambda x: x.id, author.roles)):
        return False
    return True

