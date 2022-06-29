import typing

import asyncpg
from bot import MetroBot

async def add_setting(
    bot: MetroBot,
    setting: typing.Literal['manager'],
    value: typing.Any,
    guild_id: int
    ):
    """Add a setting for giveaways."""

    query = f"""
            INSERT INTO giveaway_settings
            (guild_id, {setting})
            VALUES ($1, $2)
            """

    try:
        await bot.db.execute(query, guild_id, value)
    except asyncpg.exceptions.UniqueViolationError:
        backup_query = f"""
                        UPDATE giveaway_settings
                        SET {setting} = $1
                        WHERE guild_id = $2
                        """
        await bot.db.execute(backup_query, value, guild_id)