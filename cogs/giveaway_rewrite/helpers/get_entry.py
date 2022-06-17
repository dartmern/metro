from bot import MetroBot


async def get_entry(
    bot: MetroBot,
    message_id: int,
    author_id: int,

    ):
    """Get a giveaway entry."""

    query = """
            SELECT * FROM giveaway_entries
            WHERE message_id = $1
            AND author_id = $2
            """
    return await bot.db.fetchval(query, message_id, author_id)