from discord.ext import commands
import re
import discord
import parsedatetime as pdt
import datetime
from dateutil.relativedelta import relativedelta

# this utils file is mainly helper functions from R. Danny
# https://github.com/Rapptz/RoboDanny/blob/1fb95d76d1b7685e2e2ff950e11cddfc96efbfec/cogs/utils/time.py
# mainly anything to do with time converting including the UserFriendlyTime class found in lots of my commands
# all credit goes to danny for making it

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

    if len(output) == 0:
        return "now"
    else:
        if not brief:
            return human_join(output, final="and") + suffix
        else:
            return " ".join(output) + suffix



class PastShortTime:
    compiled = re.compile(
        """(?:(?P<years>[0-9])(?:years?|y))?             # e.g. 2y
                             (?:(?P<months>[0-9]{1,2})(?:months?|mo))?     # e.g. 2months
                             (?:(?P<weeks>[0-9]{1,4})(?:weeks?|w))?        # e.g. 10w
                             (?:(?P<days>[0-9]{1,5})(?:days?|d))?          # e.g. 14d
                             (?:(?P<hours>[0-9]{1,5})(?:hours?|h))?        # e.g. 12h
                             (?:(?P<minutes>[0-9]{1,5})(?:minutes?|m))?    # e.g. 10m
                             (?:(?P<seconds>[0-9]{1,5})(?:seconds?|s))?    # e.g. 15s
                          """,
        re.VERBOSE,
    )

    def __init__(self, argument, *, now=None):
        match = self.compiled.fullmatch(argument)
        if match is None or not match.group(0):
            raise commands.BadArgument("Invalid time provided")

        data = {k: int(v) for k, v in match.groupdict(default=0).items()}
        now = now or discord.utils.utcnow()
        self.dt = now - relativedelta(**data)
        print("THIS IS THE DT")
        print(self.dt)

    @classmethod
    async def convert(cls, ctx, argument):
        return cls(argument, now=ctx.message.created_at)


class HumanTime:
    calendar = pdt.Calendar(version=pdt.VERSION_CONTEXT_STYLE)

    def __init__(self, argument, *, now=None):
        now = discord.utils.utcnow()
        dt, status = self.calendar.parseDT(argument, sourceTime=now)
        if not status.hasDateOrTime:
            raise commands.BadArgument(
                'Invalid time provided, try e.g. "tomorrow" or "3 days"'
            )

        if not status.hasTime:
            # replace it with the current time
            dt = dt.replace(
                hour=now.hour,
                minute=now.minute,
                second=now.second,
                microsecond=now.microsecond,
                tzinfo=datetime.timezone.utc,
            )
        else:
            dt = dt.replace(tzinfo=datetime.timezone.utc)

        self.dt = dt
        self._past = dt < now

    @classmethod
    async def convert(cls, ctx, argument):
        return cls(argument, now=ctx.message.created_at)


class PastHumanTime:
    calendar = pdt.Calendar(version=pdt.VERSION_CONTEXT_STYLE)

    def __init__(self, argument, *, now=None):
        now = now or discord.utils.utcnow()
        argument = argument + " ago"
        dt, status = self.calendar.parseDT(argument, sourceTime=now)
        if not status.hasDateOrTime:
            raise commands.BadArgument(
                'Invalid time provided, try e.g. "yesterday" or "3 days ago"'
            )

        if not status.hasTime:
            # replace it with the current time
            dt = dt.replace(
                hour=now.hour,
                minute=now.minute,
                second=now.second,
                microsecond=now.microsecond,
                tzinfo=datetime.timezone.utc,
            )
        else:
            dt = dt.replace(tzinfo=datetime.timezone.utc)

        self.dt = dt
        self._past = dt < now

    @classmethod
    async def convert(cls, ctx, argument):
        return cls(argument, now=ctx.message.created_at)


class ShortTime:
    compiled = re.compile("""(?:(?P<years>[0-9])(?:years?|y))?             # e.g. 2y
                             (?:(?P<months>[0-9]{1,2})(?:months?|mo))?     # e.g. 2months
                             (?:(?P<weeks>[0-9]{1,4})(?:weeks?|w))?        # e.g. 10w
                             (?:(?P<days>[0-9]{1,5})(?:days?|d))?          # e.g. 14d
                             (?:(?P<hours>[0-9]{1,5})(?:hours?|h))?        # e.g. 12h
                             (?:(?P<minutes>[0-9]{1,5})(?:minutes?|m))?    # e.g. 10m
                             (?:(?P<seconds>[0-9]{1,5})(?:seconds?|s))?    # e.g. 15s
                          """, re.VERBOSE)

    def __init__(self, argument, *, now=None):
        match = self.compiled.fullmatch(argument)
        if match is None or not match.group(0):
            raise commands.BadArgument('invalid time provided')

        data = { k: int(v) for k, v in match.groupdict(default=0).items() }
        now = now or datetime.datetime.now(datetime.timezone.utc)
        self.dt = now + relativedelta(**data)

    @classmethod
    async def convert(cls, ctx, argument):
        return cls(argument, now=ctx.message.created_at)

class Time(HumanTime):
    def __init__(self, argument, *, now=None):
        try:
            o = ShortTime(argument, now=now)
        except Exception as e:
            super().__init__(argument)
        else:
            self.dt = o.dt
            self._past = False


class NegativeTime(PastHumanTime):
    def __init__(self, argument, *, now=None):
        try:
            o = PastShortTime(argument, now=now)
        except Exception as e:
            print(e)
            super().__init__(argument)
        else:
            self.dt = o.dt
            self._past = False


class FutureTime(Time):
    def __init__(self, argument, *, now=None):
        super().__init__(argument, now=now)
        self.argument = argument

        if self._past:
            raise commands.BadArgument("this time is in the past")


class PastTime(NegativeTime):
    def __init__(self, argument, *, now=None):
        super().__init__(argument, now=now)



class UserFriendlyTime(commands.Converter):
    """That way quotes aren't absolutely necessary."""

    def __init__(self, converter=None, *, default=None):
        if isinstance(converter, type) and issubclass(converter, commands.Converter):
            converter = converter()

        if converter is not None and not isinstance(converter, commands.Converter):
            raise TypeError("commands.Converter subclass necessary.")

        self.converter = converter
        self.default = default

    async def check_constraints(self, ctx, now, remaining):
        if not hasattr(self, "dt"):
            self.arg = remaining
            self.dt = None
            return self
        if self.dt < now:
            raise commands.BadArgument("This time is in the past.")

        if not remaining:
            if self.default is None:
                raise commands.BadArgument("Missing argument after the time.")
            remaining = self.default

        if self.converter is not None:
            self.arg = await self.converter.convert(ctx, remaining)
        else:
            self.arg = remaining
        return self

    def copy(self):
        cls = self.__class__
        obj = cls.__new__(cls)
        obj.converter = self.converter
        obj.default = self.default
        return obj

    async def convert(self, ctx, argument):
        # Create a copy of ourselves to prevent race conditions from two
        # events modifying the same instance of a converter
        #argument = argument.replace('for')  # people sometimes use "for" in the time string
        result = self.copy()
        try:
            calendar = HumanTime.calendar
            regex = ShortTime.compiled
            now = ctx.message.created_at

            match = regex.match(argument)
            if match is not None and match.group(0):    
                data = {k: int(v) for k, v in match.groupdict(default=0).items()}
                remaining = argument[match.end() :].strip()
                result.dt = now + relativedelta(**data)
                return await result.check_constraints(ctx, now, remaining)

            # apparently nlp does not like "from now"
            # it likes "from x" in other cases though so let me handle the 'now' case
            argument = argument.replace(
                ",", ""
            )  # In case someone actually says 3,600 seconds
            if argument.endswith("from now"):
                argument = argument[:-8].strip()

            if argument[0:2] == "me":
                # starts with "me to", "me in", or "me at "
                if argument[0:6] in ("me to ", "me in ", "me at "):
                    argument = argument[6:]

            if argument.strip().startswith("for "):
                argument = argument[4:]

            elements = calendar.nlp(argument, sourceTime=now)
            if elements is None or len(elements) == 0:
                return await result.check_constraints(ctx, now, argument)

            # handle the following cases:
            # "date time" foo
            # date time foo
            # foo date time

            # first the first two cases:
            dt, status, begin, end, dt_string = elements[0]

            if not status.hasDateOrTime:
                raise commands.BadArgument(
                    "Invalid time provided, try `tomorrow` or `2 days`."
                )
            if begin not in (0, 1) and end != len(argument):
                raise commands.BadArgument(
                    f"I did not understand your input. Please use the `{ctx.clean_prefix}examples` command for assistance."
                )

            if not status.hasTime:
                # replace it with the current time
                dt = dt.replace(
                    hour=now.hour,
                    minute=now.minute,
                    second=now.second,
                    microsecond=now.microsecond,
                    tzinfo=datetime.timezone.utc,
                )
            else:
                dt = dt.replace(tzinfo=datetime.timezone.utc)

            # if midnight is provided, just default to next day
            if status.accuracy == pdt.pdtContext.ACU_HALFDAY:
                dt = dt.replace(day=now.day + 1)

            result.dt = dt

            if begin in (0, 1):
                if begin == 1:
                    # check if it's quoted:
                    # if argument[0] != '"':
                    #     raise commands.BadArgument(
                    #         "Expected quote before time input..."
                    #     )

                    # if not (end < len(argument) and argument[end] == '"'):
                    #     raise commands.BadArgument(
                    #         "If the time is quoted, you must unquote it."
                    #     )

                    remaining = argument[end + 1 :].lstrip(" ,.!")
                else:
                    remaining = argument[end:].lstrip(" ,.!")
            elif len(argument) == end:
                remaining = argument[:begin].strip()

            return await result.check_constraints(ctx, now, remaining)
        except Exception as e:
            print(f"Error in UserFriendlyTime: {e}")



def format_dt(dt, style=None):
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)

    if style is None:
        return f'<t:{int(dt.timestamp())}>'
    return f'<t:{int(dt.timestamp())}:{style}>'

def format_relative(dt):
    return format_dt(dt, 'R')