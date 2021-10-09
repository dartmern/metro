import datetime
import asyncio

import discord
from discord.ext import commands
from cogs.buttons import human_timedelta

from utils.useful import Embed



def can_block():
    def predicate(ctx):
        if ctx.guild is None:
            return False
        
        return ctx.channel.permissions_for(ctx.author).manage_channels

    return commands.check(predicate)

class block(commands.Cog, description="Manage your server by blocking/temp-blocking spammers."):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(name='block',slash_command=True)
    @can_block()
    @commands.bot_has_permissions(manage_channels=True, send_messages=True)
    @commands.bot_has_permissions(manage_channels=True, send_messages=True)
    async def block(self, ctx, member : discord.Member = commands.Option(default=None, description='member to block')):
        """
        Block a member from your channel.
        """



        reason = f'Blocked by {ctx.author} (ID: {ctx.author.id})'

        try:
            await ctx.channel.set_permissions(member, send_messages=False, add_reactions=False, reason=reason)
        except:
            return await ctx.send(f'Failed to block `{member}`')

        await ctx.send(f'Blocked `{member}`')


    @commands.command(name='unblock',slash_command=True)
    @can_block()
    @commands.bot_has_permissions(manage_channels=True, send_messages=True)
    @commands.bot_has_permissions(manage_channels=True, send_messages=True)
    async def unblock(self, ctx, member : discord.Member = commands.Option(default=None, description='member to unblock')):
        """
        Unblock a member from your channel.
        """

        reason = f'Unblocked by {ctx.author} (ID: {ctx.author.id})'

        try:
            await ctx.channel.set_permissions(member, send_messages=None, add_reactions=None, reason=reason)
        except:
            return await ctx.send(f'Failed to unblock `{member}`')

        await ctx.send(f'Unblocked `{member}`')













def setup(bot):
    bot.add_cog(block(bot))