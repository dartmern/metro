from discord.ext import commands

from utils.constants import SUPPORT_GUILD

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

def is_support():
    def predicate(ctx):
        return ctx.author.id in ctx.bot.owner_ids or ctx.author.id in ctx.bot.support_staff
    return commands.check(predicate)
