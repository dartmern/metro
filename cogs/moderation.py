import discord
from discord.ext import commands
from utils.context import MyContext
from utils.remind_utils import human_timedelta

from utils.converters import ActionReason, MemberConverter, MemberID

from typing import Optional
from collections import Counter

import typing
import datetime
import re
import humanize
from humanize.time import precisedelta

from utils import remind_utils


time_regex = re.compile(r"(\d{1,5}(?:[.,]?\d{1,5})?)([smhd])")
time_dict = {"h":3600, "s":1, "m":60, "d":86400}

class TimeConverter(commands.Converter):
    async def convert(self, ctx, argument):
        matches = time_regex.findall(argument.lower())
        time = 0
        for v, k in matches:
            try:
                time += time_dict[k]*float(v)
            except KeyError:
                raise commands.BadArgument("{} is an invalid time-key! h/m/s/d are valid!".format(k))
            except ValueError:
                raise commands.BadArgument("{} is not a number!".format(v))
        return time

class moderation(commands.Cog, description=":hammer: Moderation commands."):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(name="kick", brief="Kick a member from the server.")
    @commands.has_guild_permissions(kick_members=True)
    @commands.bot_has_permissions(send_messages=True, kick_members=True)
    async def kick_cmd(self,
                       ctx,
                       member : discord.Member,
                       *,
                       reason=None  
                       ):
        """
        Kicks a member from the server.\n
        Member must be in the server at the moment of running the command
        """

        try:
            await member.send(f"You were kicked from **{ctx.guild}** `{ctx.guild.id}`\n\nModerator: **{ctx.author}** `{ctx.author.id}`\nReason: **{reason}**")
        except:
            pass
        await member.kick(reason=reason)
        await ctx.send(f"Kicked **{member}**")


    @commands.command(
        name="ban",
        brief="Ban a member from the server.",
        usage="<member> [reason]"
    )
    @commands.has_guild_permissions(ban_members=True)
    @commands.bot_has_permissions(send_messages=True, ban_members=True)
    async def ban_cmd(
            self,
            ctx,
            member : discord.User,
            *,
            reason : str = None
    ):
        """
        Ban a member from the server.\n
        Member doesn't need to be in the server. Can be a mention, name or id.
        """

        reason_1 = reason

        reason = f"Action requested by {ctx.author} (ID: {ctx.author.id}).\nReason: {reason_1}"

        try:
            await ctx.guild.ban(member, reason=reason)
        except:
            raise commands.BadArgument(f"An error occurred while invoking the `ban` command. ")


        try:
            await member.send(
                f"You were banned from **{ctx.guild}** `{ctx.guild.id}`\n\nModerator: **{ctx.author}** `{ctx.author.id}`\nReason: **{reason_1}**")
        except:
            pass


        await ctx.send(f"Banned **{member}**")


    @commands.command(name="unban",
                      brief="Unban a previously banned member.",
                      usage="<member>")
    @commands.has_guild_permissions(ban_members=True)
    @commands.bot_has_permissions(send_messages=True, ban_members=True)
    async def unban_cmd(
            self,
            ctx : MyContext,
            member : discord.User,
            reason : str = None
    ):
        """
        Unbans an user from the server.
        Raises an error if the user is not a previously banned member."""

        bans = await ctx.guild.bans()
        for ban in bans:
            user = ban.user
            if user.id == member.id:
                await ctx.guild.unban(user, reason=reason)
                await ctx.send(f"Unbanned **{user}**")
                return
        raise commands.BadArgument(
            "**" + member.name + "** was not a previously banned member."
        )

    @commands.command(name='multiban',usage="[users]... [reason]")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(send_messages=True, ban_members=True)
    async def _multiban(self, ctx, members : commands.Greedy[MemberID], *, reason : ActionReason = None):
        """
        Ban multiple people from the server.
        
        For this to work you need to input user ids and user ids only.
        """

        if reason is None:
            reason = f"Action requested by {ctx.author} (ID: {ctx.author.id})\nReason: No reason provided."

        total_members = len(members)
        if total_members == 0:
            return await ctx.send('Please input member ids.')

        confirm = await ctx.confirm(f'This will ban **{total_members}** members. Are you sure about that?',timeout=30)

        if confirm is None:
            return await ctx.send('Timed out.')

        if confirm is False:
            return await ctx.send('Canceled.')

        fails = 0
        for member in members:
            try:
                await ctx.guild.ban(member, reason=reason)
            except:
                fails += 1

        await ctx.send(f'Banned {total_members-fails}/{total_members} members.')



    @commands.command(
        name="lockdown",
        brief="Lockdown a channel.",
        usage="[channel]",
        aliases=["lock"]
    )
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(send_messages=True, manage_channels=True)
    async def lockdown_cmd(self,
                           ctx,
                           channel : discord.TextChannel = None):
        """
        Locks down a channel by changing permissions for the default role.
        This will not work if your server is set up improperly
        """

        channel = channel or ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(f"{self.bot.check} Locked down **{channel.name}**.")


    @commands.command(
        name="unlockdown",
        brief="Unlock a channel.",
        usage="[channel]",
        aliases=["unlock"]
    )
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(send_messages=True, manage_channels=True)
    async def unlockdown_cmd(self,
                           ctx,
                           channel: discord.TextChannel = None):
        """
        Unlocks down a channel by changing permissions for the default role.
        This will not work if your server is set up improperly
        """

        channel = channel or ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = None
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        await ctx.send(f"{self.bot.check} Unlocked **{channel.name}**.")


    @commands.command()
    @commands.bot_has_permissions(send_messages=True)
    async def cleanup(self, ctx, amount: int=5):
        """
        Cleans up the bot's messages. 
        Defaults to 25 messages. If you or the bot doesn't have `manage_messages` permission, the search will be limited to 25 messages.
        """
        if amount > 25:
            if not ctx.channel.permissions_for(ctx.author).manage_messages:
                await ctx.send("You must have `manage_messages` permission to perform a search greater than 25")
                return
            if not ctx.channel.permissions_for(ctx.me).manage_messages:
                await ctx.send("I need the `manage_messages` permission to perform a search greater than 25")
                return

        def check(msg):
            return msg.author == ctx.me
        if ctx.channel.permissions_for(ctx.me).manage_messages:
            deleted = await ctx.channel.purge(limit=amount, check=check)
        else:
            deleted = await ctx.channel.purge(limit=amount, check=check, bulk = False)
        spammers = Counter(m.author.display_name for m in deleted)
        deleted = len(deleted)
        messages = [f'{deleted} message{" was" if deleted == 1 else "s were"} removed.']
        if deleted:
            messages.append('')
            spammers = sorted(spammers.items(), key=lambda t: t[1], reverse=True)
            messages.extend(f'**{name}**: {count}' for name, count in spammers)

        to_send = '\n'.join(messages)
        if len(to_send) > 2000:
            await ctx.send(f'Successfully removed {deleted} messages.', delete_after=10)
        else:
            await ctx.send(to_send, delete_after=10)



    @commands.command(aliases=['sm'])
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_permissions(send_messages=True, manage_channels=True)
    async def slowmode(self, ctx, time : TimeConverter=None):
        """Change the slowmode for the current channel."""

        if time:
            delta = datetime.timedelta(seconds=int(time))
            timeconverter = precisedelta(
                delta, minimum_unit="seconds", suppress=["microseconds"]
            )
            if time < 21601:
                await ctx.channel.edit(slowmode_delay=int(time))
                await ctx.send(f"Set the slowmode delay to `{timeconverter}`")



        else:
            await ctx.channel.edit(slowmode_delay=0)
            await ctx.send(f"Removed the slowmode for this channel")


    @commands.command()
    @commands.has_permissions(ban_members=True, send_messages=True)
    @commands.bot_has_permissions(ban_members=True, send_messages=True)
    async def tempban(self, ctx, member : discord.User, duration : remind_utils.FutureTime, *, reason : ActionReason):
        """Temporarily bans a member for the specified duration.

        The duration can be a a short time form, e.g. 30d or a more human
        duration such as "until thursday at 3PM" or a more concrete time
        such as "2024-12-31".

        Note that times are in UTC.
        """

        if reason is None:
            reason = f'Action requested by: {ctx.author} (ID: {ctx.author.id})'
        
        reminder_cog = self.bot.get_cog('reminder')
        if reminder_cog is None:
            return await ctx.send('This function is not available at this time. Try again later.')

        until = f"for {human_timedelta(duration.dt)}"
        heads_up = f"You have been banned from {ctx.guild.name} {until}. \n{reason}"

        try:
            await member.send(heads_up)
        except (AttributeError, discord.HTTPException):
            pass

        await ctx.guild.ban(member, reason=reason)

        timer = await reminder_cog.create_timer(duration.dt, 'tempban', ctx.guild.id,
                                                                    ctx.author.id,
                                                                    member.id,
                                                                    connection=self.bot.db,
                                                                    created=ctx.message.created_at
        )
        
        await ctx.send(f'Tempbanned {member} {until}')


    @commands.Cog.listener()
    async def on_tempban_timer_complete(self, timer):
        guild_id, mod_id, member_id = timer.args
        print('b4')
        await self.bot.wait_until_ready()
        print('co')

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            # RIP
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

        reason = f'Automatic unban from timer made on {timer.created_at} by {moderator}.'
        await guild.unban(discord.Object(id=member_id), reason=reason)


        















def setup(bot):
    bot.add_cog(moderation(bot))