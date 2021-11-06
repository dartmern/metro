import discord
from discord.ext import commands

SUPPORT_GUILD = 812143286457729055
TESTER_ROLE = 861141649265262592



def can_execute_action(ctx, user, target):
    return (
        user == ctx.guild.owner
            or user.top_role > target.top_role
    )

def check_dev(bot, user):
    return(
        user.id in bot.owner_ids
    )

def in_support():
    def predicate(ctx):
        return ctx.guild.id == SUPPORT_GUILD
    return commands.check(predicate)

def is_dev():
    def predicate(ctx):
        return ctx.author.id in ctx.bot.owner_ids or ctx.author == ctx.bot.owner_id
    return commands.check(predicate)






