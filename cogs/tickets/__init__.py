from .tickets import tickets

from bot import MetroBot

async def setup(bot: MetroBot):
    await bot.add_cog(tickets(bot))
