from bot import MetroBot
from utils.constants import TESTING_GUILD

from .giveaway_rewrite import giveaways
from .context_menus.giveaway_end import end_giveaway_context_menu
from .context_menus.giveaway_reroll import reroll_giveaway_context_menu

async def setup(bot: MetroBot):
    bot.tree.add_command(end_giveaway_context_menu)
    bot.tree.add_command(reroll_giveaway_context_menu)
    await bot.add_cog(giveaways(bot))