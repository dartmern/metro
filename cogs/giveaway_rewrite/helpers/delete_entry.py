from bot import MetroBot

async def delete_entry(
    bot: MetroBot,
    message_id: int,
    author_id: int
    ):

    query = """
            DELETE FROM giveaway_entries
            WHERE message_id = $1
            AND author_id = $2
            """

    await bot.db.execute(query, message_id, author_id)

