from bot import MetroBot


async def get_giveaway(
    bot: MetroBot, 
    guild_id: int,
    channel_id: int, 
    message_id: int
    ):
    """Get a giveaway from database."""
    
    query = """
            SELECT (raw, winners) FROM giveaway
            WHERE guild_id = $1
            AND channel_id = $2
            AND message_id = $3
            """
    return await bot.db.fetchval(query, guild_id, channel_id, message_id)


