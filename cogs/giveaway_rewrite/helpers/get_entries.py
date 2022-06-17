from bot import MetroBot

async def get_entires(
    bot: MetroBot,
    message_id: int
    ):
    """Get all the entires for a giveaway."""

    query = """
            SELECT * FROM giveaway_entries
            WHERE message_id = $1
            """
    return await bot.db.fetch(query, message_id)