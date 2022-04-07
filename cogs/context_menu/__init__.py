from bot import MetroBot
from .context_menu import AdvancedPoll

async def setup(bot: MetroBot):
    await bot.add_cog(AdvancedPoll(bot))