import discord
from discord.ext import commands


def can_execute_action(ctx, user, target):
    return (
            user.id == ctx.bot.owner_id
            or user == ctx.guild.owner
            or user.top_role > target.top_role
    )





def is_tester():
    def predicate(ctx):
        role = ctx.guild.get_role(861141649265262592)
        if role in ctx.author.roles:
            return True
        else:
            raise commands.BadArgument('Pickup the tester role by typing `!tester` in my support server to use this.')
    return commands.check(predicate)

