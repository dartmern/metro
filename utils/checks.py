import discord
from discord.ext import commands


def can_execute_action(ctx, user, target):
    return (
            user.id == ctx.bot.owner_id
            or user == ctx.guild.owner
            or user.top_role > target.top_role
    )





def is_a_tester():
    def predicate(ctx):

        author = ctx.author
        guild = ctx.bot.get_guild(812143286457729055)

        dev_role = discord.utils.get(guild.roles, id=861141649265262592)

        if not author in guild.members:
            return False

        else:

            if dev_role in author.roles:
                return True

            else:

                return False

    return commands.check(predicate)

