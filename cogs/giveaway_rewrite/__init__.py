from bot import MetroBot
from utils.constants import TESTING_GUILD

from .giveaway_rewrite import giveaways2
from .context_menus.giveaway_end import end_giveaway_context_menu

async def setup(bot: MetroBot):
    bot.tree.add_command(end_giveaway_context_menu, guild=TESTING_GUILD)
    await bot.add_cog(giveaways2(bot))