import datetime
from typing import Optional
import discord
from discord import app_commands
import pytz
import asyncio
from discord.ext import commands, menus

from bot import MetroBot
from utils.custom_context import MyContext
from utils.new_pages import SimplePages
from utils.useful import Embed

from thefuzz import process

async def setup(bot: MetroBot):
    await bot.add_cog(tags(bot))


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


class tags(commands.Cog, description='Manage and create tags'):
    def __init__(self, bot: MetroBot):
        self.bot = bot
        self.blacklisted_names = ['add', 'delete', 'remove', 'owner', 'info', 'list', 'create', 'raw']

    @property
    def emoji(self) -> str:
        return '\U0001f50d'

    @commands.hybrid_group(name='tag', invoke_without_command=True, case_insensitive=True, fallback='get')
    @app_commands.describe(tag='The tag you want to get.')
    async def tag(self, ctx: MyContext, *, tag: Optional[commands.clean_content]):
        """Retrieve a tag from my database by name."""

        if not tag:
            return await ctx.help()

        data = await self.bot.db.fetchval("SELECT (text, uses) FROM tags WHERE guild_id = $1 AND name = $2", ctx.guild.id, tag.lower())
        if not data:
            data = await self.bot.db.fetch("SELECT (name) FROM tags WHERE guild_id = $1", ctx.guild.id)
            choices = [x['name'] for x in data]
            x = process.extract(tag, choices, limit=3)

            names = '\n'.join(choice[0] for choice in x)
            return await ctx.send(f"Tag not found. Did you mean...\n{names}", hide=True)
        else:
            await ctx.send(data[0], reference=ctx.replied_reference, reply=False)
            await self.bot.db.execute("UPDATE tags SET uses = $1 WHERE guild_id = $2 AND text = $3", data[1]+1, ctx.guild.id, data[0])

    @tag.command(name='add', aliases=['create'])
    @app_commands.describe(name='The name of the tag you want to add.')
    @app_commands.describe(tag='The content of the tag you want to add.')
    async def tag_add(self, ctx: MyContext, name: commands.clean_content, *, tag: commands.clean_content):
        """Create/Add a new tag."""

        if name in self.blacklisted_names:
            return await ctx.send("This tag name is blacklisted. Aborting.", hide=True)

        check = await self.bot.db.fetchval("SELECT * FROM tags WHERE name = $1 AND guild_id = $2", name, ctx.guild.id)
        if check:
            return await ctx.send("This tag already exists.", hide=True)


        await self.bot.db.execute("INSERT INTO tags (name, guild_id, owner_id, text, uses, created_at) VALUES ($1, $2, $3, $4, $5, $6)",
            name, ctx.guild.id, ctx.author.id, tag[0:1950], 0, discord.utils.utcnow().astimezone(datetime.timezone.utc).replace(tzinfo=None))
        
        await ctx.send(f"Successfully created the tag {tag}")

    @tag.command(name='raw')
    @app_commands.describe(name='The name of the tag you want to get.')
    async def tag_raw(self, ctx: MyContext, *, name: commands.clean_content):
        """Get the raw output of a tag."""
        tag = await self.bot.db.fetchval("SELECT text FROM tags WHERE name = $1 AND guild_id = $2", name, ctx.guild.id)
        if not tag:
            return await ctx.send("This tag does not exist...", hide=True)

        await ctx.send(discord.utils.escape_markdown(tag), reply=False)

    @tag.command(name='edit')
    @app_commands.describe(name='The name of the tag you want to edit.')
    @app_commands.describe(tag='The new content of the tag.')
    async def tag_edit(self, ctx: MyContext, name: commands.clean_content, *, tag: commands.clean_content):
        """Edit a tag that you own."""
        check = await self.bot.db.fetchval("SELECT text FROM tags WHERE name = $1 AND guild_id = $2 AND owner_id = $3", name, ctx.guild.id, ctx.author.id)
        if not check:
            return await ctx.send("This tag does not exist or you do not own this tag.", hide=True)

        await self.bot.db.execute("UPDATE tags SET text = $1 WHERE name = $2 AND guild_id = $3 AND owner_id = $4", tag, name, ctx.guild.id, ctx.author.id)
        await ctx.send("Edited that tag.")

    @tag.command(name='info', aliases=['owner'])
    @app_commands.describe(name='The name of the tag you want to see.')
    async def tag_info(self, ctx: MyContext, *, name: commands.clean_content):
        """View information about a tag."""

        data = await self.bot.db.fetchval("SELECT (uses, created_at, owner_id) FROM tags WHERE guild_id = $1 AND name = $2", ctx.guild.id, name)
        if not data:
            return await ctx.send("Tag not found.", hide=True)

        owner = await self.bot.get_or_fetch_member(ctx.guild, data[2])
        if not owner:
            owner = await self.bot.fetch_user(data[3])
            if not owner:
                return await ctx.send("I had a problem querying the owner of this tag.", hide=True)

        embed = Embed(color=ctx.color, title=name)
        embed.set_author(name=owner, icon_url=owner.display_avatar.url)
        embed.add_field(name='Owner', value=owner.mention)
        embed.add_field(name='Uses', value=data[0])
        embed.add_field(name='Created', value=f"{discord.utils.format_dt(pytz.utc.localize(data[1]), 'R')}")
        
        await ctx.send(embed=embed)

    @tag.command(name='remove', aliases=['delete'])
    @app_commands.describe(name='The name of the tag you want to remove.')
    async def tag_remove(self, ctx: MyContext, *, name: commands.clean_content):
        """Remove a tag by it's name."""

        status = await self.bot.db.execute("DELETE FROM tags WHERE name = $3 AND owner_id = $2 AND guild_id = $1", ctx.guild.id, ctx.author.id, name)
        if status == "DELETE 0":
            return await ctx.send("Could not remove a tag with that name.", hide=True)
        await ctx.send("Removed that tag.")

    @tag.command(name='list')
    async def tag_list(self, ctx: MyContext):
        """List all the tags in the current guild."""

        data = await self.bot.db.fetch("SELECT (name, uses) FROM tags WHERE guild_id = $1 ORDER BY uses", ctx.guild.id)
        if not data:
            return await ctx.send("This server has no tags.", hide=True)

        menu = SimplePages(source=TagSource(data[::-1], per_page=15), ctx=ctx, compact=True)
        await menu.start()
