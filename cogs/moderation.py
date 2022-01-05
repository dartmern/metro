import asyncio
import shlex
import discord
import copy

from discord.ext import commands
from bot import MetroBot
from utils.custom_context import MyContext
from utils.remind_utils import FutureTime, UserFriendlyTime, human_timedelta

from utils.converters import ActionReason, MemberID
from utils.checks import SUPPORT_GUILD, can_execute_action

from typing import Dict, Optional, Union
from collections import Counter

import pytz
import json
import datetime
import re
import argparse
import asyncpg
from humanize.time import precisedelta

from utils import remind_utils
from utils.useful import Cooldown, Embed

SUPPORT_ROLE = 814018291353124895

def can_block():
    def predicate(ctx : MyContext):
        if ctx.guild is None:
            return False
        
        if ctx.channel.permissions_for(ctx.author).manage_channels:
            return True
        if ctx.guild.id == SUPPORT_GUILD and SUPPORT_ROLE in map(lambda x: x.id, ctx.author.roles):
            return True

    return commands.check(predicate)


class Arguments(argparse.ArgumentParser):
    def error(self, message):
        raise RuntimeError(message)


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

class MuteRoleView(discord.ui.View):
    def __init__(self, ctx : MyContext, role_id : int):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.role_id = role_id

    async def interaction_check(self, interaction):
        if self.ctx.author.id == interaction.user.id:
            return True
        else:
            await interaction.response.send_message(
                "Only the command invoker can use this button.", ephemeral=True
            )

    @discord.ui.button(label='Create new mute role', style=discord.ButtonStyle.blurple, row=0)
    async def _(self, button : discord.ui.Button, interaction : discord.Interaction):
        
        message = await interaction.response.send_message(f"<a:mtyping:904156199967158293> Creating muterole and setting permissions across the server...")
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        await interaction.message.edit(view=self)
        #Create the role
        muterole = await self.ctx.guild.create_role(name='Muted', reason='Muterole setup [Invoked by: {0} (ID: {0.id})]'.format(self.ctx.author))

        overwrites = {"send_messages": False}
        for channel in self.ctx.guild.channels:
            await channel.set_permissions(muterole, **overwrites)

        try:
            await self.ctx.bot.db.execute("INSERT INTO servers (muterole, server_id) VALUES ($1, $2)", muterole.id, self.ctx.guild.id)
        except asyncpg.exceptions.UniqueViolationError:
            await self.ctx.bot.db.execute("UPDATE servers SET muterole = $1 WHERE server_id = $2", muterole.id, self.ctx.guild.id)

        await interaction.edit_original_message(content=f"{self.ctx.bot.check} Created muterole `@{muterole.name}` and set to this guild's muterole.")


    @discord.ui.button(label='Set existing mute role', style=discord.ButtonStyle.green, row=0)
    async def __(self, button : discord.ui.Button, interaction : discord.Interaction):

        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        await interaction.message.edit(view=self)

        e = Embed()
        e.description = 'Please send the mention/id/name of the role to be set.'
        await interaction.response.send_message(embed=e)

        def check(message : discord.Message):
            return message.author == self.ctx.message.author and message.channel == self.ctx.channel

        try:
            role_string : discord.Message = await self.ctx.bot.wait_for('message', check=check, timeout=30.0)
        except asyncio.TimeoutError:
            return await interaction.followup.send('Timed out.')
        try:
            role = await commands.RoleConverter().convert(self.ctx, role_string.content)
        except commands.RoleNotFound:
            return await interaction.edit_original_message(content='Could not convert that into a role.', embeds=[])
        
        try:
            await self.ctx.bot.db.execute("INSERT INTO servers (muterole, server_id) VALUES ($1, $2)", role.id, self.ctx.guild.id)
        except asyncpg.exceptions.UniqueViolationError:
            await self.ctx.bot.db.execute("UPDATE servers SET muterole = $1 WHERE server_id = $2", role.id, self.ctx.guild.id)

        return await interaction.edit_original_message(content=f'{self.ctx.bot.check} Successfully updated `@{role.name}` to the mutedrole.', embeds=[])


    @discord.ui.button(label='Remove existing muted role', style=discord.ButtonStyle.danger, row=0, custom_id='remove_muterole')
    async def ___(self, button : discord.ui.Button, interaction : discord.Interaction):

        if not self.role_id:
            await interaction.response.send_message(f"This guild does not have a mute role configured yet.", ephemeral=True)
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    if item.custom_id == 'remove_muterole':
                        item.disabled = True
            await interaction.message.edit(view=self)
            return

        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        await interaction.message.edit(view=self)

        # Give a confirmation on deleting this role from database
        confirm = await self.ctx.confirm('Are you sure you want to remove the existing mutedrole for this guild?', interaction=interaction)
        if confirm is None:
            return
        if confirm is False:
            return
        
        # Remove from db
        await self.ctx.bot.db.execute("DELETE FROM servers WHERE muterole = $1", self.role_id)

        await interaction.followup.send(f":wastebasket: Removed the existing mutedrole for this guild.")
        for item in self.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
        return await interaction.message.edit(view=self)

    @discord.ui.button(emoji='\U00002753', style=discord.ButtonStyle.gray, row=1)
    async def ____(self, button : discord.ui.Button, interaction : discord.Interaction):
        
        await interaction.response.send_message(
            f"\nNeed help with which option to choose?"
            f"\n\n- \🔵 Choose **Create new mute role** if you don't currently have a role named `@Muted` setup correctly (choose this if you are confused)"
            f"\n\n- \🟢 Choose **Set existing mute role** if you *already* have a role named `@Muted` setup across the channels"
            f"\n\n- \🔴 Choose **Remove existing muted role** if you want to delete a already setup muted role from my database (this action cannot be undone)",
            ephemeral=True
        )

    @discord.ui.button(emoji='\U0001f5d1', style=discord.ButtonStyle.gray, row=1)
    async def stop_view(self, button : discord.ui.Button, interaction : discord.Interaction):
        """
        Stop the pagination session. 
        Unless this pagination menu was invoked with a slash command
        """

        await interaction.response.defer()
        await interaction.delete_original_message()
        self.stop()


class moderation(commands.Cog, description="Moderation commands."):
    def __init__(self, bot : MetroBot):
        self.bot = bot

    @property
    def emoji(self) -> str:
        return '🔨'

    @commands.command(name="kick", brief="Kick a member from the server.")
    @commands.has_guild_permissions(kick_members=True)
    @commands.bot_has_permissions(send_messages=True, kick_members=True)
    async def kick_cmd(self,
                       ctx : MyContext,
                       member : discord.Member = commands.Option(description='Member to kick.'),
                       *,
                       reason : Optional[str] = commands.Option(description='Reason for kicking this member.')  
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
            return await ctx.send(f'{self.bot.cross} You cannot kick yourself.')

        if not can_execute_action(ctx, ctx.author, member):
            return await ctx.send('You are not high enough in role hierarchy to kick this member.')

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
        name='softban'
    )
    @commands.has_guild_permissions(ban_members=True)
    @commands.bot_has_guild_permissions(ban_members=True)
    async def soft_ban(self, ctx : MyContext, member : Union[discord.Member, discord.User], delete_days : Optional[int] = 1, *, reason : Optional[str] = None):
        """
        Soft-bans a member from the server.
        
        A softban bans the user and immediately unbans them to delete their messages.
        """
        if delete_days and not 8 > delete_days > -1:
            raise commands.BadArgument(f"{self.bot.cross} `delete_days` must be between 0 and 7 days.")

        if not can_execute_action(ctx, ctx.author, member):
            return await ctx.send('You are not high enough in role hierarchy to ban this member.')

        await ctx.guild.ban(member, reason=f'Soft-ban requested by: {ctx.author} (ID: {ctx.author.id})\n{f"Reason: {reason}" if reason else ""}')
        await ctx.guild.unban(member, reason=f'Soft-ban requested by: {ctx.author} (ID: {ctx.author.id})\n{f"Reason: {reason}" if reason else ""}')

        e = Embed()
        e.colour = discord.Colour.green()
        e.description = f"You were soft-banned in **{ctx.guild}** by {ctx.author}"
        e.set_footer(text=f'{f"Reason: {reason}" if reason else "No reason provided..."}')

        try:
            await member.send(embed=e)
            success = '✅'
        except discord.HTTPException:
            success = '❌'
        
        embed = Embed()
        embed.description = f'**{ctx.author.mention}** has banned **{member}**\n{f"Reason: {reason}" if reason else "No reason provided..."}'
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
            member : discord.User = commands.Option(description='Member to ban.'),
            delete_days : Optional[int] = commands.Option(default=0, description='Amount of days worth of messages to delete.'),
            *,
            reason : str = commands.Option(default=None, description='Reason to ban this member/user.')
    ):
        """
        Ban a member from the server.\n
        Can be a mention, name or id.
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
        if member in ctx.guild.members:
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
    @commands.check(Cooldown(2, 8, 2, 4, commands.BucketType.member))
    async def unban_cmd(
            self,
            ctx : MyContext,
            member : discord.User = commands.Option(description='User to be unbanned.'),
            *,
            reason : Optional[str] = commands.Option(description='Reason for this user to be unbanned.')
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
    
    @commands.command(name='listbans', aliases=['bans'])
    @commands.bot_has_guild_permissions(ban_members=True)
    @commands.has_guild_permissions(ban_members=True)
    @commands.check(Cooldown(2, 8, 2, 4, commands.BucketType.member))
    async def list_bans(self, ctx : MyContext):
        """List all the banned users for this guild."""

        await ctx.defer()
        bans = await ctx.guild.bans()
        if not bans:
            return await ctx.send(f"No users are banned in this guild.")

        to_append = []
        for ban_entry in bans:
            to_append.append(f"{ban_entry.user} {ban_entry.user.mention} - {ban_entry.reason}")
        
        return await ctx.paginate(to_append, per_page=12)

    @commands.command(name='multiban',usage="[users...] [reason]")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(send_messages=True, ban_members=True)
    async def _multiban(self, ctx : MyContext, members : commands.Greedy[MemberID], *, reason : ActionReason = None):
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

    @commands.command()
    @commands.bot_has_permissions(send_messages=True)
    async def cleanup(self, ctx, amount: int=5):
        """
        Cleans up the bot's messages. 
        Defaults to 25 messages. If you or the bot does not have the Manage Messages permission, the search will be limited to 25 messages.
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
                raise commands.BadArgument("Slowmode delay must be more than 1 second and less than 6 hours.")

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

        
        reminder_cog = self.bot.get_cog('utility')
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
        

    @staticmethod
    async def do_removal(ctx : MyContext, limit : int, predicate, *, before = None, after = None, bulk : bool = True):
        if limit > 2000:
            raise commands.BadArgument(f'Too many messages to search. ({limit}/2000)')

        async with ctx.typing():
            if before is None:
                before = ctx.message
            else:
                before = discord.Object(id=before)
            
            if after is not None:
                after = discord.Object(id=after)

            try:
                deleted = await ctx.channel.purge(limit=limit, before=before, after=after, check=predicate, bulk=bulk)
            except discord.Forbidden:
                raise commands.BadArgument(f'I do not have the `manage_messages` permission to delete messages.')
            except discord.HTTPException as e:
                return await ctx.send(f'Error: {e}')

            spammers = Counter(m.author.display_name for m in deleted)
            deleted = len(deleted)
            messages = [f'{deleted} message{" was" if deleted == 1 else "s were"} removed.']
            if deleted:
                messages.append('')
                spammers = sorted(spammers.items(), key=lambda t: t[1], reverse=True)
                messages.extend(f'**{name}**: {count}' for name, count in spammers)

            to_send = '\n'.join(messages)

            if len(to_send) > 2000:
                await ctx.send(f'Successfully removed {deleted} messages.', delete_after=7)
            else:
                await ctx.send(to_send, delete_after=7)

    @commands.group(
        name='purge',
        aliases=['clear', 'clean'],
        invoke_without_command=True
    )
    @commands.has_permissions(manage_messages=True)
    async def purge(self, ctx : MyContext, search : Optional[int]):
        """
        Remove messages that meet a certain criteria.
        
        If you run this without sub-commands it will remove all messages that are not pinned to the channel.
        Use "remove all <amount>" to remove all messages inculding pinned ones.
        """

        if search is None:
            return await ctx.help()

        await self.do_removal(ctx, search, lambda e: not e.pinned)
        
    @purge.command(name='embeds', aliases=['embed'])
    @commands.has_permissions(manage_messages=True)
    async def purge_embeds(self, ctx : MyContext, search : int):
        """Remove messages that have embeds in them."""
        await self.do_removal(ctx, search, lambda e: len(e.embeds))

    @purge.command(name='files', aliases=['attachments'])
    @commands.has_permissions(manage_messages=True)
    async def purge_files(self, ctx : MyContext, search : int):
        """Remove messages that have files in them."""
        await self.do_removal(ctx, search, lambda e: len(e.attachments))

    @purge.command(name='images')
    @commands.has_permissions(manage_messages=True)
    async def purge_images(self, ctx : MyContext, search : int):
        """Remove messages that have embeds or attachments."""
        await self.do_removal(ctx, search, lambda e: len(e.embeds) or len(e.attachments))

    @purge.command(name='all')
    @commands.has_permissions(manage_messages=True)
    async def purge_all(self, ctx : MyContext, search : int):
        """Remove all messages."""
        await self.do_removal(ctx, search, lambda e: True)

    @purge.command(name='user', aliases=['member'])
    @commands.has_permissions(manage_messages=True)
    async def purge_user(self, ctx : MyContext, member : discord.Member, search : int):
        """Remove all messages sent by that member."""
        await self.do_removal(ctx, search, lambda e: e.author == member)

    @purge.command(name='contains',aliases=['has'])
    @commands.has_permissions(manage_messages=True)
    async def purge_contains(self, ctx : MyContext, *, text : str):
        """
        Remove all messages containing a substring.
        Must be at least 3 characters long.
        """
        if len(text) < 3:
            await ctx.send(f'The substring must be at least 3 characters.')
        else:
            await self.do_removal(ctx, 100, lambda e: text in e.content)

    @purge.command(name='bot', aliases=['bots'])
    @commands.has_permissions(manage_messages=True)
    async def purge_bots(self, ctx : MyContext, prefix : Optional[str] = None, search : int = 25):
        """Remove a bot's user messages and messages with their optional prefix."""

        def predicate(msg):
            return (msg.webhook_id is None and msg.author.bot) or (prefix and msg.content.startswith(prefix))

        await self.do_removal(ctx, search, predicate)

    @purge.command(name='emoji', aliases=['emojis'])
    @commands.has_permissions(manage_messages=True)
    async def purge_emojis(self, ctx : MyContext, search : int):
        """Remove all messages containing a custom emoji."""

        custom_emoji = re.compile(r'<a?:[a-zA-Z0-9_]+:([0-9]+)>')

        def predicate(m):
            return custom_emoji.search(m.content)

        await self.do_removal(ctx, search, predicate)

    @purge.command(name='reactions')
    @commands.has_permissions(manage_messages=True)
    async def purge_reactions(self, ctx : MyContext, search : int):
        """Remove all reactions from messages that have them."""

        async with ctx.typing():
            if search > 2000:
                return await ctx.send(f'Too many messages to search. ({search}/2000)')
            
            total_reactions = 0
            async for message in ctx.history(limit=search, before=ctx.message):
                if len(message.reactions):
                    total_reactions += sum(r.count for r in message.reactions)
                    await message.clear_reactions()
                    await asyncio.sleep(.5)

            await ctx.send(f'Successfully removed {total_reactions} reactions.')

    @purge.command(name='threads')
    @commands.has_permissions(manage_messages=True)
    async def purge_threads(self, ctx : MyContext, search : int):
        """Remove threads from the channel."""

        async with ctx.typing():
            if search > 2000:
                return await ctx.send(f'Too many messages to search given ({search}/2000)')

            def check(m: discord.Message):
                return m.flags.has_thread

            deleted = await ctx.channel.purge(limit=search, check=check)
            thread_ids = [m.id for m in deleted]
            if not thread_ids:
                return await ctx.send("No threads found!")

            for thread_id in thread_ids:
                thread = self.bot.get_channel(thread_id)
                if isinstance(thread, discord.Thread):
                    await thread.delete()
                    await asyncio.sleep(0.5)

            spammers = Counter(m.author.display_name for m in deleted)
            deleted = len(deleted)
            messages = [f'{deleted} message'
                        f'{" and its associated thread was" if deleted == 1 else "s and their associated messages were"} '
                        f'removed.']

            if deleted:
                messages.append('')
                spammers = sorted(spammers.items(), key=lambda t: t[1], reverse=True)
                messages.extend(f'**{name}**: {count}' for name, count in spammers)

            to_send = '\n'.join(messages)

            if len(to_send) > 2000:
                await ctx.send(f'Successfully removed {deleted} messages and their associated threads.',
                               delete_after=1)
            else:
                await ctx.send(to_send, delete_after=10)


    @purge.command(name='custom')
    @commands.has_permissions(manage_messages=True)
    async def purge_custom(self, ctx : MyContext, *, args : str = None):
        """
        A more advanced purge command with a command-line-like syntax.

        Most options support multiple values to indicate 'any' match.
        If the value has spaces it must be quoted.
        The messages are only deleted if all options are met unless
        the `--or` flag is passed, in which case only if any is met.

        The following options are valid.
        `--user`: A mention or name of the user to remove.
        `--contains`: A substring to search for in the message.
        `--starts`: A substring to search if the message starts with.
        `--ends`: A substring to search if the message ends with.
        `--search`: Messages to search. Default 100. Max 2000.
        `--after`: Messages after this message ID.
        `--before`: Messages before this message ID.

        Flag options (no arguments):
        `--bot`: Check if it's a bot user.
        `--embeds`: Checks for embeds.
        `--files`: Checks for attachments.
        `--emoji`: Checks for custom emoji.
        `--reactions`: Checks for reactions.
        `--or`: Use logical OR for ALL options.
        `--not`: Use logical NOT for ALL options.   
        """
        if args is None:
            return await ctx.help()

        parser = Arguments(add_help=False, allow_abbrev=False)
        parser.add_argument('--user', nargs='+')
        parser.add_argument('--contains', nargs='+')
        parser.add_argument('--starts', nargs='+')
        parser.add_argument('--ends', nargs='+')
        parser.add_argument('--or', action='store_true', dest='_or')
        parser.add_argument('--not', action='store_true', dest='_not')
        parser.add_argument('--emoji', action='store_true')
        parser.add_argument('--bot', action='store_const', const=lambda m: m.author.bot)
        parser.add_argument('--embeds', action='store_const', const=lambda m: len(m.embeds))
        parser.add_argument('--files', action='store_const', const=lambda m: len(m.attachments))
        parser.add_argument('--reactions', action='store_const', const=lambda m: len(m.reactions))
        parser.add_argument('--search', type=int)
        parser.add_argument('--after', type=int)
        parser.add_argument('--before', type=int)

        try:
            args = parser.parse_args(shlex.split(args))
        except Exception as e:
            await ctx.send(str(e))
            return

        predicates = []
        if args.bot:
            predicates.append(args.bot)

        if args.embeds:
            predicates.append(args.embeds)

        if args.files:
            predicates.append(args.files)

        if args.reactions:
            predicates.append(args.reactions)

        if args.emoji:
            custom_emoji = re.compile(r'<:(\w+):(\d+)>')
            predicates.append(lambda m: custom_emoji.search(m.content))

        if args.user:
            users = []
            converter = commands.MemberConverter()
            for u in args.user:
                try:
                    user = await converter.convert(ctx, u)
                    users.append(user)
                except Exception as e:
                    await ctx.send(str(e))
                    return

            predicates.append(lambda m: m.author in users)

        if args.contains:
            predicates.append(lambda m: any(sub in m.content for sub in args.contains))

        if args.starts:
            predicates.append(lambda m: any(m.content.startswith(s) for s in args.starts))

        if args.ends:
            predicates.append(lambda m: any(m.content.endswith(s) for s in args.ends))

        op = all if not args._or else any

        def predicate(m):
            r = op(p(m) for p in predicates)
            if args._not:
                return not r
            return r

        if args.after:
            if args.search is None:
                args.search = 2000

        if args.search is None:
            args.search = 100

        args.search = max(0, min(2000, args.search))  # clamp from 0-2000
        await self.do_removal(ctx, args.search, predicate, before=args.before, after=args.after)


    @commands.command(name='block')
    @commands.bot_has_permissions(manage_channels=True, send_messages=True)
    @commands.has_permissions(manage_channels=True, send_messages=True)
    async def block(self, ctx, member : discord.Member = commands.Option(description='member to block')):
        """
        Block a member from your channel.
        """
        
        if not can_execute_action(ctx, ctx.author, member):
            return

        reason = f'Blocked by {ctx.author} (ID: {ctx.author.id})'

        try:
            await ctx.channel.set_permissions(member, send_messages=False, add_reactions=False, reason=reason)
        except:
            return await ctx.cross()

        await ctx.check()


    @commands.command(name='unblock')
    @commands.bot_has_permissions(manage_channels=True, send_messages=True)
    @commands.has_permissions(manage_channels=True, send_messages=True)
    async def unblock(self, ctx, member : discord.Member = commands.Option(description='member to unblock')):
        """
        Unblock a member from your channel.
        """
        
        if not can_execute_action(ctx, ctx.author, member):
            return

        reason = f'Unblocked by {ctx.author} (ID: {ctx.author.id})'

        try:
            await ctx.channel.set_permissions(member, send_messages=None, add_reactions=None, reason=reason)
        except:
            return await ctx.cross()

        await ctx.check()


    @commands.command(name='tempblock')
    @can_block()
    @commands.bot_has_permissions(manage_channels=True, send_messages=True)
    async def tempblock(self, ctx, member : discord.Member, *, duration : remind_utils.FutureTime):
        """Temporarily blocks a user from your channel.

        The duration can be a a short time form, e.g. 30d or a more human
        duration such as "until thursday at 3PM" or a more concrete time
        such as "2017-12-31".

        Note that times are in UTC.
        """
        
        if not can_execute_action(ctx, ctx.author, member):
            return

        created_at = ctx.message.created_at

        reminder_cog = self.bot.get_cog('utility')
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
            delta = human_timedelta(duration.dt - datetime.timedelta(seconds=2))
            await ctx.send(f'Blocked {member} for {delta}')

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


    @commands.command(
        name='muterole'
    )
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_guild_permissions(manage_roles=True, manage_channels=True)
    @commands.check(Cooldown(2, 10, 2, 8, commands.BucketType.member))
    async def muterole(self, ctx : MyContext):
        """
        Manage this guild's mute role with an interactive menu.
        """
        # Muterole menu idea from Neutra
        # https://github.com/Hecate946/Neutra/blob/main/cogs/admin.py#L51-L125

        data = await self.bot.db.fetchrow("SELECT muterole FROM servers WHERE server_id = $1", ctx.guild.id)
        if not data:
            role_id = None
            current_settings = "No muterole set yet..."
        else:
            role_id = data['muterole']
            current_settings = f"<@&{role_id}> (ID: {role_id})"
        e = Embed()
        e.color = discord.Color.yellow()
        e.title = 'Muterole Configuration'
        e.description = 'Please choose one of the options below to manage/set/create the muted role.'\
                        f"\n\n**Your current muterole configured:** {current_settings}"

        await ctx.send(embed=e, view=MuteRoleView(ctx, role_id))


    @commands.command(
        name='mute', 
        aliases=['moot', 'tempmute'], 
        extras={"examples" : "[p]mute @dartmern 1h spamming\n[p]mute @dartmern @Pickles @gamer97878 raiders\n[p]mute @Picklesbefree"},
        usage="[members...] [duration] [reason]"
    )
    @commands.check(Cooldown(4, 8, 6, 8, commands.BucketType.member))
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_guild_permissions(manage_roles=True)
    async def mute(
        self, 
        ctx : MyContext,
        members : commands.Greedy[discord.Member],
        *,
        duration : UserFriendlyTime(
            commands.clean_content, default='\u2026'
        ) = None
    ):
        """
        Mute multiple members using the configured muted role.
        
        The bot's stop role must be above the configured role.
        To setup or change the muted role see the `muterole` command.
        """
        reminder_cog = self.bot.get_cog("utility")
        if not reminder_cog:
            return await ctx.send("This feature is currectly unavailable. Please try again later.")
        if not len(members):
            return await ctx.help()

        muterole = await ctx.bot.db.fetchval("SELECT muterole FROM servers WHERE server_id = $1", ctx.guild.id)
        muterole = ctx.guild.get_role(muterole)
        if not muterole:
            return await ctx.send(f"You do not have a mute role setup yet. Please run `{ctx.prefix}muterole`")

        await ctx.defer()

        if muterole.position > ctx.guild.me.top_role.position:
            to_send = ""
            to_send += (
                f"\🔴 I am unable to mute {'these members' if len(members) > 1 else 'this member'} due to discord hierarchy rules."
                f"\nMy top role's position ({ctx.guild.me.top_role.mention}) is lower than the configured mute role."
                f"\n\nMy top role position: {ctx.guild.me.top_role.position} • Muted Role's position: {muterole.position}"
                f"\n\nPlease move my top role higher to make this command work!"
            )
            raise commands.BadArgument(to_send)
        
        if duration:
            reason = duration.arg if duration.arg != "…" else None
            endtime = duration.dt.replace(tzinfo=None) if duration.dt else None
            ftime = human_timedelta((endtime), accuracy=500)
            
        else:
            reason = None
            endtime = None

        if reason:
            real_reason = await ActionReason().convert(ctx, reason)
        else:
            real_reason = f"Action requested by {ctx.author} (ID: {ctx.author.id})"
        
        failed, muted = [], []
        for user in members:
            if not can_execute_action(ctx, ctx.author, user):
                failed.append(f"• `{user}` cannot be muted due to your top role being lower than their top role.")
                continue
                
            if user == ctx.author:
                failed.append(f"• I cannot mute `{user}` as you cannot mute yourself.")
                continue

            if user == self.bot.user:
                failed.append(f"• I cannot mute myself.")
                continue

            if muterole in user.roles:
                failed.append(f"• `{user}` was already muted")
                continue

            await self.bot.db.fetchval("DELETE FROM reminders WHERE event = 'mute' AND extra->'kwargs'->>'user_id' = $1", str(user.id))
            try:
                if endtime:
                    timer = await reminder_cog.create_timer(
                        duration.dt,
                        "mute",
                        ctx.guild.id,
                        ctx.author.id,
                        user.id,
                        user_id=user.id,
                        connection=self.bot.db,
                        created=ctx.message.created_at
                    )
                    desc = f"for `{ftime}`"
                else:
                    desc = ""

                await user.add_roles(muterole, reason=real_reason)
                muted.append(str(user))

                e = Embed()
                e.colour = discord.Colour.orange()
                e.description = f'You were muted from **{ctx.guild.name}** by {ctx.author} {desc}'
                e.set_footer(text=f'Reason: {reason if reason else "No reason provided..."}')

                try:
                    await user.send(embed=e)
                except discord.HTTPException:
                    pass

            except Exception as e:
                failed.append(f"• {str(user)} : `{e}`")

        if muted:
            if endtime:
                to_send = f"{self.bot.check} Successfully **muted** `{', '.join(muted)}` for **{ftime}**"
            else:
                to_send = f"{self.bot.check} Successfully **muted** `{', '.join(muted)}`"
            
            e = Embed()
            e.colour = discord.Colour.green()
            e.description = to_send
            e.set_footer(text=f'Reason: {reason if reason else "No reason provided..."}')

            await ctx.send(embed=e)
        if failed:
            nl = '\n'
            await ctx.send(f"Had a problem muting these members:\n {nl.join(failed)}")

    @commands.command(
        name='unmute',
        aliases=['unmoot'],
        usage="[members...] [reason]"
    )
    @commands.check(Cooldown(4, 8, 6, 8, commands.BucketType.member))
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_guild_permissions(manage_roles=True)
    async def unmute(
        self,
        ctx : MyContext,
        members : commands.Greedy[discord.Member],
        *,
        reason : Optional[str] = None
    ):
        """
        Unmute previously muted members.

        They must have the configured mutedrole for this to work.
        """
        reminder_cog = self.bot.get_cog("utility")
        if not reminder_cog:
            return await ctx.send("This feature is currectly unavailable. Please try again later.")
        if not len(members):
            return await ctx.help()

        muterole = await ctx.bot.db.fetchval("SELECT muterole FROM servers WHERE server_id = $1", ctx.guild.id)
        muterole = ctx.guild.get_role(muterole)
        if not muterole:
            return await ctx.send(f"You do not have a mute role setup yet. Please run `{ctx.prefix}muterole`")

        await ctx.defer()

        if muterole.position > ctx.guild.me.top_role.position:
            to_send = ""
            to_send += (
                f"\🔴 I am unable to mute {'these members' if len(members) > 1 else 'this member'} due to discord hierarchy rules."
                f"\nMy top role's position ({ctx.guild.me.top_role.mention}) is lower than the configured mute role."
                f"\n\nMy top role position: {ctx.guild.me.top_role.position} • Muted Role's position: {muterole.position}"
                f"\n\nPlease move my top role higher to make this command work!"
            )
            raise commands.BadArgument(to_send)

        failed, unmuted = [], []
        for user in members:
            if not can_execute_action(ctx, ctx.author, user):
                failed.append(f"• `{user}` cannot be unmuted due to your top role being lower than their top role.")
                continue

            if not muterole in user.roles:
                failed.append(f"• `{user}` is not even muted.")
                continue

            query = """
                    select (id, extra)
                    from reminders
                    where event = 'mute'
                    and extra->'kwargs'->>'user_id' = $1
                    """
            s = await self.bot.db.fetchval(query, str(user.id))
            if not s:
                await user.remove_roles(muterole)

                em = Embed()
                em.colour = discord.Colour.yellow()
                em.description = f"You were unmuted in **{ctx.guild}** by {ctx.author}"
                em.set_footer(text=f'Reason: {reason if reason else "No reason provided..."}')

                try:
                    await user.send(embed=em)
                except discord.HTTPException:
                    pass

                unmuted.append(str(user))
                continue

            task_id = s[0]
            try:
                await user.remove_roles(muterole)
                query = """
                        DELETE FROM reminders
                        WHERE id = $1
                        """
                await self.bot.db.execute(query, task_id)

                em = Embed()
                em.colour = discord.Colour.yellow()
                em.description = f"You were unmuted in **{ctx.guild}** by {ctx.author}"
                em.set_footer(text=f'Reason: {reason if reason else "No reason provided..."}')

                try:
                    await user.send(embed=em)
                except discord.HTTPException:
                    pass

                unmuted.append(str(user))
            except Exception as e:
                failed.append(f"• {user} : {e}")

        if unmuted:
            e = Embed()
            e.colour = discord.Colour.green()
            e.description = f"{self.bot.check} Successfully **unmuted** `{', '.join(unmuted)}`"
            e.set_footer(text=f'Reason: {reason if reason else "No reason provided..."}')
            return await ctx.send(embed=e)
        if failed:
            nl = '\n'
            return await ctx.send(f"Had a problem unmuting these members: \n{nl.join(failed)}")
        return

    @commands.command(name='mutelist', aliases=['listmute'])
    @commands.guild_only()
    async def mutelist(self, ctx : MyContext):
        """
        List all the current and active mutes in this server.

        This includes indefinite and temporary mutes.
        """
        reminder_cog = self.bot.get_cog("utility")
        if not reminder_cog:
            return await ctx.send("This feature is currectly unavailable. Please try again later.")

        muterole = await ctx.bot.db.fetchval("SELECT muterole FROM servers WHERE server_id = $1", ctx.guild.id)
        muterole = ctx.guild.get_role(muterole)
        if not muterole:
            return await ctx.send(f"This server's moderators have not setup a mute role yet...Therefore no one is muted.")

        await ctx.defer()

        embed = Embed()
        embed.colour = discord.Colour.yellow()

        query = """
                SELECT (expires, extra, created)
                FROM reminders
                WHERE event = 'mute'
                ORDER BY expires;
                """
        records = await self.bot.db.fetch(query)
        if not records:
            return await ctx.send("No one is muted in this guild.")

        for record in records:
            expires : datetime.datetime = pytz.utc.localize(record['row'][0])
            extra : Dict = json.loads(record['row'][1])
            created = pytz.utc.localize(record['row'][2])

            user = self.bot.get_user(extra['kwargs'].get('user_id'))
            selfmute = self.bot.check if extra['kwargs'].get('selfmute') else self.bot.cross
            embed.add_field(
                name=f'{user.name[0:40]}#{user.discriminator}', 
                value=f'\n Muted: {discord.utils.format_dt(created, "R")}'\
                    f"\n Moderator: <@{extra['args'][2]}>"\
                    f"\n Expired: {discord.utils.format_dt(expires, 'R')}"
                    f"\n Selfmute: {selfmute}",
                inline=False
            )
        return await ctx.send(embed=embed)

        

    @commands.command(name='selfmute')
    @commands.guild_only()
    @commands.bot_has_guild_permissions(manage_roles=True)
    async def selfmute(self, ctx : MyContext, *, duration : FutureTime):
        """
        Temporarily mute yourself for a specific duration.

        You must specify a duration at least 5 minutes and no longer than 1 day.

        **:warning: Do not ask an moderator to unmute you :warning:** 
        """
        reminder_cog = self.bot.get_cog("utility")
        if not reminder_cog:
            return await ctx.send("This feature is currectly unavailable. Please try again later.")

        muterole = await ctx.bot.db.fetchval("SELECT muterole FROM servers WHERE server_id = $1", ctx.guild.id)
        muterole = ctx.guild.get_role(muterole)
        if not muterole:
            return await ctx.send(f"This server's moderators have not setup a mute role yet...")

        if muterole in ctx.author.roles:
            raise commands.BadArgument("Somehow you are already muted...")
            
        reason = f"Self-mute requested by: {ctx.author} (ID: {ctx.author.id})"

        if muterole.position > ctx.guild.me.top_role.position:
            to_send = ""
            to_send += (
                f"\🔴 I am unable to mute you due to discord hierarchy rules."
                f"\nMy top role's position ({ctx.guild.me.top_role.mention}) is lower than the configured mute role."
                f"\n\nMy top role position: {ctx.guild.me.top_role.position} • Muted Role's position: {muterole.position}"
                f"\n\nPlease ask a moderator to move my top role higher to make this command work!"
            )
            raise commands.BadArgument(to_send)

        created_at = ctx.message.created_at
        if duration.dt < (created_at + datetime.timedelta(minutes=5)):
            raise commands.BadArgument("Duration is too short. Must be at least 5 minutes and less than 1 day.")

        if duration.dt > (created_at + datetime.timedelta(days=1)):
            raise commands.BadArgument("Duration is too long. Must be at least 5 minutes and less than 1 day.")

        ftime = human_timedelta(duration.dt, accuracy=50)

        confirm = await ctx.confirm(f"_Are you sure you want to mute yourself for **{ftime}**?_"
                                    f"\n**__Don't ask the moderators to undo this!__**", timeout=45.0
        )
        if confirm is False:
            return await ctx.send("Canceled.")
        if confirm is None:
            return await ctx.send("Timed out.")

        await ctx.send(f"Selfmuted for `{ftime}`, be sure to bother anyone about it.")

        try:
            await ctx.author.add_roles(muterole, reason=reason)
        except discord.HTTPException:
            raise commands.BadArgument(f"I am having trouble adding `@{muterole.name}` to your roles.")

        await self.bot.db.fetchval("DELETE FROM reminders WHERE event = 'mute' AND extra->'kwargs'->>'user_id' = $1", str(ctx.author.id))
        try:
            timer = await reminder_cog.create_timer(
                        duration.dt.replace(tzinfo=None),
                        "mute",
                        ctx.guild.id,
                        ctx.author.id,
                        ctx.author.id,
                        user_id=ctx.author.id,
                        selfmute=True,
                        connection=self.bot.db,
                        created=ctx.message.created_at.replace(tzinfo=None)
            ) 
        except Exception as e:
            return await ctx.send(str(e))
            


    @commands.Cog.listener()
    async def on_mute_timer_complete(self, timer):
        await self.bot.wait_until_ready()
        guild_id, mod_id, member_id = timer.args


        print("fired")
        guild = self.bot.get_guild(guild_id)
        if guild is None:
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
                moderator = f"{moderator} ({mod_id})"
        else:
            moderator = f"{moderator} ({mod_id})"

        reason = (
            f"Automatic unmute from timer made on {timer.created_at} by {moderator}."
        )
        member = guild.get_member(member_id)
        if not member:
            return  # They left...

        muterole = await self.bot.db.fetchval("SELECT muterole FROM servers WHERE server_id = $1", guild.id)
        muterole = guild.get_role(muterole)
        if not muterole:
            return # Muted role somehow not found...

        #try:
        await member.remove_roles(muterole, reason=reason)
        #except Exception:  # They probably removed roles lmao.
        #return
        
        e = Embed()
        e.colour = discord.Colour.yellow()
        e.description = f"You were automatically unmuted in **{guild}** as your mute expried."
        
        try:
            await member.send(embed=e)
        except discord.HTTPException:
            pass # DMs off or somehow cannot dm them
        

def setup(bot):
    bot.add_cog(moderation(bot))