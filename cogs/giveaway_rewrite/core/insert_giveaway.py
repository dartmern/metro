import datetime
import json
import typing
from bot import MetroBot

async def insert_giveaway(
    bot: MetroBot,
    guild_id: int,
    channel_id: int,
    message_id: int,
    ends_at: datetime.datetime,
    embed_raw: typing.Dict,
    winners: int,
    requirements: typing.Dict
    ):
    """Insert a giveaway."""
    query = """
            INSERT INTO giveaway (guild_id, channel_id, message_id, ends_at, raw, winners, ended, requirements)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            """
    requirements = json.dumps(requirements, default=str)

    await bot.db.execute(
        query, 
        guild_id, 
        channel_id, 
        message_id, 
        ends_at, 
        str(embed_raw), 
        winners, 
        False, 
        str(requirements)
        )
