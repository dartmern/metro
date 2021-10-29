import discord
from discord.ext import commands, menus


from typing import Optional, Union


import traceback
import asyncio
import os
import io
import datetime
import itertools
import copy
import sys
from collections import Counter
import argparse, shlex
import textwrap
from contextlib import redirect_stdout


from jishaku.paginators import WrappedPaginator
from jishaku.codeblocks import Codeblock, codeblock_converter
from jishaku.features.baseclass import Feature
from jishaku.models import copy_context_with
from jishaku.paginators import WrappedPaginator
import jishaku.modules


from utils.useful import Embed, fuzzy, BaseMenu, pages, get_bot_uptime


class TabularData:
    def __init__(self):
        self._widths = []
        self._columns = []
        self._rows = []

    def set_columns(self, columns):
        self._columns = columns
        self._widths = [len(c) + 2 for c in columns]

    def add_row(self, row):
        rows = [str(r) for r in row]
        self._rows.append(rows)
        for index, element in enumerate(rows):
            width = len(element) + 2
            if width > self._widths[index]:
                self._widths[index] = width

    def add_rows(self, rows):
        for row in rows:
            self.add_row(row)

    def render(self):
        """Renders a table in rST format.
        Example:
        +-------+-----+
        | Name  | Age |
        +-------+-----+
        | Alice | 24  |
        |  Bob  | 19  |
        +-------+-----+
        """

        sep = '+'.join('-' * w for w in self._widths)
        sep = f'+{sep}+'

        to_draw = [sep]

        def get_entry(d):
            elem = '|'.join(f'{e:^{self._widths[i]}}' for i, e in enumerate(d))
            return f'|{elem}|'

        to_draw.append(get_entry(self._columns))
        to_draw.append(sep)

        for row in self._rows:
            to_draw.append(get_entry(row))

        to_draw.append(sep)
        return '\n'.join(to_draw)

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




@pages()
async def show_result(self, menu, entry):
    return f"```\n{entry}```"

class Arguments(argparse.ArgumentParser):
    def error(self, message):
        raise RuntimeError(message)


def restart_program():
        python = sys.executable
        os.execl(python, python, * sys.argv)






class Arguments(argparse.ArgumentParser):
    def error(self, message):
        raise RuntimeError(message)


import os

def clearConsole():
    command = 'clear'
    if os.name in ('nt', 'dos'):  # If Machine is running on Windows, use cls
        command = 'cls'
    os.system(command)





class developer(commands.Cog, description="Developer commands."):
    def __init__(self, bot):
        self.bot = bot
        self._last_result = None

    def cleanup_code(self, content):
        """Automatically removes code blocks from the code."""
        # remove ```py\n```
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])

        # remove `foo`
        return content.strip('` \n')




    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if before.author.id != 525843819850104842:
            return
        await self.bot.process_commands(after)

    @commands.group(
        name="developer",
        aliases=["dev"],
        brief="Developer related commands",
        invoke_without_command=True,
        case_insensitive=True,
        usage="",
        hidden=True
    )
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def developer_cmds(self, ctx):
        """
        Commands reserved for bot developers.
        """
        await ctx.send_help('dev')

    @developer_cmds.command(
        name='invite',
        aliases=['inviteme']
    )
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def invite_to_guild(self, ctx, guild_id : int, **flags : Optional[str]):
        """
        Get a invite with a guild id.

        Create a invite at the top channel in the guild.
        The bot must have create_invite permission in that guild for this to work
        Bot also must be in the guild.

        """


        try:
            guild = self.bot.get_guild(guild_id)
        except:
            return await ctx.reply('Invaild guild id.')

        try:
            invite = await guild.text_channels[0].create_invite()
        except:
            return await ctx.reply('I do not have permissions to create invites in that guild.')

        await ctx.check()
        return await ctx.author.send(invite)
            


    @developer_cmds.command(
        name='guilds',
        aliases=['servers']
    )
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True,embed_links=True)
    async def servers(self, ctx, search=None):
        """
        Get all the guilds the bot is in.

        You can search a server name or get all the guild's name and guild's id.
        """

        if not search:
            paginator = commands.Paginator(prefix=None, suffix=None, max_size=500)
            for guild in sorted(self.bot.guilds, key=lambda guild: len(guild.members), reverse=True):
                summary = f"GUILD: {guild.name} [{guild.id}]\nOWNER: {guild.owner} [{guild.owner_id}]\nMEMBERS: {len(guild.members)}\n"
                paginator.add_line(summary)

            menu = BaseMenu(source=show_result(paginator.pages))
            await menu.start(ctx)
        else:
            collection = {guild.name: guild.id for guild in self.bot.guilds}
            found = fuzzy.finder(search, collection, lazy=False)[:5]

            if len(found) == 1:
                guild = self.bot.get_guild(collection[found[0]])
                em = Embed(
                    description=f"ID: {guild.id}\nTotal members: {len(guild.members)}"
                )
                em.set_author(name=found[0])
                await ctx.send(embed=em)
            elif len(found) > 1:
                newline = "\n"
                await ctx.send(
                    f"{len(found)} guilds found:\n{newline.join(found)}"
                )
            else:
                await ctx.send(f"No guild was found named **{search}**")


    @developer_cmds.command(name="reload")
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def reload_a_cog(self, ctx, cog):
        """
        Reload a cog.

        Use this just in case `jsk reload <exts>` doesn't work or breaks.
        """

        ext = f"{cog.lower()}.py"

        try:
            self.bot.unload_extension(f"cogs.{ext[:-3]}")
            self.bot.load_extension(f"cogs.{ext[:-3]}")
            await ctx.send(f"Reloaded ``{ext}``")
        except Exception:
            desired_trace = traceback.format_exc()
            await ctx.send(f"```py\n{desired_trace}```")




    @developer_cmds.command(name="load")
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def load_cog(self, ctx, cog):
        """
        Load a unloaded cog.

        Use this just in case `jsk load <exts>` doesn't work or breaks.
        """

        ext = f"{cog.lower()}.py"
        try:
            self.bot.load_extension(f"cogs.{ext[:-3]}")
            await ctx.send(f"Loaded ``{ext}``")
        except Exception:
            desired_trace = traceback.format_exc()
            await ctx.send(f"```py\n{desired_trace}```")



    @developer_cmds.command(name="unload")
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def unload_cog(self, ctx, cog):
        """
        Unload a loaded cog.

        Use this just in case `jsk unload <exts>` doesn't work or breaks.
        """

        if cog.lower() == "developer":
            return await ctx.reply(f"You cannot reload `{cog.lower()}.py`")

        ext = f"{cog.lower()}.py"
        try:
            self.bot.unload_extension(f"cogs.{ext[:-3]}")
            await ctx.send(f"Unloaded ``{ext}``")
        except Exception:
            desired_trace = traceback.format_exc()
            await ctx.send(f"```py\n{desired_trace}```")


    @developer_cmds.command(name='cleanup',brief='Cleanup my messages with no limit')
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True)
    async def dev_cleanup(self, ctx, amount : int = 25, *, flags : str = None):
        """
        Cleanup my messages with no limit and no permission checks
        Requires me to have manage_messages for bulk deletion.

        Apply the `--dm` flag to purge direct messages.
        """

        if flags is None:

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

            return

        else:
            parser = Arguments(add_help=False, allow_abbrev=False)
            parser.add_argument('--dm', action='store_true')

            try:
                args = parser.parse_args(shlex.split(flags))
            except Exception as e:
                return await ctx.send(str(e))

            if args.dm:
                await ctx.check()

                async for message in ctx.channel.history(limit=amount):
                    if message.author == ctx.bot.user:
                        await message.delete()

                return await ctx.send("Purged {} message(s) sent by me.".format(amount), delete_after=3)

            else:
                return await ctx.send("That is not a vaild flag.")

    
    @developer_cmds.command()
    @commands.bot_has_permissions(send_messages=True)
    async def info(self, ctx):
        """
        Display some developer stats/info.
        """
        check = ':white_check_mark:'
        cross = ':x:'

        if self.bot.maintenance:
            m=check
        else:
            m=cross

        if round(self.bot.latency*1000) > 200:
            l=check
        else:
            l=cross
        
        embed = Embed(
            title='Bot Stats for nerds',
            description=
            f'Maintenance: {m}\n'
            f'High Latency: {l}'
        )

        guilds = 0
        text = 0
        voice = 0
        t_m = 0

        for guild in self.bot.guilds:
            guilds += 1
            if guild.unavailable:
                continue

            t_m += guild.member_count

            for channel in guild.channels:
                if isinstance(channel, discord.TextChannel):
                    text += 1
                if isinstance(channel, discord.VoiceChannel):
                    voice += 1

                
        
        embed.add_field(name='Guilds',value=len(self.bot.guilds),inline=True)
        embed.add_field(name='Uptime',value=get_bot_uptime(self.bot,brief=True),inline=True)

        embed.add_field(name='Members',value=f'Total: {t_m}\nUnique: {len(self.bot.users)}',inline=False)
        embed.add_field(name='Channels',value=f'Total: {text+voice}\nText: {text}\nVoice: {voice}',inline=True)
        

        await ctx.send(embed=embed)


    
    @commands.command(aliases=['save'])
    @commands.bot_has_permissions(send_messages=True, read_message_history=True)
    async def archive(self, ctx, *, message : Optional[discord.Message]):
        """
        Archive a message by replying or passing in a message link / message id.
        I will pin the message content in our dms for later reference.
        """

        if not message:
            message = getattr(ctx.message.reference, "resolved", None)

        if not message:
            raise commands.BadArgument(f"You must either reply to a message, or pass in a message ID/jump url")

        # Resort message
        content = message.content or "_No content_"
        em = Embed(title="You archived a message!", url=message.jump_url, description=content, timestamp=discord.utils.utcnow())
        em.set_author(name=message.author, icon_url=message.author.avatar.url)
        try:
            msg = await ctx.author.send(embed=em)
            await msg.pin()
            await ctx.send(f"Archived the message in your DMs!\n{msg.jump_url}")
        except discord.Forbidden:
            await ctx.send("Oops! I couldn't send you a message. Are you sure your DMs are on?")


    @commands.command(name='delete',aliases=['d'])
    @commands.bot_has_permissions(send_messages=True)
    async def delete_message(self, ctx, *, message : Optional[discord.Message]):

        if not message:
            message = getattr(ctx.message.reference, "resolved", None)
        
        if message.author != ctx.me:
            return await ctx.send('I can only delete **my** messages.')

        else:

            try:
                await message.delete()
            except:
                return await ctx.send('Failed to delete that message, try again later.')


    @commands.command(slash_command=False)
    async def eval(self, ctx, *, body : str):
        """Evaluate python code."""

        if ctx.author.id != 525843819850104842:
            try:
                return await ctx.interaction.response.send_message('You must own this bot to use this command.',ephemeral=True)
            except:
                return await ctx.send('You must own this bot to use this command.')

        env = {
            'bot': self.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'guild': ctx.guild,
            'message': ctx.message,
            '_': self._last_result
        }

        env.update(globals())

        body = self.cleanup_code(body)
        stdout = io.StringIO()

        to_compile = f'async def func():\n{textwrap.indent(body, "  ")}'

        try:
            exec(to_compile, env)
        except Exception as e:
            return await ctx.send(f'```py\n{e.__class__.__name__}: {e}\n```')

        func = env['func']
        try:
            with redirect_stdout(stdout):
                ret = await func()
        except Exception as e:
            value = stdout.getvalue()
            await ctx.send(f'```py\n{value}{traceback.format_exc()}\n```')
        else:
            value = stdout.getvalue()
            try:
                await ctx.message.add_reaction('\u2705')
            except:
                pass

            if ret is None:
                if value:
                    await ctx.send(f'```py\n{value}\n```')
            else:
                self._last_result = ret
                await ctx.send(f'```py\n{value}{ret}\n```')




    @commands.command(aliases=['cc'])
    @commands.is_owner()
    async def clearconsole(self, ctx):
        try:
            clearConsole()
        except Exception as e:
            return await ctx.send(str(e))

        await ctx.check()


    @commands.command()
    @commands.is_owner()
    async def sudo(self, ctx, channel : Union[discord.TextChannel, None], who : Union[discord.Member, discord.User], *, command : str):
        """Run a command as another user optionally in another channel."""

        msg = copy.copy(ctx.message)
        channel = channel or ctx.channel
        msg.channel = channel
        msg.author = who
        msg.content = ctx.prefix + command
        new_ctx = await self.bot.get_context(msg, cls=type(ctx))
        
        await self.bot.invoke(new_ctx)


    @commands.command(help="Reloads all extensions", aliases=['rall'])
    @commands.is_owner()
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def reloadall(self, ctx, *extensions: jishaku.modules.ExtensionConverter):
        self.bot.last_rall = datetime.datetime.utcnow()
        pages = WrappedPaginator(prefix='', suffix='')
        to_send = []
        err = False
        first_reload_failed_extensions = []

        extensions = extensions or [await jishaku.modules.ExtensionConverter.convert(self, ctx, '~')]

        for extension in itertools.chain(*extensions):
            method, icon = (
                (self.bot.reload_extension, "\N{CLOCKWISE RIGHTWARDS AND LEFTWARDS OPEN CIRCLE ARROWS}")
                if extension in self.bot.extensions else
                (self.bot.load_extension, "\N{INBOX TRAY}")
            )
            # noinspection PyBroadException
            try:
                method(extension)
                pages.add_line(f"{icon} `{extension}`")
            except Exception:
                first_reload_failed_extensions.append(extension)

        error_keys = {
            discord.ext.commands.ExtensionNotFound: 'Not found',
            discord.ext.commands.NoEntryPointError: 'No setup function',
            discord.ext.commands.ExtensionNotLoaded: 'Not loaded',
            discord.ext.commands.ExtensionAlreadyLoaded: 'Already loaded'
        }

        for extension in first_reload_failed_extensions:
            method, icon = (
                (self.bot.reload_extension, "\N{CLOCKWISE RIGHTWARDS AND LEFTWARDS OPEN CIRCLE ARROWS}")
                if extension in self.bot.extensions else
                (self.bot.load_extension, "\N{INBOX TRAY}")
            )
            try:
                method(extension)
                pages.add_line(f"{icon} `{extension}`")

            except tuple(error_keys.keys()) as exc:
                pages.add_line(f"{icon}❌ `{extension}` - {error_keys[type(exc)]}")

            except discord.ext.commands.ExtensionFailed as e:
                traceback_string = f"```py" \
                                   f"\n{''.join(traceback.format_exception(etype=None, value=e, tb=e.__traceback__))}" \
                                   f"\n```"
                pages.add_line(f"{icon}❌ `{extension}` - Execution error")
                to_dm = f"❌ {extension} - Execution error - Traceback:"

                if (len(to_dm) + len(traceback_string) + 5) > 2000:
                    await ctx.author.send(file=io.StringIO(traceback_string))
                else:
                    await ctx.author.send(f"{to_dm}\n{traceback_string}")

        for page in pages.pages:
            await ctx.send(page)


    @commands.command(hidden=True)
    @commands.is_owner()
    async def sql(self, ctx, *, query: str):
        """Run some SQL."""
        # the imports are here because I imagine some people would want to use
        # this cog as a base for their other cog, and since this one is kinda
        # odd and unnecessary for most people, I will make it easy to remove
        # for those people.
        
        import time

        query = self.cleanup_code(query)

        is_multistatement = query.count(';') > 1
        if is_multistatement:
            # fetch does not support multiple statements
            strategy = ctx.bot.db.execute
        else:
            strategy = ctx.bot.db.fetch

        try:
            start = time.perf_counter()
            results = await strategy(query)
            dt = (time.perf_counter() - start) * 1000.0
        except Exception:
            return await ctx.send(f'```py\n{traceback.format_exc()}\n```')

        rows = len(results)
        if is_multistatement or rows == 0:
            return await ctx.send(f'`{dt:.2f}ms: {results}`')

        headers = list(results[0].keys())
        table = TabularData()
        table.set_columns(headers)
        table.add_rows(list(r.values()) for r in results)
        render = table.render()

        fmt = f'```\n{render}\n```\n*Returned {plural(rows):row} in {dt:.2f}ms*'
        if len(fmt) > 2000:
            fp = io.BytesIO(fmt.encode('utf-8'))
            await ctx.send('Too many results...', file=discord.File(fp, 'results.txt'))
        else:
            await ctx.send(fmt)

        

        




def setup(bot):
    bot.add_cog(developer(bot))


