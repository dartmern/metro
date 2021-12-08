# R. Danny's reminder cog with small amounts of modifications.
# https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/reminder.py

# Credits to Danny for making this


from utils.useful import Embed
import discord
from discord.ext import commands, menus

from utils.remind_utils import UserFriendlyTime

import datetime
import asyncio
import json
import datetime
import asyncpg

from utils.custom_context import MyContext



from datetime import timedelta

from utils.remind_utils import human_timedelta

from utils.pages import ExtraPages

class MySource(menus.ListPageSource):
    def __init__(self, data):
        super().__init__(data, per_page=5)

    async def format_page(self, menu, entries):

        embed= Embed()

        for i in entries:
            embed.add_field(name=f'ID: {i.get("id")}:  in {human_timedelta(i.get("expires"))}',value=i.get("?column?"),inline=False)

        embed.set_footer(text=f'{len(entries)} reminder{"s" if len(entries) > 1 else ""}')

        return embed



class Timer:
    __slots__ = ("args", "kwargs", "event", "id", "created_at", "expires")

    def __init__(self, *, record):
        self.id = record["id"]
        extra = record["extra"]
        self.args = extra.get("args", [])
        self.kwargs = extra.get("kwargs", {})
        self.event = record["event"]
        self.created_at = record["created"]
        self.expires = record["expires"]

    @classmethod
    def temporary(cls, *, expires, created, event, args, kwargs):
        pseudo = {
            "id": None,
            "extra": {"args": args, "kwargs": kwargs},
            "event": event,
            "created": created,
            "expires": expires,
        }
        return cls(record=pseudo)

    def __eq__(self, other):
        try:
            return self.id == other.id
        except AttributeError:
            return False

    def __hash__(self):
        return hash(self.id)

    @property
    def human_delta(self):
        return human_timedelta(self.created_at)

    def __repr__(self):
        return f"<Timer created={self.created_at} expires={self.expires} event={self.event}>"




class reminder(commands.Cog):
    """
    :thinking: Module for handling all timed tasks.
    """

    def __init__(self, bot):
        self.bot = bot
        self._have_data = asyncio.Event(loop=bot.loop)
        self._current_timer = None
        self._task = bot.loop.create_task(self.dispatch_timers())

    def cog_unload(self):
        self._task.cancel()

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send(error)
        if isinstance(error, commands.TooManyArguments):
            await ctx.send(
                f"You called the {ctx.command.name} command with too many arguments."
            )

    async def get_active_timer(self, *, connection=None, days=7):
        query = "SELECT * FROM reminders WHERE expires < (CURRENT_DATE + $1::interval) ORDER BY expires LIMIT 1;"
        con = connection or self.bot.db

        record = await con.fetchrow(query, timedelta(days=days))
        if record:
            if type(record["extra"]) is dict:
                extra = record["extra"]
            else:
                extra = json.loads(record["extra"])
            record_dict = {
                "id": record["id"],
                "extra": extra,
                "event": record["event"],
                "created": record["created"],
                "expires": record["expires"],
            }
        return Timer(record=record_dict) if record else None

    async def wait_for_active_timers(self, *, connection=None, days=7):

        timer = await self.get_active_timer(connection=connection, days=days)
        
        if timer is not None:
            self._have_data.set()
            return timer

        self._have_data.clear()
        self._current_timer = None
        await self._have_data.wait()
        return await self.get_active_timer(connection=connection, days=days)

    async def call_timer(self, timer):
        
        # delete the timer
        query = "DELETE FROM reminders WHERE id=$1;"
        await self.bot.db.execute(query, timer.id)

        # dispatch the event
        event_name = f"{timer.event}_timer_complete"
        self.bot.dispatch(event_name, timer)

    async def dispatch_timers(self):

        try:            
            while not self.bot.is_closed():
                
                # can only asyncio.sleep for up to ~48 days reliably
                # so we're gonna cap it off at 40 days
                # see: http://bugs.python.org/issue20493
                timer = self._current_timer = await self.wait_for_active_timers(days=40)
                
                now = datetime.datetime.utcnow()
                if timer.expires >= now:
                    to_sleep = (timer.expires - now).total_seconds()
                    await asyncio.sleep(to_sleep)

                await self.call_timer(timer)
        except asyncio.CancelledError:
            raise
        except (OSError, discord.ConnectionClosed, asyncpg.PostgresConnectionError):
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.dispatch_timers())
        except Exception as e:
            raise e

    async def short_timer_optimisation(self, seconds, timer):
        await asyncio.sleep(seconds)
        event_name = f"{timer.event}_timer_complete"
        self.bot.dispatch(event_name, timer)


    async def create_timer(self, *args, **kwargs):
        """Creates a timer.
        Parameters
        -----------
        when: datetime.datetime
            When the timer should fire.
        event: str
            The name of the event to trigger.
            Will transform to 'on_{event}_timer_complete'.
        \*args
            Arguments to pass to the event
        \*\*kwargs
            Keyword arguments to pass to the event
        connection: asyncpg.Connection
            Special keyword-only argument to use a specific connection
            for the DB request.
        created: datetime.datetime
            Special keyword-only argument to use as the creation time.
            Should make the timedeltas a bit more consistent.
        Note
        ------
        Arguments and keyword arguments must be JSON serialisable.
        Returns
        --------
        :class:`Timer`
        """
        when, event, *args = args

        try:
            connection = kwargs.pop('connection')
        except KeyError:
            connection = self.bot.db

        try:
            now = kwargs.pop('created')
        except KeyError:
            now = discord.utils.utcnow()

        # Remove timezone information since the database does not deal with it
        when = when.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        now = now.astimezone(datetime.timezone.utc).replace(tzinfo=None)

        timer = Timer.temporary(event=event, args=args, kwargs=kwargs, expires=when, created=now)
        delta = (when - now).total_seconds()
        if delta <= 60:
            # a shortcut for small timers
            self.bot.loop.create_task(self.short_timer_optimisation(delta, timer))
            return timer

        next_id_query = """SELECT MAX(id) FROM reminders;"""
        id = await connection.fetch(next_id_query)

        if id[0].get('max') is None:
            id = 1
        else:
            id = int(id[0].get('max')) + 1


        query = """INSERT INTO reminders (id, event, extra, expires, created)
                   VALUES ($1, $2, $3::jsonb, $4, $5)
                   RETURNING id;
                """

        jsonb = json.dumps({"args": args, "kwargs": kwargs})

        row = await connection.fetchrow(query, id, event, jsonb, when, now)
        timer.id = row[0]

        # only set the data check if it can be waited on
        if delta <= (86400 * 40): # 40 days
            self._have_data.set()

        # check if this timer is earlier than our currently run timer
        if self._current_timer and when < self._current_timer.expires:
            # cancel the task and re-run it
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.dispatch_timers())

        return timer

    @commands.group(
        aliases=['remind','rm'],
        usage="<when>",
        invoke_without_command=True,
        slash_command=True

    )
    @commands.bot_has_permissions(send_messages=True)
    async def reminder(self, ctx, *, when : UserFriendlyTime(commands.clean_content, default='\u2026')):
        """Reminds you of something after a certain amount of time.

        The input can be any direct date (e.g. YYYY-MM-DD) or a human
        readable offset. Examples:

        - "next thursday at 3pm do something funny"
        - "do the dishes tomorrow"
        - "in 3 days do the thing"
        - "2d unmute someone"

        Times are in UTC.
        """

        timer = await self.create_timer(
            when.dt,
            "reminder",
            ctx.author.id,
            ctx.channel.id,
            when.arg,
            connection=self.bot.db,
            created=ctx.message.created_at,
            message_id=ctx.message.id
        )

        delta = human_timedelta(when.dt - datetime.timedelta(seconds=2))
        #dunno why it's off by 3 seconds but this should fix
        await ctx.send(f'Alright, I will remind you about {when.arg} in {delta}\nTimer id: {timer.id}')

    @reminder.command(
        aliases=['remind','rm'],
        usage="<when>",
        slash_command=True

    )
    @commands.bot_has_permissions(send_messages=True)
    async def create(self, ctx, *, when : UserFriendlyTime(commands.clean_content, default='\u2026')):
        """Reminds you of something after a certain amount of time.

        The input can be any direct date (e.g. YYYY-MM-DD) or a human
        readable offset. Examples:

        - "next thursday at 3pm do something funny"
        - "do the dishes tomorrow"
        - "in 3 days do the thing"
        - "2d unmute someone"

        Times are in UTC.
        """

        timer = await self.create_timer(
            when.dt,
            "reminder",
            ctx.author.id,
            ctx.channel.id,
            when.arg,
            connection=self.bot.db,
            created=ctx.message.created_at,
            message_id=ctx.message.id
        )
        
        delta = human_timedelta(when.dt - datetime.timedelta(seconds=2))
        #dunno why it's off by 3 seconds but this should fix
        await ctx.send(f'Alright, I will remind you about {when.arg} in {delta}\nTimer id: {timer.id}')

    @reminder.command(
        name='list',
        aliases=['show'],
        slash_command=True
    )
    async def reminders_list(self, ctx):
        """
        Display all your current reminders.
        """

        query = """
                SELECT id, expires, extra #>> '{args,2}'
                FROM reminders
                WHERE event = 'reminder'
                AND extra #>> '{args,0}' = $1
                ORDER BY expires;
                """

        records = await self.bot.db.fetch(query, str(ctx.author.id))

        if not records:
            return await ctx.send('You have no reminders.')

        menu = ExtraPages(source=MySource(records))
        
        await menu.start(ctx)

    
    @reminder.command(
        name='delete',
        aliases=['cancel','remove'],
        slash_command=True
    )
    async def reminder_remove(self, ctx, *, id : int):
        """
        Deletes a reminder by it's id
        """        

        query = """
                DELETE FROM reminders
                WHERE id=$1
                AND event = 'reminder'
                AND extra #>> '{args,0}' = $2;
                """

        status = await self.bot.db.execute(query, id, str(ctx.author.id))
        if status == "DELETE 0":
            return await ctx.send('Could not delete any reminders with that ID')

        # if the current timer is being deleted
        if self._current_timer and self._current_timer.id == id:
            # cancel the task and re-run it
            self._task.cancel()
            self._task = self.bot.loop.create_task(self.dispatch_timers())

        await ctx.send("Successfully deleted reminder.")


    @reminder.command(
        name='clear',
        aliases=['wipe'],
        slash_command=True
    )
    async def reminder_clear(self, ctx):
        """
        Clear all reminders you set.
        """

        query = """
                SELECT COUNT(*)
                FROM reminders
                WHERE event = 'reminder'
                AND extra #>> '{args,0}' = $1;
                """

        author_id = str(ctx.author.id)
        total = await self.bot.db.fetchrow(query, author_id)
        total = total[0]

        if total == 0:
            return await ctx.send("You have no reminders to clear.")

        confirm = await ctx.confirm(f'Are you sure you want to clear **{total}** reminder(s)', timeout=30)

        if confirm is None:
            return await ctx.send('Timed out.')

        if confirm is False:
            return await ctx.send('Canceled.')

        query = """DELETE FROM reminders WHERE event = 'reminder' AND extra #>> '{args,0}' = $1;"""

        await self.bot.db.execute(query, author_id)
        await ctx.send(f'Successfully deleted **{total}** reminder(s)')
        
    
    @commands.Cog.listener()
    async def on_reminder_timer_complete(self, timer):
        

        author_id, channel_id, message = timer.args

        try:
            channel = self.bot.get_channel(int(channel_id)) or (
                await self.bot.fetch_channel(int(channel_id))
            )
        except (discord.HTTPException, discord.NotFound):
            return

        try:
            author = self.bot.get_user(int(author_id)) or (
                await self.bot.fetch_user(int(author_id))
            )
        except (discord.HTTPException, discord.NotFound):
            return

        message_id = timer.kwargs.get("message_id")


        guild_id = channel.guild.id if isinstance(channel, (discord.TextChannel, discord.Thread)) else '@me'

        
        msg = f"<@{author_id}>, {timer.human_delta}, you wanted me to remind you about: {message}"

        try:
            await channel.send(msg)
        except discord.HTTPException:
            return
        









def setup(bot):
    bot.add_cog(reminder(bot))