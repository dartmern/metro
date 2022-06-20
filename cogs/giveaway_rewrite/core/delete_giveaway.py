from bot import MetroBot

async def delete_giveaway(
    bot: MetroBot,
    message_id: int
    ):
    """Delete a giveaway object."""

    query = """
            DELETE FROM giveaway
            WHERE message_id = $1
            """
    await bot.db.execute(query, message_id)