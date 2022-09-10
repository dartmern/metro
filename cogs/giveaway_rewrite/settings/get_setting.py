import typing

import discord
from bot import MetroBot

async def get_setting(
    bot: MetroBot,
    setting: str,
    guild_id: int
):
    """Get a setting and it's value."""

    query = f"""
            SELECT ({setting}) FROM giveaway_settings
            WHERE guild_id = $1
            """
    return await bot.db.fetchval(query, guild_id)


