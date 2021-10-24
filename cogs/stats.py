import discord
from discord.ext import commands





class stats(commands.Cog, description='Get bot stats and command stats.'):
    def __init__(self, bot):
        self.bot = bot


    @commands.Cog.listener()
    async def on_command_completion(self, ctx):

        try:
            ctx.bot.usage[ctx.command.qualified_name] += 1
        except:
            ctx.bot.usage[ctx.command.qualified_name] = 1



        


        




    
def setup(bot):
    bot.add_cog(stats(bot))
