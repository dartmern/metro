from typing import Optional
import discord
from discord.ext import commands
import pytz
import asyncpg

from bot import MetroBot
from utils.custom_context import MyContext
from utils.useful import Cooldown

def setup(bot: MetroBot):
    bot.add_cog(_logging(bot))

class _logging(commands.Cog, description='Manage logging related commands.', name='logging'):
    def __init__(self, bot: MetroBot):
        self.bot = bot

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
        await ctx.check()