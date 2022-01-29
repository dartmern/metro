import datetime
from typing import Optional
import discord
import pytz
import asyncio
from discord.ext import commands, menus

from bot import MetroBot
from utils.custom_context import MyContext
from utils.new_pages import SimplePages
from utils.useful import Embed

def setup(bot: MetroBot):
    bot.add_cog(tags(bot))


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

    @commands.group(name='tag', invoke_without_command=True, case_insensitive=True)
    async def tag(self, ctx: MyContext, *, tag: Optional[commands.clean_content]):
        """Retrieve a tag from my database by name."""

        if not tag:
            return await ctx.help()

        data = await self.bot.db.fetchval("SELECT (text, uses) FROM tags WHERE guild_id = $1 AND name = $2", ctx.guild.id, tag.lower())
        if not data:
            raise commands.BadArgument("Tag not found.")
        else:
            await ctx.send(data[0], reference=ctx.replied_reference, reply=False)
            await self.bot.db.execute("UPDATE tags SET uses = $1 WHERE guild_id = $2 AND text = $3", data[1]+1, ctx.guild.id, data[0])

    @tag.command(name='add', aliases=['create'])
    async def tag_add(self, ctx: MyContext, name: commands.clean_content, *, tag: commands.clean_content):
        """Create/Add a new tag."""

        if name in self.blacklisted_names:
            raise commands.BadArgument("This tag name is blacklisted. Aborting.")

        check = await self.bot.db.fetchval("SELECT * FROM tags WHERE name = $1 AND guild_id = $2", name, ctx.guild.id)
        if check:
            raise commands.BadArgument("This tag already exists.")


        await self.bot.db.execute("INSERT INTO tags (name, guild_id, owner_id, text, uses, created_at) VALUES ($1, $2, $3, $4, $5, $6)",
            name, ctx.guild.id, ctx.author.id, tag[0:1950], 0, discord.utils.utcnow().astimezone(datetime.timezone.utc).replace(tzinfo=None))
        
        await ctx.send("Created the tag \"{}\": \n> {}".format(name, tag[0:1950]))

    @tag.command(name='raw')
    async def tag_raw(self, ctx: MyContext, name: commands.clean_content):
        """Get the raw output of a tag."""
        tag = await self.bot.db.fetchval("SELECT text FROM tags WHERE name = $1 AND guild_id = $2", name, ctx.guild.id)
        if not tag:
            raise commands.BadArgument("This tag does not exist...")

        await ctx.send(discord.utils.escape_markdown(tag), reply=False)

    @tag.command(name='edit')
    async def tag_edit(self, ctx: MyContext, name: commands.clean_content, *, tag: commands.clean_content):
        """Edit a tag that you own."""
        check = await self.bot.db.fetchval("SELECT text FROM tags WHERE name = $1 AND guild_id = $2 AND owner_id = $3", name, ctx.guild.id, ctx.author.id)
        if not check:
            raise commands.BadArgument("This tag does not exist or you do not own this tag.")

        await self.bot.db.execute("UPDATE tags SET text = $1 WHERE name = $2 AND guild_id = $3 AND owner_id = $4", tag, name, ctx.guild.id, ctx.author.id)
        await ctx.send("Edited that tag.")

    @tag.command(name='info', aliases=['owner'])
    async def tag_info(self, ctx: MyContext, *, name: commands.clean_content):
        """View information about a tag."""

        data = await self.bot.db.fetchval("SELECT (uses, created_at, owner_id) FROM tags WHERE guild_id = $1 AND name = $2", ctx.guild.id, name)
        if not data:
            raise commands.BadArgument("Tag not found.")

        owner = await self.bot.get_or_fetch_member(ctx.guild, data[2])
        if not owner:
            owner = await self.bot.fetch_user(data[3])
            if not owner:
                raise commands.BadArgument("I had a problem querying the owner of this tag.")

        embed = Embed(color=ctx.color, title=name)
        embed.set_author(name=owner, icon_url=owner.display_avatar.url)
        embed.add_field(name='Owner', value=owner.mention)
        embed.add_field(name='Uses', value=data[0])
        embed.add_field(name='Created', value=f"{discord.utils.format_dt(pytz.utc.localize(data[1]), 'R')}")
        
        await ctx.send(embed=embed)

    @tag.command(name='remove')
    async def tag_remove(self, ctx: MyContext, *, name: commands.clean_content):
        """Remove a tag by it's name."""

        status = await self.bot.db.execute("DELETE FROM tags WHERE name = $3 AND owner_id = $2 AND guild_id = $1", ctx.guild.id, ctx.author.id, name)
        if status == "DELETE 0":
            raise commands.BadArgument("Could not remove a tag with that name.")
        await ctx.send("Removed that tag.")

    @tag.command(name='list')
    async def tag_list(self, ctx: MyContext):
        """List all the tags in the current guild."""

        data = await self.bot.db.fetch("SELECT (name, uses) FROM tags WHERE guild_id = $1 ORDER BY uses", ctx.guild.id)
        if not data:
            raise commands.BadArgument("This server has no tags.")
        
        menu = SimplePages(source=TagSource(data, per_page=15), ctx=ctx, compact=True)
        await menu.start()
