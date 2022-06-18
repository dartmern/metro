from bot import MetroBot

async def delete_entires(
    bot: MetroBot,
    message_id: int
    ):
    """Delete all the entires from a giveaway."""

    query = """
            DELETE FROM giveaway_entries
            WHERE message_id = $1
            """
    await bot.db.execute(query, message_id)