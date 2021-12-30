from discord.ext import commands


SUPPORT_GUILD = 812143286457729055
TESTER_ROLE = 861141649265262592



def in_support():
    def predicate(ctx):
        try:
            return ctx.guild.id == SUPPORT_GUILD
        except:
            return False
    return commands.check(predicate)

def is_dev():
    def predicate(ctx):
        return ctx.author.id in ctx.bot.owner_ids or ctx.author == ctx.bot.owner_id
    return commands.check(predicate)

