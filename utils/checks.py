import discord
from discord.ext import commands


def can_execute_action(ctx, user, target):
    return (
        user == ctx.guild.owner
            or user.top_role > target.top_role
    )






