from bot import MetroBot
from .nsfw import NSFW

async def setup(bot: MetroBot):
    await bot.add_cog(NSFW(bot))