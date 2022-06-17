from .giveaway_rewrite import giveaways2

async def setup(bot):
    await bot.add_cog(giveaways2(bot))