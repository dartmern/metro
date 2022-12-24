import datetime
from typing import Annotated, Optional, TypedDict, Union
import asyncpg
import discord
from discord import Interaction, app_commands
import pytz
import asyncio
from discord.ext import commands, menus

from bot import MetroBot
from utils.custom_context import MyContext
from utils.pages import SimplePages
from utils.useful import Embed

from thefuzz import process

# this is a more lightweight modification of R. Danny's tags.py cog
# https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/tags.py

class TagObject(TypedDict):
    name: str
    content: str
    original: Optional[str]

class TagName(commands.clean_content):
    def __init__(self, *, lower: bool = False):
        self.lower: bool = lower
        super().__init__()

    async def convert(self, ctx: MyContext, argument: str) -> str:
        converted = await super().convert(ctx, argument)
        lower = converted.lower().strip()

        if not lower:
            raise commands.BadArgument('Missing tag name.')

        if len(lower) > 100:
            raise commands.BadArgument('Tag name is a maximum of 100 characters.')

        first_word, _, _ = lower.partition(' ')

        root: commands.GroupMixin = ctx.bot.get_command('tag')
        if first_word in root.all_commands:
            raise commands.BadArgument('This tag name starts with a reserved word.')

        return converted.strip() if not self.lower else lower

class TagSource(menus.ListPageSource):
    async def format_page(self, menu, entries):
        pages = []
        for index, entry in enumerate(entries, start=menu.current_page * self.per_page):
            pages.append(f"{index + 1}. {entry['row'][0]} ({entry['row'][1]} uses.)")

        maximum = self.get_max_pages()
        if maximum > 1:
            footer = f'Page {menu.current_page + 1}/{maximum} ({len(self.entries)} entries)'
            menu.embed.set_footer(text=footer)

        menu.embed.description = '\n'.join(pages)
        return menu.embed


class TagMakeModal(discord.ui.Modal, title='Create a new tag.'):

    name = discord.ui.TextInput(label='Name', max_length=100, min_length=1)
    content = discord.ui.TextInput(label='Content', style=discord.TextStyle.long, max_length=2000, min_length=1)

    def __init__(self, *, cog, ctx: MyContext) -> None:
        super().__init__()
        self.cog: tags = cog
        self.ctx = MyContext

    async def on_submit(self, interaction: discord.Interaction) -> None:
        assert interaction.guild_id is not None
        name = str(self.name)
        if self.cog.being_made(interaction.guild_id, name):
            await interaction.response.send_message('This tag is currently being made by someone else.', ephemeral=True)
            return 

        self.ctx.interaction = interaction # set it so create_tag can respond to it via ctx.send
        
        content = str(self.content)
        if len(content) > 2000:
            await interaction.response.send_message('Tag content must be under 2000 characters.', ephemeral=True)
        else:
            await self.cog.create_tag(interaction, name, content)

class TagEditModal(discord.ui.Modal, title='Edit tag.'):

    content = discord.ui.TextInput(
        label='New Tag Content', style=discord.TextStyle.paragraph, min_length=1, max_length=2000
    )

    def __init__(self, old_content: str) -> None:
        super().__init__()
        self.content.default = old_content

    async def on_submit(self, interaction: discord.Interaction) -> None:

        self.interaction = interaction
        self.text = self.content.value
        self.stop()

class tags(commands.Cog, description='Manage and create tags'):
    def __init__(self, bot: MetroBot):
        self.bot = bot
        self.blacklisted_names = ['add', 'delete', 'remove', 'owner', 'info', 'list', 'create', 'raw']

        # {guild: {'tags', 'being', 'made'}}
        self.is_being_made: dict[int, set[str]] = {}

    @property
    def emoji(self) -> str:
        return '\U0001f50d'

    def being_made(self, guild_id: int, name: str):
        """Check if a tag is being made."""
        try:
            being_made = self.is_being_made[guild_id]
        except KeyError:
            return False
        else:
            return name.lower() in being_made

    def add_in_progress_tag(self, guild_id: int, name: str) -> None:
        """Add to being made dict."""
        tags = self.is_being_made.setdefault(guild_id, set())
        tags.add(name.lower())

    def remove_from_being_made(self, guild_id: int, name: str):
        """Remove from the being made dict."""
        try:
            being_made = self.is_being_made[guild_id]
        except KeyError:
            return

        being_made.discard(name.lower())
        if len(being_made) == 0:
            del self.is_being_made[guild_id]

    async def get_tag(
        self,
        guild_id: int,
        name: str,
        *,
        db: Optional[asyncpg.Pool] = None 
    ) -> TagObject:
        db = db or self.bot.db

        def disambiguate(rows, query):
            if rows is None or len(rows) == 0:
                raise RuntimeError('Tag not found.')

            names = '\n'.join(r[0] for r in rows)
            raise RuntimeError(f'Tag not found. Did you mean...\n{names}')

        query = """
                SELECT name, content, original
                FROM tag_lookup
                WHERE guild_id = $1
                AND name = $2
                """
        row = await db.fetchrow(query, guild_id, name)
        if row is None:
            data = await self.bot.db.fetch("SELECT (name) FROM tag_lookup WHERE guild_id = $1", guild_id)
            choices = [x['name'] for x in data]
            x = process.extract(name, choices, limit=3)
            
            return disambiguate(x, name)
        else:
            return row

    async def create_tag(
        self,
        ctx: Union[MyContext, Interaction],
        name: str,
        content: str
    ) -> None:
        """Create a tag."""
        author = ctx.author if getattr(ctx, 'author', None) else ctx.user
        if isinstance(ctx, Interaction):
            send = ctx.response.send_message
        else:
            send = ctx.send
        
        query = """
                INSERT INTO tag_lookup (name, content, guild_id, owner_id, is_alias, original, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """
    
        try:
            await self.bot.db.execute(query, name, content, ctx.guild.id, author.id, False, None, discord.utils.utcnow().replace(tzinfo=None))
        except asyncpg.UniqueViolationError:
            return await send('This tag already exists.', ephemeral=True)
        except Exception as e:
            print(e)
            return await send(f'Could not create tag: {e}', ephemeral=True)
        
        await self.bot.db.execute(
            'INSERT INTO tags (name, owner_id, guild_id, created_at, uses) '
            'VALUES ($1, $2, $3, $4, $5)',
            name, author.id, ctx.guild.id, discord.utils.utcnow().replace(tzinfo=None), 0 # no uses
            )
        await send(f'Tag {name} successfully created.')

    async def aliased_tag_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        query = """SELECT name FROM tag_lookup WHERE guild_id=$1 AND LOWER(name) = $2 LIMIT 12;"""
        results: list[tuple[str]] = await self.bot.db.fetch(query, interaction.guild_id, current.lower())
        return [app_commands.Choice(name=a, value=a) for a, in results]

    async def non_aliased_tag_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        query = """SELECT name FROM tags WHERE guild_id=$1 AND LOWER(name) = $2 LIMIT 12;"""
        results: list[tuple[str]] = await self.bot.db.fetch(query, interaction.guild_id, current.lower())
        return [app_commands.Choice(name=a, value=a) for a, in results]

    async def owned_aliased_tag_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        query = """SELECT name
                   FROM tag_lookup
                   WHERE guild_id=$1 AND owner_id=$2 AND name = $3
                   ORDER BY similarity(name, $3) DESC
                   LIMIT 12;
                """
        results: list[tuple[str]] = await self.bot.db.fetch(
            query, interaction.guild_id, interaction.user.id, current.lower()
        )
        return [app_commands.Choice(name=a, value=a) for a, in results]

    @commands.hybrid_group(name='tag', invoke_without_command=True, case_insensitive=True, fallback='get')
    @app_commands.describe(tag='The tag you want to get.')
    @app_commands.autocomplete(tag=aliased_tag_autocomplete)
    async def _tag(self, ctx: MyContext, *, tag: Annotated[str, TagName]):
        """Retrieve an existing tag's content."""

        tag = tag.lower()
        
        try:
            tag = await self.get_tag(ctx.guild.id, tag)
        except RuntimeError as e:
            return await ctx.send(e)

        await ctx.send(tag['content'])

        # add the usage after invoking it
        original = tag['original'] if tag['original'] else tag['name']
        await self.bot.db.execute('UPDATE tags SET uses = uses + 1 WHERE name = $1 AND guild_id = $2', original, ctx.guild.id)

    @_tag.command(name='create', aliases=['add'])
    @app_commands.describe(tag='The name of the tag you want to create.')
    @app_commands.describe(content='The content of the tag you want to create.')
    async def _tag_create(
        self, ctx: MyContext,
        tag: Annotated[str, TagName], *, 
        content: Annotated[str, commands.clean_content]):
        """Create a new tag."""

        if self.being_made(ctx.guild.id, tag):
            return await ctx.send('This tag is currently being made by someone else.', hide=True)

        if len(content) > 2000:
            return await ctx.send('Tag content must be under 2000 characters.', hide=True)

        await self.create_tag(ctx, tag, content)

    @_tag.command(name='make', ignore_extra=False)
    async def _tag_make(
        self, ctx: MyContext):
        """Interactive makes a tag for you."""

        if ctx.interaction:
            modal = TagMakeModal(cog=self, ctx=ctx)
            await ctx.interaction.response.send_modal(modal)
            return

        await ctx.send('What would you like the tag\'s name to be?')

        try:
            message: discord.Message = await self.bot.wait_for('message', timeout=30, check= lambda m: m.author == ctx.author and m.channel == ctx.channel)
        except asyncio.TimeoutError:
            return await ctx.send('You took too long. Redo the command to try again.')

        try:
            name = await TagName().convert(ctx, message.content)
        except commands.BadArgument as e:
            return await ctx.send(f'{e}. Redo the command to try again.')

        if self.being_made(ctx.guild.id, name):
            return await ctx.send('This tag is currently being made by someone else.', hide=True)

        query = """SELECT 1 FROM tags WHERE guild_id = $1 AND LOWER(name) = $2"""
        data = await self.bot.db.fetchrow(query, ctx.guild.id, name)
        if data:
            return await ctx.send(
                'A tag named that already exists. Redo the command to try again.'
            )
    
        self.add_in_progress_tag(ctx.guild.id, name)

        await ctx.send(
            f'Nice. The name will be {name}. What will the tag\'s content be? '
            f'\n**You can type {ctx.prefix}abort to abort this process.**')

        try:
            message = await self.bot.wait_for('message', timeout=300, check= lambda m: m.author == ctx.author and m.channel == ctx.channel)
        except asyncio.TimeoutError:
            return await ctx.send('You took too long. Redo the command to try again.')

        if message.content == ctx.prefix + 'abort':
            self.remove_from_being_made(ctx.guild.id, name)
            return await ctx.send('Aborting tag make process.')
        elif message.content:
            clean_content = await commands.clean_content().convert(ctx, message.content)
        else:
            clean_content = message.content 

        if message.attachments:
            clean_content = clean_content + '\n' + message.attachments[0].url

        if len(clean_content) > 2000:
            return await ctx.send('Tag content must be under 2000 characters.')

        try:
            await self.create_tag(ctx, name, clean_content)
        finally:
            self.remove_from_being_made(ctx.guild.id, name)

    @_tag_make.error
    async def _tag_make_error(self, ctx: MyContext, error: commands.CommandError):
        if isinstance(error, commands.TooManyArguments):
            await ctx.send(f'Please call only {ctx.prefix}{ctx.command}')

    @_tag.command(name='alias')
    @app_commands.describe(new_name='The aliased name for the tag.')
    @app_commands.describe(old_name='The original tag you want to apply the alias on.')
    @app_commands.autocomplete(old_name=non_aliased_tag_autocomplete)
    async def _tag_alias(
        self, ctx: MyContext, 
        new_name: Annotated[str, TagName], *,
        old_name: Annotated[str, TagName]):
        """Create an alias for an existing tag."""

        try:
            content = await self.get_tag(ctx.guild.id, old_name)
        except RuntimeError:
            return await ctx.send(f'A tag with the name of "{old_name}" does not exist.')
        
        query = """
                INSERT INTO tag_lookup (name, content, guild_id, owner_id, is_alias, original, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                """
        old = content['original'] if content['original'] else old_name
        try:
            await self.bot.db.execute(query, new_name, content['content'], ctx.guild.id, ctx.author.id, True, old, discord.utils.utcnow().replace(tzinfo=None))
        except Exception as e:
            return await ctx.send(f'Error adding alias: {e}')

        await ctx.send(f'Tag alias "{new_name}" that points to "{old_name}" successfully created.')
        
    @_tag.command(name='list')
    @app_commands.describe(member='The member\'s tags you want to list. Leave blank to see your tags.')
    async def _tag_list(
        self, ctx: MyContext, *, member: discord.User = commands.Author):
        """List all the tags that you own or someone else."""

        query = """
                SELECT name, id
                FROM tag_lookup
                WHERE guild_id = $1
                AND owner_id = $2
                ORDER BY name
                """
        
        data = await self.bot.db.fetch(query, ctx.guild.id, member.id)

        if data:
            to_paginate = []
            for i, entry in enumerate(data):
                to_paginate.append(f"{i + 1}. {entry['name']} (ID: {entry['id']})")
            await ctx.paginate(to_paginate, per_page=12)
        else:
            await ctx.send(f'{member} has no tags.', hide=True)

    async def _send_alias_info(self, ctx: MyContext, row: asyncpg.Record) -> None:

        embed = discord.Embed(color=ctx.color)
        embed.title = row['name']
        embed.timestamp = pytz.utc.localize(row['created_at'])
        embed.set_footer(text='Alias created at')

        user = self.bot.get_user(row['owner_id']) or (await self.bot.fetch_user(row['owner_id']))
        embed.set_author(name=str(user), icon_url=user.display_avatar.url)
        embed.add_field(name='Owner', value=f'<@{row["owner_id"]}>')
        embed.add_field(name='Original', value=row['original'])

        await ctx.send(embed=embed)

    async def _send_tag_info(self, ctx: MyContext, row: asyncpg.Record) -> None:
        print(row)
        embed = discord.Embed(color=ctx.color)
        embed.title = row['name']
        embed.timestamp = pytz.utc.localize(row['created_at'])
        embed.set_footer(text='Tag created at')

        user = self.bot.get_user(row['owner_id']) or (await self.bot.fetch_user(row['owner_id']))
        embed.set_author(name=str(user), icon_url=user.display_avatar.url)
        embed.add_field(name='Owner', value=f'<@{row["owner_id"]}>')

        uses = await self.bot.db.fetchval('SELECT uses FROM tags WHERE guild_id = $1 AND name = $2', ctx.guild.id, row['name'])
        embed.add_field(name='Uses', value=str(uses))

        await ctx.send(embed=embed)

    @_tag.command(name='info', aliases=['owner'])
    @app_commands.describe(name='The tag you want to view information on.')
    @app_commands.autocomplete(name=aliased_tag_autocomplete)
    async def _tag_info(self, ctx: MyContext, *, name: Annotated[str, TagName(lower=True)]):
        """Get information about a tag."""

        query = """
                SELECT name, owner_id, is_alias, original, created_at
                FROM tag_lookup
                WHERE guild_id = $1
                AND name = $2
                """
        row = await self.bot.db.fetchrow(query, ctx.guild.id, name)
        if row is None:
            return await ctx.send('Tag not found.')
        
        if row['is_alias']:
            await self._send_alias_info(ctx, row)
        else:
            await self._send_tag_info(ctx, row)

    @_tag.command(name='raw')
    @app_commands.describe(name='The tag you want to get.')
    @app_commands.autocomplete(name=non_aliased_tag_autocomplete)
    async def _tag_raw(self, ctx: MyContext, *, name: Annotated[str, TagName(lower=True)]):
        """Get the raw contents of a tag.
        
        This is useful for editing the tag.
        """
            
        try:
            tag = await self.get_tag(ctx.guild.id, name)
        except RuntimeError as e:
            return await ctx.send(str(e))

        content = discord.utils.escape_markdown(tag['content'])
        await ctx.send(content.replace("<", "\\<"))

    @_tag.command(name='edit', usage='<name> <content>')
    @app_commands.describe(name='The tag you want to edit.')
    @app_commands.describe(content='The new content of the tag.')
    @app_commands.autocomplete(name=owned_aliased_tag_autocomplete)
    async def _tag_edit(
        self, ctx: MyContext, 
        name: Annotated[str, commands.clean_content], *, 
        content: Annotated[Optional[str], TagName] = None):
        """Edit a tag's content."""

        query = "SELECT (name, content) FROM tag_lookup WHERE LOWER(name) = $1 AND guild_id = $2 AND owner_id = $3 AND is_alias = False"
        row = await self.bot.db.fetchrow(query, name, ctx.guild.id, ctx.author.id)
        if not row:
            raise commands.BadArgument('Could not find tag. Are you sure it exists and you own it?')

        if content is None:
            if not ctx.interaction:
                await ctx.help()
                return

            else:
                modal = TagEditModal(row[0])
                await ctx.interaction.response.send_modal(modal)
                await modal.wait()
                ctx.interaction = modal.interaction
                content = modal.text
        
        query = "UPDATE tag_lookup SET content = $1 WHERE LOWER(name) = $2 AND guild_id = $3 AND owner_id = $4 AND is_alias = False"
        await self.bot.db.execute(query, content, name, ctx.guild.id, ctx.author.id)

        edit_aliases = "UPDATE tag_lookup SET content = $1 WHERE LOWER(original) = $2 AND guild_id = $3"
        await self.bot.db.execute(edit_aliases, content, name, ctx.guild.id)
        
        await ctx.send('Successfully edited tag.', hide=True)

    @_tag.command(name='remove', aliases=['delete'])
    @app_commands.describe(name='The tag you want to remove.')
    @app_commands.autocomplete(name=owned_aliased_tag_autocomplete)
    async def _tag_remove(self, ctx: MyContext, *, name: Annotated[str, TagName(lower=True)]):
        """Delete a tag you own."""

        # this process is really inefficent but whatever

        bypass_owner_check = ctx.author.id == self.bot.owner_id or ctx.author.guild_permissions.manage_messages
        where = 'LOWER(name) = $1 AND guild_id = $2'

        if bypass_owner_check:
            args = [name, ctx.guild.id]
        else:
            args = [name, ctx.guild.id, ctx.author.id]
            where = f'{where} AND owner_id = $3'
        
        query = f"SELECT (is_alias, original) FROM tag_lookup WHERE {where}"
        row = await self.bot.db.fetchval(query, *args)
        if not row:
            return await ctx.send('Tag not found.', hide=True)

        if row[0]:
            await self.bot.db.execute(f'DELETE FROM tag_lookup WHERE {where}', *args)
            await ctx.send('Tag alias successfully deleted.')
        else:
            await self.bot.db.execute(f'DELETE FROM tag_lookup WHERE guild_id = $1 AND original = $2', ctx.guild.id, name)
            await self.bot.db.execute(f'DELETE FROM tag_lookup WHERE guild_id = $1 AND name = $2', ctx.guild.id, name)
            await ctx.send('Tag and aliases pointing to tag successfully deleted.')

        await self.bot.db.execute(f'DELETE FROM tags WHERE {where}', *args)

