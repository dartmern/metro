# Credit this cog to Neutra
# https://github.com/Hecate946/Neutra/blob/ed933823abab40d1e35794bb43fa9df9c1d4ab9b/cogs/batch.py

import asyncio
from collections import defaultdict
import json
import time
from typing import Optional
import discord
from discord.ext import commands, tasks

from bot import MetroBot
from utils.custom_context import MyContext
from utils.useful import Cooldown, Embed, traceback_maker

def setup(bot : MetroBot):
    bot.add_cog(tracking(bot))

class tracking(commands.Cog, description='Module for user and server stats.'):
    def __init__(self, bot : MetroBot):
        self.bot = bot
        self.batch_lock = asyncio.Lock(loop=bot.loop)
        self.message_batch = []
        self.tracking_batch = defaultdict(dict)

        self.message_inserter.start()

    def cog_unload(self):
        self.message_inserter.stop()

    @property
    def emoji(self) -> str:
        return '🔍'

    @tasks.loop(seconds=0.5)
    async def message_inserter(self):
        """
        Bulk inserts messages.
        """
        
        if self.message_batch:  # Insert every message into the db
            query = """
                    INSERT INTO messages2 (unix, timestamp,
                    message_id, author_id, channel_id, server_id)
                    SELECT x.unix, x.timestamp,
                    x.message_id, x.author_id, x.channel_id, x.server_id
                    FROM JSONB_TO_RECORDSET($1::JSONB)
                    AS x(unix REAL, timestamp TIMESTAMP,
                    message_id BIGINT, author_id BIGINT,
                    channel_id BIGINT, server_id BIGINT)
                    """
            async with self.batch_lock:
                data = json.dumps(self.message_batch)
                await self.bot.db.execute(query, data)
                self.message_batch.clear()
                

    @commands.Cog.listener('on_message')
    async def message_tracking(self, message : discord.Message):
        if message.guild:
            self.bot.message_stats[message.guild.id] += 1
            async with self.batch_lock:
                self.message_batch.append(
                    {
                        "unix" : message.created_at.timestamp(),
                        "timestamp" : str(message.created_at.utcnow()),
                        "message_id" : message.id,
                        "author_id" : message.author.id,
                        "channel_id" : message.channel.id,
                        "server_id" : message.guild.id
                    }
                )
                self.tracking_batch[message.author.id] = {time.time() : "sending a message"}


    @commands.command(aliases=['gm'])
    async def messages_guild(self, ctx : MyContext):
        """
        Show total amount of messages sent in this guild.
        """
        await ctx.defer()
        query = """
                SELECT COUNT(*) AS c
                FROM messages
                WHERE server_id = $1
                """
        count = await self.bot.db.fetchval(query, ctx.guild.id)

        embed = Embed()
        embed.colour = discord.Colour.green()
        embed.description = f'I have seen **{count}** message{"" if count == 1 else "s"} in this guild.'\
                            f"\n*Message tracking started {discord.utils.format_dt(ctx.guild.me.joined_at, 'R')}*"
        await ctx.send(embed=embed)

    @commands.command(aliases=['msgs'])
    @commands.check(Cooldown(2, 10, 2, 8, commands.BucketType.member))
    async def messages(self, ctx : MyContext, *, member : Optional[discord.Member] = commands.Option(description='Member\'s messages you want to check')):
        """
        Show total amount of messages a member has sent.
        """
        member = member or ctx.author
        await ctx.defer()
        query = """
                SELECT COUNT(*) as c
                FROM messages
                WHERE author_id = $1
                AND server_id = $2
                """
        count = await self.bot.db.fetchval(query, member.id, ctx.guild.id)

        embed = Embed()
        embed.description = f'**{member}** has sent **{count}** message{"" if count == 1 else "s"}'\
                            f"\n*Message tracking started {discord.utils.format_dt(ctx.guild.me.joined_at, 'R')}*"
        await ctx.send(embed=embed)

    @commands.command(aliases=['mg'])
    @commands.check(Cooldown(2, 10, 2, 8, commands.BucketType.member))
    async def messages_global(self, ctx : MyContext, *, user : Optional[discord.User] = commands.Option(description='User\'s messages you want to check')):
        """
        Show total amount of messages a user has sent globally.
        
        This only inculdes guilds I share with the user.
        """
        user = user or ctx.author
        await ctx.defer()
        query = """
                SELECT COUNT(*) as c
                FROM messages
                WHERE author_id = $1
                """
        count = await self.bot.db.fetchval(query, user.id)

        embed = Embed()
        embed.colour = discord.Colour.yellow()
        embed.description = f'**{user}** has sent **{count}** message{"" if count == 1 else "s"} globally'\
                            f"\n*Message tracking started {discord.utils.format_dt(ctx.guild.me.joined_at, 'R')}*"
        await ctx.send(embed=embed)

    @commands.command(aliases=['mt'])
    async def messages_total(self, ctx : MyContext):
        """Get the total amount of messages sent."""
        await ctx.defer()
        query = """
                SELECT COUNT(*) as c
                FROM messages
                """
        count = await self.bot.db.fetchval(query)

        embed = Embed()
        embed.colour = discord.Colour.green()
        embed.description = f"I have seen **{count}** message{'' if count == 1 else 's'}"\
                            f"\n*Message tracking started <t:1639287704:R>*"
        await ctx.send(embed=embed)