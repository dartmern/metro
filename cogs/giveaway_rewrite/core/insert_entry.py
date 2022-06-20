from bot import MetroBot


async def insert_entry(
    bot: MetroBot,
    message_id: int,
    author_id: int
    ):
    """Insert a entry for a giveaway."""

    query = """
            INSERT INTO giveaway_entries (message_id, author_id)
            VALUES ($1, $2)
            """
    return await bot.db.execute(query, message_id, author_id)