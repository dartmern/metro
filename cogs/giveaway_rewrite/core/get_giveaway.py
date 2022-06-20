from bot import MetroBot


async def get_giveaway(
    bot: MetroBot, 
    message_id: int
    ):
    """Get a giveaway from database."""
    
    query = """
            SELECT (raw, winners, ends_at, channel_id) FROM giveaway
            WHERE message_id = $1
            """
    return await bot.db.fetchval(query, message_id)


