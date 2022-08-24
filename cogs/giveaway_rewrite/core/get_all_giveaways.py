from typing import Any, Union
from bot import MetroBot

import discord

async def get_all_giveaways(
    bot: MetroBot, 
    guild_id: int,
    ended: bool = False
    ) -> Union[Any, None]:
    """Get all the giveaways for an object."""   

    query = f"""
            SELECT (raw, winners, ends_at, channel_id, ended, requirements, message_id) FROM giveaway
            WHERE guild_id = $1 AND ended = {ended}
            """
    data = await bot.db.fetch(query, guild_id)
    return data