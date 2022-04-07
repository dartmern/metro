from .customcommand import *

async def setup(bot):
    await bot.add_cog(customcommands(bot))