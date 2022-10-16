from bot import MetroBot
from .tags import tags

async def setup(bot: MetroBot):
    await bot.add_cog(tags(bot))