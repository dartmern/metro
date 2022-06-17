import datetime
import typing
from bot import MetroBot

async def insert_giveaway(
    bot: MetroBot,
    guild_id: int,
    channel_id: int,
    message_id: int,
    ends_at: datetime.datetime,
    embed_raw: typing.Dict,
    winners: int
    ):
    """Insert a giveaway."""
    query = """
            INSERT INTO giveaway (guild_id, channel_id, message_id, ends_at, raw, winners)
            VALUES ($1, $2, $3, $4, $5, $6)
            """
    await bot.db.execute(query, guild_id, channel_id, message_id, ends_at, str(embed_raw), winners)
