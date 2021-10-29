# R. Danny's tempblock command with few modifications
# https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/api.py

# Credits to Danny of course


import datetime
import asyncio

import discord
from discord.ext import commands
from utils.remind_utils import human_timedelta

from utils.useful import Embed
from utils import remind_utils


def can_block():
    def predicate(ctx):
        if ctx.guild is None:
            return False
        
        return ctx.channel.permissions_for(ctx.author).manage_channels

    return commands.check(predicate)

class block(commands.Cog, description=":mute: Manage your server by blocking/temp-blocking spammers."):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(name='block')
    @can_block()
    @commands.bot_has_permissions(manage_channels=True, send_messages=True)
    @commands.has_permissions(manage_channels=True, send_messages=True)
    async def block(self, ctx, member : discord.Member = commands.Option(default=None, description='member to block')):
        """
        Block a member from your channel.
        """
        if member is None:
            return await ctx.send("Please specify a member to block.")

        
        
        if member.top_role >= ctx.author.top_role:
            return



        reason = f'Blocked by {ctx.author} (ID: {ctx.author.id})'

        try:
            await ctx.channel.set_permissions(member, send_messages=False, add_reactions=False, reason=reason)
        except:
            return await ctx.cross()

        await ctx.check()


    @commands.command(name='unblock')
    @can_block()
    @commands.bot_has_permissions(manage_channels=True, send_messages=True)
    @commands.has_permissions(manage_channels=True, send_messages=True)
    async def unblock(self, ctx, member : discord.Member = commands.Option(default=None, description='member to unblock')):
        """
        Unblock a member from your channel.
        """
        if member is None:
            return await ctx.send("Please specify a member to unblock.")

        
        if member.top_role >= ctx.author.top_role:
            return

        reason = f'Unblocked by {ctx.author} (ID: {ctx.author.id})'

        try:
            await ctx.channel.set_permissions(member, send_messages=None, add_reactions=None, reason=reason)
        except:
            return await ctx.cross()

        await ctx.check()


    @commands.command(name='tempblock')
    @commands.bot_has_permissions(manage_channels=True, send_messages=True)
    @commands.has_permissions(manage_channels=True, send_messages=True)
    async def tempblock(self, ctx, duration : remind_utils.FutureTime, *, member : discord.Member):
        """Temporarily blocks a user from your channel.

        The duration can be a a short time form, e.g. 30d or a more human
        duration such as "until thursday at 3PM" or a more concrete time
        such as "2017-12-31".

        Note that times are in UTC.
        """

        
        if member.top_role >= ctx.author.top_role:
            return

        created_at = ctx.message.created_at

        reminder_cog = self.bot.get_cog('reminder')
        if reminder_cog is None:
            return await ctx.send('This function is not available at this time. Try again later.')

        timer = await reminder_cog.create_timer(
            duration.dt, 'tempblock', ctx.guild.id, ctx.author.id,
                                        ctx.channel.id, member.id,
                                        connection=self.bot.db,
                                        created=created_at


        )

        reason = f'Tempblocked by {ctx.author} (ID: {ctx.author.id}) until {duration.dt}'

        try:
            await ctx.channel.set_permissions(member, send_messages=False, add_reactions=False, reason=reason)
        except:
            return await ctx.cross()
        else:
            await ctx.send(f'Blocked {member} for {human_timedelta(duration.dt)}')

        
    @commands.Cog.listener()
    async def on_tempblock_timer_complete(self, timer):
        guild_id, mod_id, channel_id, member_id = timer.args

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            # RIP
            return

        channel = guild.get_channel(channel_id)
        if channel is None:
            # RIP x2
            return

        to_unblock = await self.bot.get_or_fetch_member(guild, member_id)
        if to_unblock is None:
            # RIP x3
            return

        moderator = await self.bot.get_or_fetch_member(guild, mod_id)
        if moderator is None:
            try:
                moderator = await self.bot.fetch_user(mod_id)
            except:
                # request failed somehow
                moderator = f'Mod ID {mod_id}'
            else:
                moderator = f'{moderator} (ID: {mod_id})'
        else:
            moderator = f'{moderator} (ID: {mod_id})'


        reason = f'Automatic unblock from timer made on {timer.created_at} by {moderator}.'

        
        try:
            await channel.set_permissions(to_unblock, send_messages=None, add_reactions=None, reason=reason)
        except:
            pass  




















def setup(bot):
    bot.add_cog(block(bot))