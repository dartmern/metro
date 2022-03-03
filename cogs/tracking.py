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
        self.no_tracking = {}
        self.message_inserter.start()

        self.command_batch = []

    def cog_unload(self):
        self.message_inserter.stop()

    @property
    def emoji(self) -> str:
        return '🔍'

    async def load_optout(self):
        await self.bot.wait_until_ready()

        records = await self.bot.db.fetch("SELECT id FROM optout WHERE option = True")
        if records:
            for record in records:
                self.no_tracking[record['id']] = True

    @tasks.loop(seconds=0.5)
    async def message_inserter(self):
        """
        Bulk inserts messages.
        """
        
        if self.message_batch:  # Insert every message into the db
            query = """
                    INSERT INTO messages (unix, timestamp,
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
            if self.no_tracking.get(message.author.id) is True:
                return # They don't wanna be tracked
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

    @commands.command(name='optout', usage='[--remove]')
    async def opt_out(self, ctx: MyContext, *, flags: Optional[str]):
        """
        Optout of **all** message tracking.
        Apply `--remove` to remove previous data.
        
        Run `unoptout` to reverse this.
        """
        confirm = await ctx.confirm(
            f"Are you sure you want to optout on all message tracking{' and remove all your previous data?' if flags and '--remove' in flags else '?'}",
            delete_after=True, timeout=60)
        if confirm is False:
            raise commands.BadArgument("Canceled.")
        if confirm is None:
            raise commands.BadArgument("Timed out.")

        self.no_tracking[ctx.author.id] = True
        await self.bot.db.execute("INSERT INTO optout (id, option) VALUES ($1, $2)", ctx.author.id, True)

        if flags and "--remove" in flags:
            await self.bot.db.execute("DELETE FROM messages WHERE author_id = $1", ctx.author.id)

        await ctx.check()
        await ctx.send(f"You are now opted out of all message tracking{' and I removed all your previous data.' if flags and '--remove' in flags else '.'}")
        
    @commands.command(name='unoptout')
    async def unopt_out(self, ctx: MyContext):
        """
        Opt in me tracking your messages.
        
        I **do not** track message content and this use purly
        used for message count commands that you can use.
        """
        self.no_tracking[ctx.author.id] = False
        await self.bot.db.execute("DELETE FROM optout WHERE id=$1", ctx.author.id)

        await ctx.check()
        await ctx.send("You have opted back into message tracking.")
        

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
        embed.description = f'I have seen **{count:,}** message{"" if count == 1 else "s"} in this guild.'\
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
        embed.description = f'**{member}** has sent **{count:,}** message{"" if count == 1 else "s"}'\
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
        embed.description = f"I have seen **{count:,}** message{'' if count == 1 else 's'}"\
                            f"\n*Message tracking started <t:1639287704:R>*"
        await ctx.send(embed=embed)

    async def register_command(self, ctx: MyContext):
        if ctx.command is None:
            return

        command = ctx.command.qualified_name
        self.bot.command_stats[command] += 1
        message = ctx.message

        if ctx.guild is None:
            guild_id = None
        else:
            guild_id = ctx.guild.id

        async with self.batch_lock:
            self._data_batch.append({
                'guild': guild_id,
                'channel': ctx.channel.id,
                'author': ctx.author.id,
                'used': message.created_at.isoformat(),
                'prefix': ctx.prefix,
                'command': command,
                'failed': ctx.command_failed,
            })