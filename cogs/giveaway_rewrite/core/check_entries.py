import typing

import discord
from bot import MetroBot

async def check_entries(
    bot: MetroBot,
    entries: typing.List,
    role_req: typing.List[discord.Role],
    bypass_req: typing.List[discord.Role],
    blacklist_req: typing.List[discord.Role]
    ):
    """Check if entries are valid."""
    pass
