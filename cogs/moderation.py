import discord
from discord.ext import commands

from utils.converters import MemberConverter

from typing import Optional
from collections import Counter

import typing
import datetime
import re
import humanize
from humanize.time import precisedelta


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

class moderation(commands.Cog, description="Moderation commands."):
    def __init__(self, bot):
        self.bot = bot


    @commands.command(name="kick", brief="Kick a member from the server.")
    @commands.has_guild_permissions(kick_members=True)
    async def kick_cmd(self,
                       ctx,
                       member : MemberConverter,
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
        await ctx.reply(f"Kicked **{member}**")


    @commands.command(
        name="ban",
        brief="Ban a member from the server.",
        usage="<member> [reason]"
    )
    @commands.has_guild_permissions(ban_members=True)
    async def ban_cmd(
            self,
            ctx,
            member : typing.Union[MemberConverter, discord.User],
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
            return

        try:
            await member.send(
                f"You were banned from **{ctx.guild}** `{ctx.guild.id}`\n\nModerator: **{ctx.author}** `{ctx.author.id}`\nReason: **{reason_1}**")
        except:
            pass


        await ctx.reply(f"Banned **{member}**")


    @commands.command(name="unban",
                      brief="Unban a previously banned member.",
                      usage="<member>")
    @commands.has_guild_permissions(ban_members=True)
    async def unban_cmd(
            self,
            ctx,
            *,
            member : discord.User
    ):
        """
        Unbans an user from the server.
        Raises an error if the user is not a previously banned member."""

        bans = await ctx.guild.bans()
        for ban in bans:
            user = ban.user
            if user.id == member.id:
                await ctx.guild.unban(user)
                await ctx.send(f"Unbanned **{user}**")
                return
        raise commands.BadArgument(
            "**" + member.name + "** was not a previously banned member."
        )


    @commands.command(
        name="lockdown",
        brief="Lockdown a channel.",
        usage="[channel]",
        aliases=["lock"]
    )
    @commands.has_permissions(manage_channels=True)
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
    async def cleanup(self, ctx, amount: int=25):
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
    async def slowmode(self, ctx, time : TimeConverter=None):

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


    def strip_accs(self, text):
        try:
            text = unicodedata.normalize("NFKC", text)
            text = unicodedata.normalize("NFD", text)
            text = unidecode.unidecode(text)
            text = text.encode("ascii", "ignore")
            text = text.decode("utf-8")
        except Exception as e:
            raise e
        return str(text)

    def is_cancerous(self, text: str) -> bool:
        for segment in text.split():
            for char in segment:
                if not (char.isascii() and char.isalnum()):
                    return True
        return False


    @commands.command(aliases=['dc'])
    async def decancer(self, ctx, member : discord.Member):
        """
        Decancers the member's nickname.
        This removes all all _cancerous_ characters such as Zalgo.
        """

        if self.is_cancerous(target.display_name) == True:
            display = target.display_name
            nick = await self.nick_maker(ctx.guild, target.display_name)
            await target.edit(nick=nick)
            await ctx.send(
                f"**{display}** was now changed to **{nick}**",
                allowed_mentions=discord.AllowedMentions.none(),
            )

        else:
            await ctx.send("Member is already decancered")



    async def nick_maker(self, guild: discord.Guild, old_shit_nick):
        old_shit_nick = self.strip_accs(old_shit_nick)
        new_cool_nick = re.sub("[^a-zA-Z0-9 \n.]", "", old_shit_nick)
        new_cool_nick = " ".join(new_cool_nick.split())
        new_cool_nick = stringcase.lowercase(new_cool_nick)
        new_cool_nick = stringcase.titlecase(new_cool_nick)
        default_name = "Moderated Nickname " + "".join(
            random.choices(string.ascii_uppercase + string.digits, k=6)
        )
        if len(new_cool_nick.replace(" ", "")) <= 1 or len(new_cool_nick) > 32:
            if default_name:
                new_cool_nick = default_name
            else:
                new_cool_nick = "simp name"
        return new_cool_nick
















def setup(bot):
    bot.add_cog(moderation(bot))