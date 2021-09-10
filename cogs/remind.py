import discord
from discord.ext import commands
from discord.ext.commands.core import command

from utils.remind_utils import HumanTime, UserFriendlyTime

import datetime
import asyncio
import json
import datetime
import asyncpg



from datetime import timedelta

from utils.remind_utils import format_relative
from dateutil.relativedelta import relativedelta


class plural:
    def __init__(self, value):
        self.value = value

    def __format__(self, format_spec):
        v = self.value
        singular, sep, plural = format_spec.partition("|")
        plural = plural or f"{singular}s"
        if abs(v) != 1:
            return f"{v} {plural}"
        return f"{v} {singular}"


def human_join(seq, delim=", ", final="or"):
    size = len(seq)
    if size == 0:
        return ""

    if size == 1:
        return seq[0]

    if size == 2:
        return f"{seq[0]} {final} {seq[1]}"

    return delim.join(seq[:-1]) + f" {final} {seq[-1]}"


def human_timedelta(dt, *, source=None, accuracy=3, brief=False, suffix=True):
    now = source or discord.utils.utcnow()
    # Microsecond free zone
    now = now.replace(microsecond=0, tzinfo=datetime.timezone.utc)
    dt = dt.replace(microsecond=0, tzinfo=datetime.timezone.utc)

    # This implementation uses relativedelta instead of the much more obvious
    # divmod approach with seconds because the seconds approach is not entirely
    # accurate once you go over 1 week in terms of accuracy since you have to
    # hardcode a month as 30 or 31 days.
    # A query like "11 months" can be interpreted as "!1 months and 6 days"
    if dt > now:
        delta = relativedelta(dt, now)
        suffix = ""
    else:
        delta = relativedelta(now, dt)
        suffix = " ago" if suffix else ""

    attrs = [
        ("year", "y"),
        ("month", "mo"),
        ("day", "d"),
        ("hour", "h"),
        ("minute", "m"),
        ("second", "s"),
    ]

    output = []
    for attr, brief_attr in attrs:
        elem = getattr(delta, attr + "s")
        if not elem:
            continue

        if attr == "day":
            weeks = delta.weeks
            if weeks:
                elem -= weeks * 7
                if not brief:
                    output.append(format(plural(weeks), "week"))
                else:
                    output.append(f"{weeks}w")

        if elem <= 0:
            continue

        if brief:
            output.append(f"{elem}{brief_attr}")
        else:
            output.append(format(plural(elem), attr))

    if accuracy is not None:
        output = output[:accuracy]

    if accuracy is not None:
        output = output[:accuracy]

    if len(output) == 0:
        return "1 second" + suffix
    else:
        if not brief:
            return human_join(output, final="and") + suffix
        else:
            return " ".join(output) + suffix

class Timer:
    __slots__ = ('args', 'kwargs', 'event', 'id', 'created_at', 'expires')

    def __init__(self, *, record):
        self.id = record['id']

        extra = record['extra']
        self.args = extra.get('args', [])
        self.kwargs = extra.get('kwargs', {})
        self.event = record['event']
        self.created_at = record['created']
        self.expires = record['expires']

    @classmethod
    def temporary(cls, *, expires, created, event, args, kwargs):
        pseudo = {
            'id': None,
            'extra': { 'args': args, 'kwargs': kwargs },
            'event': event,
            'created': created,
            'expires': expires
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
        return f'<Timer created={self.created_at} expires={self.expires} event={self.event}>'


class reminder(commands.Cog, description="Reminder utilities."):
    def __init__(self, bot):
        self.bot = bot

    async def get_active_timer(self, *, connection=None, days=7):
        query = "SELECT * FROM reminders WHERE expires < (CURRENT_DATE + $1::interval) ORDER BY expires LIMIT 1;"
        con = connection or self.bot.db

        record = await con.fetchrow(query, datetime.timedelta(days=days))
        return Timer(record=record) if record else None

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
        await self.bot.pool.execute(query, timer.id)

        # dispatch the event
        event_name = f'{timer.event}_timer_complete'
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

    async def short_timer_optimisation(self, seconds, timer):
        await asyncio.sleep(seconds)
        event_name = f'{timer.event}_timer_complete'
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

        query = """INSERT INTO reminders (event, extra, expires, created)
                   VALUES ($1, $2::jsonb, $3, $4)
                   RETURNING id;
                """

        jsonb = json.dumps({"args": args, "kwargs": kwargs})
        row = await connection.fetchrow(
            query,
            event,
            jsonb,
            when,
            now,
        )
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
        invoke_without_command=True
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

        delta = human_timedelta(when.dt)
        await ctx.send(f'Alright, I will remind you about {when.arg} in {delta}')


    
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