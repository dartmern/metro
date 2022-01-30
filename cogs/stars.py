import asyncio
import enum
import re
import asyncpg
import discord
import weakref
from discord.ext import commands

from typing import Optional

from bot import MetroBot
from utils.custom_context import MyContext
from utils.useful import human_join, plural

def requires_starboard():
    async def predicate(ctx):
        if ctx.guild is None:
            return False

        cog = ctx.bot.get_cog('stars')

        ctx.starboard = await cog.get_starboard(ctx.guild.id, connection=ctx.bot.db)
        if ctx.starboard.channel is None:
            raise StarError('\N{WARNING SIGN} Starboard channel not found.')

        return True
    return commands.check(predicate)

def MessageID(argument):
    try:
        return int(argument, base=10)
    except ValueError:
        raise StarError(f'"{argument}" is not a valid message ID. Use Developer Mode to get the Copy ID option.')


class StarError(commands.BadArgument):
    pass

class StarboardConfig:
    __slots__ = ('bot', 'id', 'channel_id', 'threshold', 'locked', 'max_age')

    def __init__(self, *, guild_id, bot, record=None):
        self.id = guild_id
        self.bot = bot
        
        if record:
            self.channel_id = record['channel_id']
            self.threshold = record['threshold']
            self.locked = record['locked']

            self.max_age = record['max_age']
        else:
            self.channel_id = None

    @property
    def channel(self) -> discord.TextChannel:
        guild = self.bot.get_guild(self.id)
        return guild and guild.get_channel(self.channel_id)

def setup(bot: MetroBot):
    bot.add_cog(stars(bot))

class stars(commands.Cog, description='Manage and create starboard commands. \nThis cog is 100% \of [R. Danny\'s](https://github.com/Rapptz/RoboDanny/blob/1fb95d76d1b7685e2e2ff950e11cddfc96efbfec/cogs/) starboard cog.'):
    def __init__(self, bot: MetroBot):
        self.bot = bot
        self._locks = weakref.WeakValueDictionary()
        self._message_cache = {}

        self._about_to_be_deleted = set()

        self.spoilers = re.compile(r'\|\|(.+?)\|\|')


    @property
    def emoji(self) -> str:
        return '\U00002b50'

    async def get_message(self, channel, message_id):
        try:
            return self._message_cache[message_id]
        except KeyError:
            try:
                o = discord.Object(id=message_id + 1)
                pred = lambda m: m.id == message_id
                # don't wanna use get_message due to poor rate limit (1/1s) vs (50/1s)
                msg = await channel.history(limit=1, before=o).next()

                if msg.id != message_id:
                    return None

                self._message_cache[message_id] = msg
                return msg
            except Exception:
                return None

    async def reaction_action(self, fmt, payload):
        if str(payload.emoji) != '\N{WHITE MEDIUM STAR}':
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        channel = guild.get_channel_or_thread(payload.channel_id)
        if not isinstance(channel, (discord.Thread, discord.TextChannel)):
            return

        method = getattr(self, f'{fmt}_message')

        user = payload.member or (await self.bot.get_or_fetch_member(guild, payload.user_id))
        if user is None or user.bot:
            return

        try:
            await method(channel, payload.message_id, payload.user_id, verify=True)
        except StarError:
            pass

    async def star_message(self, channel, message_id, starrer_id, *, verify=False):
        guild_id = channel.guild.id
        lock = self._locks.get(guild_id)
        if lock is None:
            self._locks[guild_id] = lock = asyncio.Lock(loop=self.bot.loop)

        async with lock:
            async with self.bot.db.acquire(timeout=300.0) as con:
                if verify:
                    config = self.bot.get_cog('config')
                    if config:
                        plonked = await config.is_plonked(guild_id, starrer_id, channel=channel, connection=con)
                        if plonked:
                            return
                        perms = await config.get_command_permissions(guild_id, connection=con)
                        if perms.is_command_blocked('star', channel.id):
                            return

                await self._star_message(channel, message_id, starrer_id, connection=con)

    def star_emoji(self, stars):
        if 5 > stars >= 0:
            return '\N{WHITE MEDIUM STAR}'
        elif 10 > stars >= 5:
            return '\N{GLOWING STAR}'
        elif 25 > stars >= 10:
            return '\N{DIZZY SYMBOL}'
        else:
            return '\N{SPARKLES}'

    def star_gradient_colour(self, stars):
        # We define as 13 stars to be 100% of the star gradient (half of the 26 emoji threshold)
        # So X / 13 will clamp to our percentage,
        # We start out with 0xfffdf7 for the beginning colour
        # Gradually evolving into 0xffc20c
        # rgb values are (255, 253, 247) -> (255, 194, 12)
        # To create the gradient, we use a linear interpolation formula
        # Which for reference is X = X_1 * p + X_2 * (1 - p)
        p = stars / 13
        if p > 1.0:
            p = 1.0

        red = 255
        green = int((194 * p) + (253 * (1 - p)))
        blue = int((12 * p) + (247 * (1 - p)))
        return (red << 16) + (green << 8) + blue

    def is_url_spoiler(self, text, url):
        spoilers = self.spoilers.findall(text)
        for spoiler in spoilers:
            if url in spoiler:
                return True
        return False

    def get_emoji_message(self, message, stars):
        emoji = self.star_emoji(stars)

        if stars > 1:
            content = f'{emoji} **{stars}** {message.channel.mention} ID: {message.id}'
        else:
            content = f'{emoji} {message.channel.mention} ID: {message.id}'


        embed = discord.Embed(description=message.content)
        if message.embeds:
            data = message.embeds[0]
            if data.type == 'image' and not self.is_url_spoiler(message.content, data.url):
                embed.set_image(url=data.url)

        if message.attachments:
            file = message.attachments[0]
            spoiler = file.is_spoiler()
            if not spoiler and file.url.lower().endswith(('png', 'jpeg', 'jpg', 'gif', 'webp')):
                embed.set_image(url=file.url)
            elif spoiler:
                embed.add_field(name='Attachment', value=f'||[{file.filename}]({file.url})||', inline=False)
            else:
                embed.add_field(name='Attachment', value=f'[{file.filename}]({file.url})', inline=False)

        ref = message.reference
        if ref and isinstance(ref.resolved, discord.Message):
            embed.add_field(name='Replying to...', value=f'[{ref.resolved.author}]({ref.resolved.jump_url})', inline=False)

        embed.add_field(name='Original', value=f'[Jump!]({message.jump_url})', inline=False)
        embed.set_author(name=message.author.display_name, icon_url=message.author.display_avatar.url)
        embed.timestamp = message.created_at
        embed.colour = self.star_gradient_colour(stars)
        return content, embed

    async def _star_message(self, channel, message_id, starrer_id, *, connection):
        """Stars a message.
        Parameters
        ------------
        channel: :class:`TextChannel`
            The channel that the starred message belongs to.
        message_id: int
            The message ID of the message being starred.
        starrer_id: int
            The ID of the person who starred this message.
        connection: asyncpg.Connection
            The connection to use.
        """

        guild_id = channel.guild.id
        starboard = await self.get_starboard(guild_id)
        starboard_channel = starboard.channel
        if starboard_channel is None:
            raise StarError('\N{WARNING SIGN} Starboard channel not found.')

        if starboard.locked:
            raise StarError('\N{NO ENTRY SIGN} Starboard is locked.')

        if channel.is_nsfw() and not starboard_channel.is_nsfw():
            raise StarError('\N{NO ENTRY SIGN} Cannot star NSFW in non-NSFW starboard channel.')

        if channel.id == starboard_channel.id:
            # special case redirection code goes here
            # ergo, when we add a reaction from starboard we want it to star
            # the original message

            query = "SELECT channel_id, message_id FROM starboard_entries WHERE bot_message_id=$1;"
            record = await connection.fetchrow(query, message_id)
            if record is None:
                raise StarError('Could not find message in the starboard.')

            ch = channel.guild.get_channel_or_thread(record['channel_id'])
            if ch is None:
                raise StarError('Could not find original channel.')

            return await self._star_message(ch, record['message_id'], starrer_id, connection=connection)

        if not starboard_channel.permissions_for(starboard_channel.guild.me).send_messages:
            raise StarError('\N{NO ENTRY SIGN} Cannot post messages in starboard channel.')

        msg = await self.get_message(channel, message_id)

        if msg is None:
            raise StarError('\N{BLACK QUESTION MARK ORNAMENT} This message could not be found.')

        empty_message = len(msg.content) == 0 and len(msg.attachments) == 0
        if empty_message or msg.type not in (discord.MessageType.default, discord.MessageType.reply):
            raise StarError('\N{NO ENTRY SIGN} This message cannot be starred.')

        oldest_allowed = discord.utils.utcnow() - starboard.max_age
        if msg.created_at < oldest_allowed:
            raise StarError('\N{NO ENTRY SIGN} This message is too old.')

        # check if this is freshly starred
        # originally this was a single query but it seems
        # WHERE ... = (SELECT ... in some_cte) is bugged
        # so I'm going to do two queries instead
        query = """WITH to_insert AS (
                       INSERT INTO starboard_entries AS entries (message_id, channel_id, guild_id, author_id)
                       VALUES ($1, $2, $3, $4)
                       ON CONFLICT (message_id) DO NOTHING
                       RETURNING entries.id
                   )
                   INSERT INTO starrers (author_id, entry_id)
                   SELECT $5, entry.id
                   FROM (
                       SELECT id FROM to_insert
                       UNION ALL
                       SELECT id FROM starboard_entries WHERE message_id=$1
                       LIMIT 1
                   ) AS entry
                   RETURNING entry_id;
                """

        try:
            record = await connection.fetchrow(query, message_id, channel.id, guild_id, msg.author.id, starrer_id)
        except asyncpg.UniqueViolationError:
            raise StarError('\N{NO ENTRY SIGN} You already starred this message.')

        entry_id = record[0]

        query = "SELECT COUNT(*) FROM starrers WHERE entry_id=$1;"
        record = await connection.fetchrow(query, entry_id)
 
        count = record[0]
        if count < starboard.threshold:
            return

        # at this point, we either edit the message or we create a message
        # with our star info
        content, embed = self.get_emoji_message(msg, count)

        # get the message ID to edit:
        query = "SELECT bot_message_id FROM starboard_entries WHERE message_id=$1;"
        record = await connection.fetchrow(query, message_id)
        bot_message_id = record[0]

        if bot_message_id is None:
            new_msg = await starboard_channel.send(content, embed=embed)
            query = "UPDATE starboard_entries SET bot_message_id=$1 WHERE message_id=$2;"
            await connection.execute(query, new_msg.id, message_id)
        else:
            new_msg = await self.get_message(starboard_channel, bot_message_id)
            if new_msg is None:
                # deleted? might as well purge the data
                query = "DELETE FROM starboard_entries WHERE message_id=$1;"
                await connection.execute(query, message_id)
            else:
                await new_msg.edit(content=content, embed=embed)

    async def unstar_message(self, channel, message_id, starrer_id, *, verify=False):
        guild_id = channel.guild.id
        lock = self._locks.get(guild_id)
        if lock is None:
            self._locks[guild_id] = lock = asyncio.Lock(loop=self.bot.loop)

        async with lock:
            async with self.bot.db.acquire(timeout=300.0) as con:
                if verify:
                    config = self.bot.get_cog('config')
                    if config:
                        plonked = await config.is_plonked(guild_id, starrer_id, channel=channel, connection=con)
                        if plonked:
                            return
                        perms = await config.get_command_permissions(guild_id, connection=con)
                        if perms.is_command_blocked('star', channel.id):
                            return

                await self._unstar_message(channel, message_id, starrer_id, connection=con)

    async def _unstar_message(self, channel, message_id, starrer_id, *, connection):
        """Unstars a message.
        Parameters
        ------------
        channel: :class:`TextChannel`
            The channel that the starred message belongs to.
        message_id: int
            The message ID of the message being unstarred.
        starrer_id: int
            The ID of the person who unstarred this message.
        connection: asyncpg.Connection
            The connection to use.
        """

        guild_id = channel.guild.id
        starboard = await self.get_starboard(guild_id)
        starboard_channel = starboard.channel
        if starboard_channel is None:
            raise StarError('\N{WARNING SIGN} Starboard channel not found.')

        if starboard.locked:
            raise StarError('\N{NO ENTRY SIGN} Starboard is locked.')

        if channel.id == starboard_channel.id:
            query = "SELECT channel_id, message_id FROM starboard_entries WHERE bot_message_id=$1;"
            record = await connection.fetchrow(query, message_id)
            if record is None:
                raise StarError('Could not find message in the starboard.')

            ch = channel.guild.get_channel_or_thread(record['channel_id'])
            if ch is None:
                raise StarError('Could not find original channel.')

            return await self._unstar_message(ch, record['message_id'], starrer_id, connection=connection)

        if not starboard_channel.permissions_for(starboard_channel.guild.me).send_messages:
            raise StarError('\N{NO ENTRY SIGN} Cannot edit messages in starboard channel.')

        query = """DELETE FROM starrers USING starboard_entries entry
                   WHERE entry.message_id=$1
                   AND   entry.id=starrers.entry_id
                   AND   starrers.author_id=$2
                   RETURNING starrers.entry_id, entry.bot_message_id
                """

        record = await connection.fetchrow(query, message_id, starrer_id)
        if record is None:
            raise StarError('\N{NO ENTRY SIGN} You have not starred this message.')

        entry_id = record[0]
        bot_message_id = record[1]

        query = "SELECT COUNT(*) FROM starrers WHERE entry_id=$1;"
        count = await connection.fetchrow(query, entry_id)
        count = count[0]

        if count == 0:
            # delete the entry if we have no more stars
            query = "DELETE FROM starboard_entries WHERE id=$1;"
            await connection.execute(query, entry_id)

        if bot_message_id is None:
            return

        bot_message = await self.get_message(starboard_channel, bot_message_id)
        if bot_message is None:
            return

        if count < starboard.threshold:
            self._about_to_be_deleted.add(bot_message_id)
            if count:
                # update the bot_message_id to be NULL in the table since we're deleting it
                query = "UPDATE starboard_entries SET bot_message_id=NULL WHERE id=$1;"
                await connection.execute(query, entry_id)

            await bot_message.delete()
        else:
            msg = await self.get_message(channel, message_id)
            if msg is None:
                raise StarError('\N{BLACK QUESTION MARK ORNAMENT} This message could not be found.')

            content, embed = self.get_emoji_message(msg, count)
            await bot_message.edit(content=content, embed=embed)

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        await self.reaction_action('star', payload)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        await self.reaction_action('unstar', payload)

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload):
        if payload.message_id in self._about_to_be_deleted:
            # we triggered this deletion ourselves and
            # we don't need to drop it from the database
            self._about_to_be_deleted.discard(payload.message_id)
            return

        starboard = await self.get_starboard(payload.guild_id)
        if starboard.channel is None or starboard.channel.id != payload.channel_id:
            return

        # at this point a message got deleted in the starboard
        # so just delete it from the database
        async with self.bot.pool.acquire(timeout=300.0) as con:
            query = "DELETE FROM starboard_entries WHERE bot_message_id=$1;"
            await con.execute(query, payload.message_id)

    @commands.Cog.listener()
    async def on_raw_bulk_message_delete(self, payload):
        if payload.message_ids <= self._about_to_be_deleted:
            # see comment above
            self._about_to_be_deleted.difference_update(payload.message_ids)
            return

        starboard = await self.get_starboard(payload.guild_id)
        if starboard.channel is None or starboard.channel.id != payload.channel_id:
            return

        async with self.bot.pool.acquire(timeout=300.0) as con:
            query = "DELETE FROM starboard_entries WHERE bot_message_id=ANY($1::bigint[]);"
            await con.execute(query, list(payload.message_ids))

    @commands.Cog.listener()
    async def on_raw_reaction_clear(self, payload):
        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        channel = guild.get_channel_or_thread(payload.channel_id)
        if channel is None or not isinstance(channel, (discord.Thread, discord.TextChannel)):
            return

        async with self.bot.db.acquire(timeout=300.0) as con:
            starboard = await self.get_starboard(channel.guild.id, connection=con)
            if starboard.channel is None:
                return

            query = "DELETE FROM starboard_entries WHERE message_id=$1 RETURNING bot_message_id;"
            bot_message_id = await con.fetchrow(query, payload.message_id)

            if bot_message_id is None:
                return


            bot_message_id = bot_message_id[0]
            msg = await self.get_message(starboard.channel, bot_message_id)
            if msg is not None:
                await msg.delete()

    async def get_starboard(self, guild_id: int, *, connection: asyncpg.Pool=None):
        connection = connection or self.bot.db
        query = "SELECT * FROM starboard WHERE id=$1;"
        record = await connection.fetchrow(query, guild_id)
        return StarboardConfig(guild_id=guild_id, bot=self.bot, record=record)

    @commands.group(case_insensitive=True, invoke_without_command=True)
    @commands.has_guild_permissions(manage_guild=True)
    @commands.bot_has_guild_permissions(manage_channels=True)
    async def starboard(self, ctx: MyContext, *, name:str = "starboard"):
        """
        Setup the starboard for this server.
        
        This will create a new channel with the specified name
        and make it into the server's "starboard". If no name is passed
        then it will default to the name "starboard".
        
        You can edit details about the starboard channel after running
        this command and after I create the channel.

        The starboard takes full insparation from [R Danny's starboard](https://github.com/Rapptz/RoboDanny/blob/1fb95d76d1b7685e2e2ff950e11cddfc96efbfec/cogs/stars.py)
        """
        
        starboard = await self.get_starboard(ctx.guild.id, connection=self.bot.db)
        if starboard.channel is not None:
            raise commands.BadArgument(f"This server already has a starboard ({starboard.channel.mention}).")

        if hasattr(starboard, 'locked'):
            confirm = await ctx.confirm("Apparently, a previously configured starboard channel was deleted. Is this true?")
            if confirm is None:
                raise commands.BadArgument("Timed out.")
            if confirm is False:
                return await ctx.send("Aborting starboard creation. Join bot support server for more info.")
            await self.bot.db.execute("DELETE FROM starboard WHERE id=$1", ctx.guild.id)

        perms = ctx.channel.permissions_for(ctx.me)

        if not perms.manage_roles or not perms.manage_channels:
            return await ctx.send('\N{NO ENTRY SIGN} I do not have proper permissions (Manage Roles and Manage Channel)')

        overwrites = {
            ctx.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True,
                                                embed_links=True, read_message_history=True),
            ctx.guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False,
                                                                read_message_history=True)
        }

        reason = f'{ctx.author} (ID: {ctx.author.id}) has created the starboard channel.'

        try:
            channel = await ctx.guild.create_text_channel(name=name, overwrites=overwrites, reason=reason)
        except discord.Forbidden:
            return await ctx.send('\N{NO ENTRY SIGN} I do not have permissions to create a channel.')
        except discord.HTTPException:
            return await ctx.send('\N{NO ENTRY SIGN} This channel name is bad or an unknown error happened.')

        query = "INSERT INTO starboard (id, channel_id) VALUES ($1, $2);"
        try:
            await self.bot.db.execute(query, ctx.guild.id, channel.id)
        except:
            await channel.delete(reason='Failure to commit to create the starboard.')
            await ctx.send('Could not create the channel due to an internal error. Join the bot support server for help.')
        else:
            await ctx.send(f'\N{GLOWING STAR} Starboard created at {channel.mention}.')

    @commands.group(invoke_without_command=True)
    @commands.guild_only()
    async def star(self, ctx, message: MessageID):
        """
        Stars a message via message ID.
        
        To star a message you should right click on the on a message and then
        click "Copy ID". You must have Developer Mode enabled to get that
        functionality.
        It is recommended that you react to a message with \N{WHITE MEDIUM STAR} instead.
        You can only star a message once.

        The starboard takes full insparation from [R Danny's starboard](https://github.com/Rapptz/RoboDanny/blob/1fb95d76d1b7685e2e2ff950e11cddfc96efbfec/cogs/stars.py)
        """
        if not message:
            return await ctx.help()

        try:
            await self.star_message(ctx.channel, message, ctx.author.id)
        except StarError as e:
            await ctx.send(e)
        else:
            await ctx.message.delete()

    @commands.command()
    @commands.guild_only()
    async def unstar(self, ctx, message: MessageID):
        """Unstars a message via message ID.
        To unstar a message you should right click on the on a message and then
        click "Copy ID". You must have Developer Mode enabled to get that
        functionality.
        """
        try:
            await self.unstar_message(ctx.channel, message, ctx.author.id, verify=True)
        except StarError as e:
            return await ctx.send(e)
        else:
            await ctx.message.delete()

    @star.command(name='lock')
    @commands.has_guild_permissions(manage_guild=True)
    @requires_starboard()
    async def star_lock(self, ctx):
        """Locks the starboard from being processed.
        This is a moderation tool that allows you to temporarily
        disable the starboard to aid in dealing with star spam.
        When the starboard is locked, no new entries are added to
        the starboard as the bot will no longer listen to reactions or
        star/unstar commands.
        To unlock the starboard, use the unlock subcommand.
        To use this command you need Manage Server permission.
        """

        query = "UPDATE starboard SET locked=TRUE WHERE id=$1;"
        await ctx.bot.db.execute(query, ctx.guild.id)

        await ctx.send('Starboard is now locked.')

    @star.command(name='unlock')
    @commands.has_guild_permissions(manage_guild=True)
    @requires_starboard()
    async def star_unlock(self, ctx):
        """Unlocks the starboard for re-processing.
        To use this command you need Manage Server permission.
        """

        query = "UPDATE starboard SET locked=FALSE WHERE id=$1;"
        await ctx.bot.db.execute(query, ctx.guild.id)

        await ctx.send('Starboard is now unlocked.')

    @star.command(name='limit', aliases=['threshold'])
    @commands.has_guild_permissions(manage_guild=True)
    @requires_starboard()
    async def star_limit(self, ctx, stars: int):
        """Sets the minimum number of stars required to show up.
        When this limit is set, messages must have this number
        or more to show up in the starboard channel.
        You cannot have a negative number and the maximum
        star limit you can set is 100.
        Note that messages that previously did not meet the
        limit but now do will still not show up in the starboard
        until starred again.
        You must have Manage Server permissions to use this.
        """

        stars = min(max(stars, 1), 100)
        query = "UPDATE starboard SET threshold=$2 WHERE id=$1;"
        await self.bot.db.execute(query, ctx.guild.id, stars)

        await ctx.send(f'Messages now require {plural(stars):star} to show up in the starboard.')

    @star.command(name='age')
    @commands.has_guild_permissions(manage_guild=True)
    @requires_starboard()
    async def star_age(self, ctx, number: int, units='days'):
        """Sets the maximum age of a message valid for starring.
        By default, the maximum age is 7 days. Any message older
        than this specified age is invalid of being starred.
        To set the limit you must specify a number followed by
        a unit. The valid units are "days", "weeks", "months",
        or "years". They do not have to be pluralized. The
        default unit is "days".
        The number cannot be negative, and it must be a maximum
        of 35. If the unit is years then the cap is 10 years.
        You cannot mix and match units.
        You must have Manage Server permissions to use this.
        """

        valid_units = ('days', 'weeks', 'months', 'years')

        if units[-1] != 's':
            units = units + 's'

        if units not in valid_units:
            return await ctx.send(f'Not a valid unit! I expect only {human_join(valid_units)}.')

        number = min(max(number, 1), 35)

        if units == 'years' and number > 10:
            return await ctx.send('The maximum is 10 years!')

        # the input is sanitised so this should be ok
        # only doing this because asyncpg requires a timedelta object but
        # generating that with these clamp units is overkill
        query = f"UPDATE starboard SET max_age='{number} {units}'::interval WHERE id=$1;"
        await ctx.bot.db.execute(query, ctx.guild.id)

        if number == 1:
            age = f'1 {units[:-1]}'
        else:
            age = f'{number} {units}'

        await ctx.send(f'Messages must now be less than {age} old to be starred.')