from typing import Union
import discord
from discord.ext import commands
from .constants import SUPPORT_GUILD

from utils.custom_context import MyContext

def check_support(ctx: MyContext):
    return (
        ctx.author.id in ctx.bot.support
    )

async def can_execute_role_action(ctx: MyContext, user: discord.Member, target: discord.Member, role: discord.Role):

    if role.position >= ctx.guild.me.top_role.position:
        to_send = ""
        to_send += (
                f"\🔴 I am unable to add/remove/modify this role due to discord hierarchy rules."
                f"\nMy top role's position ({ctx.guild.me.top_role.mention}) is lower than `@{role.name}`"
                f"\n\nMy top role position: {ctx.guild.me.top_role.position} • `@{role.name}` position: {role.position}"
                f"\n\nPlease move my top role higher to make this command work!"
        )
        await ctx.send(to_send)
        return False

    if user == ctx.guild.owner or user.top_role > target.top_role:
        return True

    return False

async def can_execute_role_edit(ctx: MyContext, role: discord.Role):
    if role.position >= ctx.guild.me.top_role.position:
        to_send = ""
        to_send += (
                f"\🔴 I am unable to add/remove/modify this role due to discord hierarchy rules."
                f"\nMy top role's position ({ctx.guild.me.top_role.mention}) is lower than `@{role.name}`"
                f"\n\nMy top role position: {ctx.guild.me.top_role.position} • `@{role.name}` position: {role.position}"
                f"\n\nPlease move my top role higher to make this command work!"
        )
        await ctx.send(to_send)
        return False

    if ctx.author == ctx.guild.owner or ctx.author.top_role.position > role.position:
        return True
    return False

async def can_bot_execute_role_action(ctx: MyContext, role: discord.Role):
    if role.position >= ctx.guild.me.top_role.position:
        to_send = ""
        to_send += (
                f"\🔴 I am unable to add/remove/modify this role due to discord hierarchy rules."
                f"\nMy top role's position ({ctx.guild.me.top_role.mention}) is lower than `@{role.name}`"
                f"\n\nMy top role position: {ctx.guild.me.top_role.position} • `@{role.name}` position: {role.position}"
                f"\n\nPlease move my top role higher to make this command work!"
        )
        await ctx.send(to_send)
        return False
    return True

def can_execute_action(ctx : MyContext, user : discord.Member, target : discord.Member):
    return (
        user == ctx.guild.owner
            or user.top_role > target.top_role
    )

def check_dev(bot, user : Union[discord.Member, discord.User]):
    return(
        user.id in bot.owner_ids
    )
    
def in_support():
    def predicate(ctx: MyContext):
        try:
            return ctx.guild.id == SUPPORT_GUILD
        except:
            return False
    return commands.check(predicate)

def is_dev():
    def predicate(ctx: MyContext):
        return ctx.author.id in ctx.bot.owner_ids or ctx.author == ctx.bot.owner_id
    return commands.check(predicate)

def is_support():
    def predicate(ctx: MyContext):
        return ctx.author.id in ctx.bot.owner_ids or ctx.author.id in ctx.bot.support_staff
    return commands.check(predicate)
