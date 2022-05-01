import discord
from discord.ext import commands, menus
from discord.ext.menus import First, Last

from discord.ext.commands.cooldowns import BucketType

import re
import asyncio

import utils.checks


from typing import Dict, Any, Optional


from utils.remind_utils import human_timedelta

PAGE_REGEX = r'(Page)?(\s)?((\[)?((?P<current>\d+)/(?P<last>\d+))(\])?)'

async def delete_silent(message: discord.Message, *, delay: Optional[float] = None):
    """Replaces the `silent` kwarg in edpy."""
    try:
        await message.delete(delay=delay)
    except discord.HTTPException:
        pass

class OldRoboPages(menus.MenuPages):
    def __init__(self, source):
        super().__init__(source=source, check_embeds=True)
        self.input_lock = asyncio.Lock()

    async def finalize(self, timed_out):
        try:
            if timed_out:
                await self.message.clear_reactions()
            else:
                await self.message.delete()
        except discord.HTTPException:
            pass

    @menus.button('\N{INFORMATION SOURCE}\ufe0f', position=menus.Last(3))
    async def show_help(self, payload):
        """shows this message"""
        embed = discord.Embed(title='Paginator help', description='Hello! Welcome to the help page.')
        messages = []
        for (emoji, button) in self.buttons.items():
            messages.append(f'{emoji}: {button.action.__doc__}')

        embed.add_field(name='What are these reactions for?', value='\n'.join(messages), inline=False)
        embed.set_footer(text=f'We were on page {self.current_page + 1} before this message.')
        await self.message.edit(content=None, embed=embed)

        async def go_back_to_current_page():
            await asyncio.sleep(30.0)
            await self.show_page(self.current_page)

        self.bot.loop.create_task(go_back_to_current_page())

    @menus.button('\N{INPUT SYMBOL FOR NUMBERS}', position=menus.Last(2), lock=False)
    async def numbered_page(self, payload):
        """lets you type a page number to go to"""
        if self.input_lock.locked():
            return

        async with self.input_lock:
            channel = self.message.channel
            author_id = payload.user_id
            to_delete = []
            to_delete.append(await channel.send('What page do you want to go to?'))

            def message_check(m):
                return m.author.id == author_id and \
                       channel == m.channel and \
                       m.content.isdigit()

            try:
                msg = await self.bot.wait_for('message', check=message_check, timeout=30.0)
            except asyncio.TimeoutError:
                to_delete.append(await channel.send('Took too long.'))
                await asyncio.sleep(5)
            else:
                page = int(msg.content)
                to_delete.append(msg)
                await self.show_checked_page(page - 1)

            try:
                await channel.delete_messages(to_delete)
            except Exception:
                pass


class fuzzy:

    @staticmethod
    def finder(to_find, collection, *, key=None, lazy=True):
        suggestions = []
        text = str(to_find)
        pat = '.*?'.join(map(re.escape, text))
        regex = re.compile(pat, flags=re.IGNORECASE)
        for item in collection:
            to_search = key(item) if key else item
            r = regex.search(to_search)
            if r:
                suggestions.append((len(r.group()), r.start(), item))

        def sort_key(tup):
            if key:
                return tup[0], tup[1], key(tup[2])
            return tup

        if lazy:
            return (z for _, _, z in sorted(suggestions, key=sort_key))
        else:
            return [z for _, _, z in sorted(suggestions, key=sort_key)]


def pages(per_page=1, show_page=True):
    """Compact ListPageSource that was originally made teru but was modified"""
    def page_source(coro):
        async def create_page_header(self, menu, entry):
            result = await discord.utils.maybe_coroutine(coro, self, menu, entry)
            return menu.generate_page(result, self._max_pages)

        def __init__(self, list_pages):
            super(self.__class__, self).__init__(list_pages, per_page=per_page)
        kwargs = {
            '__init__': __init__,
            'format_page': (coro, create_page_header)[show_page]
        }
        return type(coro.__name__, (menus.ListPageSource,), kwargs)
    return page_source



def clean_code(content):
    if content.startswith("```") and content.endswith("```"):
        return "\n".join(content.split("\n")[1:])[:-3]
    if content.startswith("```py") and content.endswith("```"):
        return "\n".join(content.split("\n")[1:])[:-3]
    else:
        return content


class Embed(discord.Embed):
    def __init__(self, color=0x1ABC9C, fields=(), field_inline=False, **kwargs):
        super().__init__(color=color, **kwargs)
        for n, v in fields:
            self.add_field(name=n, value=v, inline=field_inline)


class Cooldown:
    def __init__(
        self,
        rate: int,
        per: float,
        alter_rate: int,
        alter_per: float,
        bucket: commands.BucketType,
    ):
        self.default_mapping = commands.CooldownMapping.from_cooldown(rate, per, bucket)
        self.altered_mapping = commands.CooldownMapping.from_cooldown(
            alter_rate, alter_per, bucket
        )

    def __call__(self, ctx):
        
        if ctx.bot.premium_guilds.get(ctx.guild.id):# or ctx.bot.premium_users.get(ctx.author.id):
            ctx.bucket = self.altered_mapping.get_bucket(ctx.message)
        else:
            ctx.bucket = self.default_mapping.get_bucket(ctx.message)
        retry_after = ctx.bucket.update_rate_limit()
        if retry_after:
            raise commands.CommandOnCooldown(ctx.bucket, retry_after, BucketType.user)
        return True


def ts_now(type : Optional[str] = 'f'):
    time =  discord.utils.format_dt(discord.utils.utcnow(), type)
    return time


def chunkIt(seq, num):
    avg = len(seq) / float(num)
    out = []
    last = 0.0

    while last < len(seq):
        out.append(seq[int(last):int(last + avg)])
        last += avg

    return out


from jishaku.shim.paginator_base import EMOJI_DEFAULT


class PaginatorInterface:  # pylint: disable=too-many-instance-attributes
    """
    A message and reaction based interface for paginators.
    This allows users to interactively navigate the pages of a Paginator, and supports live output.
    An example of how to use this with a standard Paginator:
    .. code:: python3
        from discord.ext import commands
        from jishaku.paginators import PaginatorInterface
        # In a command somewhere...
            # Paginators need to have a reduced max_size to accommodate the extra text added by the interface.
            paginator = commands.Paginator(max_size=1900)
            # Populate the paginator with some information
            for line in range(100):
                paginator.add_line(f"Line {line + 1}")
            # Create and send the interface.
            # The 'owner' field determines who can interact with this interface. If it's None, anyone can use it.
            interface = PaginatorInterface(ctx.bot, paginator, owner=ctx.author)
            await interface.send_to(ctx)
            # send_to creates a task and returns control flow.
            # It will raise if the interface can't be created, e.g., if there's no reaction permission in the channel.
            # Once the interface has been sent, line additions have to be done asynchronously, so the interface can be updated.
            await interface.add_line("My, the Earth sure is full of things!")
            # You can also check if it's closed using the 'closed' property.
            if not interface.closed:
                await interface.add_line("I'm still here!")
    """

    def __init__(self, bot: commands.Bot, paginator: commands.Paginator, **kwargs):
        if not isinstance(paginator, commands.Paginator):
            raise TypeError('paginator must be a commands.Paginator instance')

        self._display_page = 0

        self.bot = bot

        self.message = None
        self.paginator = paginator

        self.owner = kwargs.pop('owner', None)
        self.emojis = kwargs.pop('emoji', EMOJI_DEFAULT)
        self.timeout = kwargs.pop('timeout', 7200)
        self.delete_message = kwargs.pop('delete_message', False)

        self.sent_page_reactions = False

        self.task: asyncio.Task = None
        self.send_lock: asyncio.Event = asyncio.Event()

        self.close_exception: Exception = None

        if self.page_size > self.max_page_size:
            raise ValueError(
                f'Paginator passed has too large of a page size for this interface. '
                f'({self.page_size} > {self.max_page_size})'
            )

    @property
    def pages(self):
        """
        Returns the paginator's pages without prematurely closing the active page.
        """
        # protected access has to be permitted here to not close the paginator's pages

        # pylint: disable=protected-access
        paginator_pages = list(self.paginator._pages)
        if len(self.paginator._current_page) > 1:
            paginator_pages.append('\n'.join(self.paginator._current_page) + '\n' + (self.paginator.suffix or ''))
        # pylint: enable=protected-access

        return paginator_pages

    @property
    def page_count(self):
        """
        Returns the page count of the internal paginator.
        """

        return len(self.pages)

    @property
    def display_page(self):
        """
        Returns the current page the paginator interface is on.
        """

        self._display_page = max(0, min(self.page_count - 1, self._display_page))
        return self._display_page

    @display_page.setter
    def display_page(self, value):
        """
        Sets the current page the paginator is on. Automatically pushes values inbounds.
        """

        self._display_page = max(0, min(self.page_count - 1, value))

    max_page_size = 2000

    @property
    def page_size(self) -> int:
        """
        A property that returns how large a page is, calculated from the paginator properties.
        If this exceeds `max_page_size`, an exception is raised upon instantiation.
        """
        page_count = self.page_count
        return self.paginator.max_size + len(f'\nPage {page_count}/{page_count}')

    @property
    def send_kwargs(self) -> dict:
        """
        A property that returns the kwargs forwarded to send/edit when updating the page.
        As this must be compatible with both `discord.TextChannel.send` and `discord.Message.edit`,
        it should be a dict containing 'content', 'embed' or both.
        """

        display_page = self.display_page
        page_num = f'\nPage {display_page + 1}/{self.page_count}'
        content = self.pages[display_page] + page_num
        return {'content': content}

    async def add_line(self, *args, **kwargs):
        """
        A proxy function that allows this PaginatorInterface to remain locked to the last page
        if it is already on it.
        """

        display_page = self.display_page
        page_count = self.page_count

        self.paginator.add_line(*args, **kwargs)

        new_page_count = self.page_count

        if display_page + 1 == page_count:
            # To keep position fixed on the end, update position to new last page and update message.
            self._display_page = new_page_count

        # Unconditionally set send lock to try and guarantee page updates on unfocused pages
        self.send_lock.set()

    async def send_to(self, destination: discord.abc.Messageable):
        """
        Sends a message to the given destination with this interface.
        This automatically creates the response task for you.
        """

        self.message = await destination.send(**self.send_kwargs)

        # add the close reaction
        await self.message.add_reaction(self.emojis.close)

        self.send_lock.set()

        if self.task:
            self.task.cancel()

        self.task = self.bot.loop.create_task(self.wait_loop())

        # if there is more than one page, and the reactions haven't been sent yet, send navigation emotes
        if not self.sent_page_reactions and self.page_count > 1:
            await self.send_all_reactions()

        return self

    async def send_all_reactions(self):
        """
        Sends all reactions for this paginator, if any are missing.
        This method is generally for internal use only.
        """

        for emoji in filter(None, self.emojis):
            try:
                await self.message.add_reaction(emoji)
            except discord.NotFound:
                # the paginator has probably already been closed
                break
        self.sent_page_reactions = True

    @property
    def closed(self):
        """
        Is this interface closed?
        """

        if not self.task:
            return False
        return self.task.done()

    async def send_lock_delayed(self):
        """
        A coroutine that returns 1 second after the send lock has been released
        This helps reduce release spam that hits rate limits quickly
        """

        gathered = await self.send_lock.wait()
        self.send_lock.clear()
        await asyncio.sleep(1)
        return gathered

    async def wait_loop(self):  # pylint: disable=too-many-branches, too-many-statements
        """
        Waits on a loop for reactions to the message. This should not be called manually - it is handled by `send_to`.
        """

        start, back, forward, end, close = self.emojis

        def check(payload: discord.RawReactionActionEvent):
            """
            Checks if this reaction is related to the paginator interface.
            """

            owner_check = not self.owner or payload.user_id == self.owner.id

            emoji = payload.emoji
            if isinstance(emoji, discord.PartialEmoji) and emoji.is_unicode_emoji():
                emoji = emoji.name

            tests = (
                owner_check,
                payload.message_id == self.message.id,
                emoji,
                emoji in self.emojis,
                payload.user_id != self.bot.user.id
            )

            return all(tests)

        task_list = [
            self.bot.loop.create_task(coro) for coro in {
                self.bot.wait_for('raw_reaction_add', check=check),
                self.bot.wait_for('raw_reaction_remove', check=check),
                self.send_lock_delayed()
            }
        ]

        try:  # pylint: disable=too-many-nested-blocks
            last_kwargs = None

            while not self.bot.is_closed():
                done, _ = await asyncio.wait(task_list, timeout=self.timeout, return_when=asyncio.FIRST_COMPLETED)

                if not done:
                    raise asyncio.TimeoutError

                for task in done:
                    task_list.remove(task)
                    payload = task.result()

                    if isinstance(payload, discord.RawReactionActionEvent):
                        emoji = payload.emoji
                        if isinstance(emoji, discord.PartialEmoji) and emoji.is_unicode_emoji():
                            emoji = emoji.name

                        if emoji == close:
                            await self.message.delete()
                            return

                        if emoji == start:
                            self._display_page = 0
                        elif emoji == end:
                            self._display_page = self.page_count - 1
                        elif emoji == back:
                            self._display_page -= 1
                        elif emoji == forward:
                            self._display_page += 1

                        if payload.event_type == 'REACTION_ADD':
                            task_list.append(self.bot.loop.create_task(
                                self.bot.wait_for('raw_reaction_add', check=check)
                            ))
                        elif payload.event_type == 'REACTION_REMOVE':
                            task_list.append(self.bot.loop.create_task(
                                self.bot.wait_for('raw_reaction_remove', check=check)
                            ))
                    else:
                        # Send lock was released
                        task_list.append(self.bot.loop.create_task(self.send_lock_delayed()))

                if not self.sent_page_reactions and self.page_count > 1:
                    self.bot.loop.create_task(self.send_all_reactions())
                    self.sent_page_reactions = True  # don't spawn any more tasks

                if self.send_kwargs != last_kwargs:
                    try:
                        await self.message.edit(**self.send_kwargs)
                    except discord.NotFound:
                        # something terrible has happened
                        return

                    last_kwargs = self.send_kwargs

        except (asyncio.CancelledError, asyncio.TimeoutError) as exception:
            self.close_exception = exception

            if self.bot.is_closed():
                # Can't do anything about the messages, so just close out to avoid noisy error
                return

            if self.delete_message:
                return await self.message.delete()

            for emoji in filter(None, self.emojis):
                try:
                    await self.message.remove_reaction(emoji, self.bot.user)
                except (discord.Forbidden, discord.NotFound):
                    pass

        finally:
            for task in task_list:
                task.cancel()


class PaginatorEmbedInterface(PaginatorInterface):
    """
    A subclass of :class:`PaginatorInterface` that encloses content in an Embed.
    """

    def __init__(self, *args, **kwargs):
        self._embed = kwargs.pop('embed', None) or discord.Embed()
        super().__init__(*args, **kwargs)

    @property
    def send_kwargs(self) -> dict:
        display_page = self.display_page
        self._embed.description = self.pages[display_page]
        self._embed.set_footer(text=f'Page {display_page + 1}/{self.page_count}')
        return {'embed': self._embed}

    max_page_size = 2048

    @property
    def page_size(self) -> int:
        return self.paginator.max_size



def get_bot_uptime(bot : commands.Bot, brief : bool =False):
    return human_timedelta(bot.uptime, accuracy=None, brief=brief, suffix=False)



import traceback

def traceback_maker(err, advance: bool = True):
    """ A way to debug your code anywhere """
    header = "Traceback (most recent call last):"
    _traceback = "".join(traceback.format_tb(err.__traceback__))
    error = ("{3}\n{1}{0}: {2}\n").format(type(err).__name__, _traceback, err, header)
    return error if advance else f"{type(err).__name__}: {err}"


class plural:
    def __init__(self, value):
        self.value = value
    def __format__(self, format_spec):
        v = self.value
        singular, sep, plural = format_spec.partition('|')
        plural = plural or f'{singular}s'
        if abs(v) != 1:
            return f'{v} {plural}'
        return f'{v} {singular}'

# Usage for plural
# "You have 0 {plural(1):tasks}"

def human_join(seq, delim=', ', final='or'):
    size = len(seq)
    if size == 0:
        return ''

    if size == 1:
        return seq[0]

    if size == 2:
        return f'{seq[0]} {final} {seq[1]}'

    return delim.join(seq[:-1]) + f' {final} {seq[-1]}'