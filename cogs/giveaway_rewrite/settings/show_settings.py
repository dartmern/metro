from bot import MetroBot

async def show_settings(
    bot: MetroBot,
    guild_id: int
    ):
    """Show giveaway settings for a guild id."""

    query = """
            SELECT * FROM giveaway_settings
            WHERE guild_id = $1
            """
    return await bot.db.fetchval(query, guild_id)