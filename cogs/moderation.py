import discord
from discord.ext import commands
from utils.context import MyContext
from utils.remind_utils import UserFriendlyTime, human_timedelta

from utils.converters import ActionReason, MemberConverter, MemberID
from utils.checks import can_execute_action

from typing import Optional, Union
from collections import Counter

import typing
import json
import datetime
import re
import humanize
from humanize.time import precisedelta

from utils import remind_utils
from utils.useful import Embed


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
                       ctx : MyContext,
                       member : discord.Member,
                       *,
                       reason : Optional[str] = None  
                       ):
        """
        Kicks a member from the server.\n
        Member must be in the server at the moment of running the command
        """
        action_converter = ActionReason()
        converted_action = await action_converter.convert(ctx, reason)

        if reason is None:
            real_reason = ''
        else:
            real_reason = f'Reason: {reason}'

        if member == ctx.author:
            return await ctx.send('You cannot kick yourself.')

        if not can_execute_action(ctx, ctx.author, member):
            return await ctx.send('You are not high enough in role hierarchy to ban this member.')

        embed = Embed()
        embed.description = (
            f'You were kicked from **{ctx.guild.name}** by {ctx.author}'
        )

        if real_reason == '':
            pass
        else:
            embed.set_footer(text=real_reason)

        try:
            await member.send(embed=embed)
            success = '✅'
        except discord.HTTPException:
            success = '❌'

        await ctx.guild.kick(member, reason=converted_action)

        embed = Embed()
        embed.description = f'**{ctx.author.mention}** has kicked **{member}**'
        embed.set_footer(text=f'ID: {member.id} | DM successful: {success}')

        await ctx.send(embed=embed)
        

    @commands.command(
        name="ban",
        brief="Ban a member from the server."
    )
    @commands.has_guild_permissions(ban_members=True)
    @commands.bot_has_permissions(send_messages=True, ban_members=True)
    async def ban_cmd(
            self,
            ctx : MyContext,
            member : Union[discord.Member, discord.User],
            delete_days : Optional[int] = 0,
            *,
            reason : Optional[str] = None
    ):
        """
        Ban a member from the server.\n
        Member doesn't need to be in the server. Can be a mention, name or id.
        """
        action_converter = ActionReason()
        converted_action = await action_converter.convert(ctx, reason)

        if reason is None:
            real_reason = ''
        else:
            real_reason = f'Reason: {reason}'
        
        if delete_days and 7 < delete_days < 0:
            return await ctx.send('`delete_days` must be less than or equal to 7 days.')

        if member == ctx.author:
            return await ctx.send(f'{self.bot.cross} You cannot ban yourself!')
        if isinstance(member, discord.Member):
            if not can_execute_action(ctx, ctx.author, member):
                return await ctx.send('You are not high enough in role hierarchy to ban this member.')

            embed = Embed()
            embed.description = f'You were banned from **{ctx.guild.name}** by {ctx.author}'

            if real_reason == '':
                pass
            else:
                embed.set_footer(text=f'Reason: {reason[0:100]}')
            
            try:
                await member.send(embed=embed)
                success = '✅'
            except discord.HTTPException:
                success = '❌'

        else:
            success = '❌'


        embed = Embed()
        embed.description = f'**{ctx.author.mention}** has banned **{member}**\n{real_reason}'
        embed.set_footer(text=f'ID: {member.id} | DM successful: {success}')

        await ctx.guild.ban(member, reason=converted_action, delete_message_days=delete_days)

        await ctx.send(embed=embed)
          


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

    @commands.command(name='multiban',usage="[users...] [reason]")
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
            return await ctx.help()

        confirm = await ctx.confirm(f'This will ban **{total_members}** members. Are you sure about that?',timeout=30)

        if confirm is None:
            return await ctx.send('Timed out.')

        if confirm is False:
            return await ctx.send('Canceled.')
        
        d = await ctx.send("Banning...")

        fails = 0
        for member in members:
            try:
                await ctx.guild.ban(member, reason=reason)
            except:
                fails += 1

        await d.delete(silent=True)
        await ctx.send(f'Banned {total_members-fails}/{total_members} members.')



    @commands.command(
        name="lockdown",
        brief="Lockdown a channel.",
        aliases=["lock"]
    )
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(send_messages=True, manage_channels=True)
    async def lockdown_cmd(self,
                           ctx : MyContext,
                           channel : Optional[discord.TextChannel] = None,
                           *,
                           duration : UserFriendlyTime(
                               commands.clean_content, default='\u2026'
                           ) = None):
        """
        Locks down a channel by changing permissions for the default role.
        This will not work if your server is set up improperly
        """
        channel = channel or ctx.channel
        await ctx.trigger_typing()

        if not channel.permissions_for(ctx.guild.me).read_messages:
            raise commands.BadArgument(
                f"I need to be able to read messages in {channel.mention}"
            )
        if not channel.permissions_for(ctx.guild.me).send_messages:
            raise commands.BadArgument(
                f"I need to be able to send messages in {channel.mention}"
            )

        query = """
                SELECT (id)
                FROM reminders
                WHERE event = 'lockdown'
                AND EXTRA->'kwargs'->>'channel_id' = $1; 
                """
        data = await self.bot.db.fetchval(query, str(channel.id))
        if data:
            raise commands.BadArgument(f"Channel {channel.mention} is already locked.")
        
        overwrites = channel.overwrites_for(ctx.guild.default_role)
        perms = overwrites.send_messages
        if perms is False:
            raise commands.BadArgument(f"Channel {channel.mention} is already locked.")

        reminder_cog = self.bot.get_cog('reminder')
        if not reminder_cog:
            raise commands.BadArgument(f'This feature is currently unavailable.')

        message = await ctx.send(f'Locking {channel.mention} ...')
        bot_perms = channel.overwrites_for(ctx.guild.me)
        if not bot_perms.send_messages:
            bot_perms.send_messages = True
            await channel.set_permissions(
                ctx.guild.me, overwrite=bot_perms, reason="For channel lockdown."
            )

        endtime = duration.dt.replace(tzinfo=None) if duration and duration.dt else None

        if endtime:

            timer = await reminder_cog.create_timer(
                endtime,
                "lockdown",
                ctx.guild.id,
                ctx.author.id,
                ctx.channel.id,
                perms=perms,
                channel_id=channel.id,
                connection=self.bot.db,
                created=ctx.message.created_at.replace(tzinfo=None)
            )
        overwrites.send_messages = False
        reason = "Channel locked by command."
        await channel.set_permissions(
            ctx.guild.default_role,
            overwrite=overwrites,
            reason=await ActionReason().convert(ctx, reason),
        )

        if duration and duration.dt:
            timefmt = human_timedelta(endtime)
        else:
            timefmt = None
        
        ft = f" for {timefmt}" if timefmt else ""
        await message.edit(
            content=f'{self.bot.check} Channel {channel.mention} locked{ft}'
        )


    @commands.command(
        name="unlockdown",
        brief="Unlock a channel.",
        aliases=["unlock"]
    )
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(send_messages=True, manage_channels=True)
    async def unlockdown_cmd(self,
                           ctx : MyContext,
                           channel: discord.TextChannel = None):
        """
        Unlocks down a channel by changing permissions for the default role.
        This will not work if your server is set up improperly
        """

        channel = channel or ctx.channel

        await ctx.trigger_typing()
        if not channel.permissions_for(ctx.guild.me).read_messages:
            raise commands.BadArgument(
                f"I need to be able to read messages in {channel.mention}"
            )
        if not channel.permissions_for(ctx.guild.me).send_messages:
            raise commands.BadArgument(
                f"I need to be able to send messages in {channel.mention}"
            )

        query = """
                SELECT (id, extra)
                FROM reminders
                WHERE event = 'lockdown'
                AND extra->'kwargs'->>'channel_id' = $1;
                """
        s = await self.bot.db.fetchval(query, str(channel.id))
        if not s:
            overwrites = channel.overwrites_for(ctx.guild.default_role)
            perms = overwrites.send_messages
            if perms is True:
                return await ctx.send(f"Channel {channel.mention} is already unlocked.")
            else:
                pass   
        else:
            pass
           

        message = await ctx.send(f"Unlocking {channel.mention} ...")
        if s:
            task_id = s[0]
            args_and_kwargs = json.loads(s[1])
            perms = args_and_kwargs["kwargs"]["perms"]
            

            query = """
                    DELETE FROM reminders
                    WHERE id = $1
                    """
            await self.bot.db.execute(query, task_id)
        reason = "Channel unlocked by command execution."

        overwrites = channel.overwrites_for(ctx.guild.default_role)
        overwrites.send_messages = None
        await channel.set_permissions(
            ctx.guild.default_role,
            overwrite=overwrites,
            reason=await ActionReason().convert(ctx, reason),
        )
        await message.edit(
            content=f"{self.bot.check} Channel {channel.mention} unlocked."
        )


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
            await ctx.send(f'Successfully removed {deleted} messages.', delete_after=5)
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
    async def tempban(self, ctx, member : discord.Member, duration : remind_utils.FutureTime, *, reason : Optional[str] = None):
        """Temporarily bans a member for the specified duration.

        The duration can be a a short time form, e.g. 30d or a more human
        duration such as "until thursday at 3PM" or a more concrete time
        such as "2024-12-31".

        Note that times are in UTC.
        """
        action_converter = ActionReason()
        converted_action = await action_converter.convert(ctx, reason)

        if reason is None:
            real_reason = ''
        else:
            real_reason = f'Reason: {reason}'

        
        reminder_cog = self.bot.get_cog('reminder')
        if reminder_cog is None:
            return await ctx.send('This function is not available at this time. Try again later.')
        
        delta = human_timedelta(duration.dt - datetime.timedelta(seconds=3))
        until = f"for {delta}"

        if member == ctx.author:
            return await ctx.send(f'{self.bot.cross} You cannot ban yourself!')
        if not can_execute_action(ctx, ctx.author, member):
            return await ctx.send(f'You are not high enough in role hierarchy to ban this member.')

        embed = Embed()
        embed.description = (f'You were tempbanned from **{ctx.guild.name}**'
                                f'\nDuration: {delta}'
                                f'\nAction requested by: {ctx.author} (ID: {ctx.author.id})'
        )
      
        if real_reason == '':
            pass
        else:
            embed.set_footer(text=f'{real_reason}')

        try:
            await member.send(embed=embed)
            success = '✅'
        except discord.HTTPException:
            success = '❌'

        await ctx.guild.ban(member, reason=converted_action)

        timer = await reminder_cog.create_timer(duration.dt, 'tempban', ctx.guild.id,
                                                                    ctx.author.id,
                                                                    member.id,
                                                                    connection=self.bot.db,
                                                                    created=ctx.message.created_at
        )

        embed = Embed()
        embed.description = f'**{ctx.author.mention}** has tempbanned **{member}**\nDuration: {delta}\n{real_reason}'
        embed.set_footer(text=f'ID: {member.id} | DM successful: {success}')
        
        await ctx.send(embed=embed)


    @commands.Cog.listener()
    async def on_tempban_timer_complete(self, timer):
        guild_id, mod_id, member_id = timer.args

        await self.bot.wait_until_ready()

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
        try:
            await guild.unban(discord.Object(id=member_id), reason=reason)
        except discord.errors.NotFound:
            pass


    @commands.Cog.listener()
    async def on_lockdown_timer_complete(self, timer):
        await self.bot.wait_until_ready()
        guild_id, mod_id, channel_id = timer.args
        perms = timer.kwargs["perms"]

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            # RIP
            return

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            # RIP
            return

        moderator = guild.get_member(mod_id)
        if moderator is None:
            try:
                moderator = await self.bot.fetch_user(mod_id)
            except:
                # request failed somehow
                moderator = f"Mod ID {mod_id}"
            else:
                moderator = f"{moderator} (ID: {mod_id})"
        else:
            moderator = f"{moderator} (ID: {mod_id})"

        reason = (
            f"Automatic unlock from timer made on {timer.created_at} by {moderator}."
        )
        overwrites = channel.overwrites_for(guild.default_role)
        overwrites.send_messages = perms
        await channel.set_permissions(
            guild.default_role,
            overwrite=overwrites,
            reason=reason,
        )
        















def setup(bot):
    bot.add_cog(moderation(bot))