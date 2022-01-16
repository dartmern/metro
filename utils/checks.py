from typing import Union
import discord
from discord.ext import commands
from utils.constants import SUPPORT_ROLE


from utils.custom_context import MyContext

SUPPORT_GUILD = 812143286457729055
TESTER_ROLE = 861141649265262592

def check_support(ctx):
    return (
        ctx.author.id in ctx.bot.support
    )

def can_execute_action(ctx : MyContext, user : discord.Member, target : discord.Member):
    return (
        user == ctx.guild.owner
            or user.top_role > target.top_role
    )

def check_dev(bot, user : Union[discord.Member, discord.User]):
    return(
        user.id in bot.owner_ids
    )

def check_tester(ctx : MyContext):
    guild = ctx.bot.get_guild(SUPPORT_GUILD)
    role = guild.get_role(TESTER_ROLE)
    if ctx.author in role.members:
        return True
        






