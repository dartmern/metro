from typing import Optional
import discord
from discord.ext import commands, menus
import pytz
import asyncpg

from bot import MetroBot
from utils.custom_context import MyContext
from utils.new_pages import SimplePages
from utils.useful import Cooldown

class CasesSource(menus.ListPageSource):
    def __init__(self, entries, *, ctx: MyContext, footer: str):
        super().__init__(entries, per_page=1)
        self.ctx = ctx
        self.actions = {
            "ban" : discord.Colour.red(),
            "mute" : discord.Colour.dark_orange(),
            "selfmute": discord.Colour.orange(),
            "kick" : discord.Colour.blue(),
            "unmute" : discord.Colour.green(),
            "tempban" : 0xFFC0CB,
            "unban" : 0x1ABC9C,
            "selfmute": discord.Colour.orange(),
            "softban": discord.Colour.dark_orange()
        }
        self.footer = footer

    async def get_modlog(self, guild: discord.Guild) -> discord.TextChannel:
        modlog = await self.ctx.bot.db.fetchval('SELECT modlog FROM servers WHERE server_id = $1', guild.id)
        if not modlog:
            return None
        channel = guild.get_channel(modlog)
        return channel if channel else None

    async def format_page(self, menu: SimplePages, case_js):

        member = await self.ctx.bot.try_user(case_js['row'][3])
        moderator = self.ctx.guild.get_member(case_js['row'][1])

        description = ""
        description += (
            f"\n**Offender:** {member if member else 'Not Found.'} (<@{case_js['row'][3]}>)"\
            f"\n**Reason:** {case_js['row'][4]}"
        )
        if case_js['row'][6]:
            description += f"\n**Duration:** {case_js['row'][6]}"
        description += (
            f"\n**Responsible moderator:** {moderator if moderator else 'Not Found'}"\
            f"\n**Occurred:** {discord.utils.format_dt(pytz.utc.localize(case_js['row'][0]), 'F')} ({discord.utils.format_dt(pytz.utc.localize(case_js['row'][0]), 'R')})"
        )
        embed = discord.Embed(color=self.actions[case_js['row'][2]], title=f"{case_js['row'][2]} | case {case_js['row'][8]}", description=description)

        modlog = await self.get_modlog(self.ctx.guild)
        if modlog:
            message = modlog.get_partial_message(case_js['row'][7])
            if message:
                embed.add_field(name='Jump link', value=f'[Jump!]({message.jump_url} \"Jump to modlog case\")')
        embed.set_footer(text=self.footer)
        return embed

        

def setup(bot: MetroBot):
    bot.add_cog(_logging(bot))

class _logging(commands.Cog, description='Manage logging related commands.', name='logging'):
    def __init__(self, bot: MetroBot):
        self.bot = bot
        self.actions = {
            "ban" : discord.Colour.red(),
            "mute" : discord.Colour.dark_orange(),
            "selfmute": discord.Colour.orange(),
            "kick" : discord.Colour.blue(),
            "unmute" : discord.Colour.green(),
            "tempban" : 0xFFC0CB,
            "unban" : 0x1ABC9C,
            "selfmute": discord.Colour.orange(),
            "softban": discord.Colour.dark_orange()
        }

    @property
    def emoji(self) -> str:
        return '\U0001f516'


    @commands.group(name='modlog', aliases=['ml'], invoke_without_command=True, case_insensitive=True)
    @commands.has_guild_permissions(administrator=True)
    @commands.bot_has_guild_permissions(administrator=True)
    @commands.guild_only()
    async def modlog(self, ctx: MyContext):
        """Base command for modifying modlog."""
        await ctx.help()

    @modlog.command(name='reset', aliases=['wipe', 'clear'])
    @commands.guild_only()
    @commands.has_guild_permissions(administrator=True)
    @commands.bot_has_guild_permissions(administrator=True)
    @commands.check(Cooldown(2, 10, 2, 8, commands.BucketType.user))
    async def modlog_reset(self, ctx: MyContext):
        """Reset all modlog cases for this guild."""

        cases = await self.bot.db.fetchval("SELECT COUNT(*) FROM modlogs WHERE guild_id = $1", ctx.guild.id)
        if not cases:
            raise commands.BadArgument("This guild does not have any modlog cases.")

        confirm = await ctx.confirm(f"Are you sure you want to clear **{cases}** cases?", timeout=30)
        if confirm is False:
            return await ctx.send("Canceled.")
        if confirm is None:
            return await ctx.send("Timed out.")

        await self.bot.db.execute("DELETE FROM modlogs WHERE guild_id = $1", ctx.guild.id)
        await ctx.send(f"Cleared **{cases}** modlog cases for this guild.")

    @modlog.command(name='channel')
    @commands.guild_only()
    @commands.has_guild_permissions(administrator=True)
    @commands.bot_has_guild_permissions(administrator=True)
    @commands.check(Cooldown(1, 5, 1, 3, commands.BucketType.user))
    async def modlog_channel(self, ctx: MyContext, *, channel: Optional[discord.TextChannel]):
        """Set a channel as the modlog.
        
        Run this command without arguments to remove the channel."""
        if not channel:
            await ctx.send("Removed the modlog channel.")
            try:
                await self.bot.db.execute("INSERT INTO servers (modlog, server_id) VALUES ($1, $2)", None, ctx.guild.id)
            except asyncpg.exceptions.UniqueViolationError:
                await self.bot.db.execute("UPDATE servers SET modlog = $1 WHERE server_id = $2", None, ctx.guild.id)
            return 

        message = await channel.send(
            "\nThis channel has been set as the modlog channel."\
            "\nAny moderation action will be logged here."\
            f"\nYou can edit the reason with `{ctx.clean_prefix}reason <case> <reason>`"\
            "\nIt is recommended to keep this channel visible for everyone but that's up to you."
        )
        await message.pin()
        await ctx.send(f"Set {channel.mention} as the modlog channel.")

        try:
            await self.bot.db.execute("INSERT INTO servers (modlog, server_id) VALUES ($1, $2)", channel.id, ctx.guild.id)
        except asyncpg.exceptions.UniqueViolationError:
            await self.bot.db.execute("UPDATE servers SET modlog = $1 WHERE server_id = $2", channel.id, ctx.guild.id)

    async def get_modlog(self, guild: discord.Guild) -> discord.TextChannel:
        modlog = await self.bot.db.fetchval('SELECT modlog FROM servers WHERE server_id = $1', guild.id)
        if not modlog:
            return None
        channel = guild.get_channel(modlog)
        return channel if channel else None

    @commands.command(name='case')
    @commands.guild_only()
    @commands.bot_has_guild_permissions(administrator=True)
    @commands.has_guild_permissions(manage_guild=True)
    @commands.check(Cooldown(2, 10, 2, 8, commands.BucketType.member))
    async def _case(self, ctx: MyContext, number: int):
        """Show the specified case."""

        case_js = await self.bot.db.fetchval(
            "SELECT (added_time, moderator, action, target, reason, message_id, duration, message_id) "\
            "FROM modlogs "\
            "WHERE guild_id = $1 "\
            "AND case_number = $2", ctx.guild.id, number
        )
        if not case_js:
            raise commands.BadArgument("That specified case was not found.")

        member = await self.bot.try_user(case_js[3])
        moderator = ctx.guild.get_member(case_js[1])

        description = ""
        description += (
            f"\n**Offender:** {member if member else 'Not Found.'} (<@{case_js[3]}>)"\
            f"\n**Reason:** {case_js[4]}"
        )
        if case_js[6]:
            description += f"\n**Duration:** {case_js[6]}"
        description += (
            f"\n**Responsible moderator:** {moderator if moderator else 'Not Found'}"\
            f"\n**Occurred:** {discord.utils.format_dt(pytz.utc.localize(case_js[0]), 'F')} ({discord.utils.format_dt(pytz.utc.localize(case_js[0]), 'R')})"
        )

        embed = discord.Embed(color=self.actions[case_js[2]], title=f"{case_js[2]} | case {number}", description=description)

        modlog = await self.get_modlog(ctx.guild)
        if modlog:
            message = modlog.get_partial_message(case_js[7])
            if message:
                embed.add_field(name='Jump link', value=f'[Jump!]({message.jump_url} \"Jump to modlog case\")')
        await ctx.send(embed=embed)
        
    @commands.command(name='casesfor', aliases=['cf'])
    @commands.guild_only()
    @commands.bot_has_guild_permissions(administrator=True)
    @commands.has_guild_permissions(manage_guild=True)
    @commands.check(Cooldown(2, 10, 2, 8, commands.BucketType.user))
    async def cases_for(self, ctx: MyContext, *, member: discord.Member):
        """Display cases for the specified member."""

        async with ctx.typing():
            case_js = await self.bot.db.fetch(
                "SELECT (added_time, moderator, action, target, reason, message_id, duration, message_id, case_number) "\
                "FROM modlogs "\
                "WHERE guild_id = $1 "\
                "AND target = $2", ctx.guild.id, member.id
            )
            if not case_js:
                raise commands.BadArgument("This member doesn't have any modlog cases.")
            menu = SimplePages(source=CasesSource(case_js, ctx=ctx, footer=f"{len(case_js)} modlog cases."), ctx=ctx, compact=True)
            await menu.start()

    @commands.command(name='reason')
    @commands.guild_only()
    @commands.bot_has_guild_permissions(administrator=True)
    @commands.has_guild_permissions(manage_guild=True)
    @commands.check(Cooldown(1, 5, 1, 3, commands.BucketType.member))
    async def reason(self, ctx: MyContext, case: int, *, reason: str):
        """Set a reason for a modlog case."""
        modlog = await self.get_modlog(ctx.guild)
        if not modlog:
            raise commands.BadArgument("Modlog channel was not found for this guild.")

        query = """
                SELECT (added_time, moderator, action, target, message_id, duration)
                FROM modlogs
                WHERE guild_id = $1
                AND case_number = $2
                """
        data = await self.bot.db.fetchval(query, ctx.guild.id, case)
        if not data:
            raise commands.BadArgument("That case number was not found.")

        message = modlog.get_partial_message(data[4])
        if not message:
            raise commands.BadArgument("This modlog case was found but I cannot find the message, perhaps it was deleted?")

        member = await self.bot.try_user(data[3])
        moderator = ctx.guild.get_member(data[1])

        description = ""
        description += (
            f"\n**Offender:** {member if member else 'Not Found.'} (<@{data[3]}>)"\
            f"\n**Reason:** {reason}"
        )
        if data[5]:
            description += f"\n**Duration:** {data[5]}"
        description += (
            f"\n**Responsible moderator:** {moderator if moderator else 'Not Found'}"\
            f"\n**Occurred:** {discord.utils.format_dt(pytz.utc.localize(data[0]), 'F')} ({discord.utils.format_dt(pytz.utc.localize(data[0]), 'R')})"
        )

        embed = discord.Embed(title=f"{data[2]} | case {case}", color=self.actions[data[2]], description=description)                      
        embed.set_footer(text=f"ID: {data[3]}")

        await message.edit(embed=embed)

        await self.bot.db.execute("UPDATE modlogs SET reason = $1 WHERE guild_id = $2 AND case_number = $3", reason, ctx.guild.id, case)
        await ctx.check()