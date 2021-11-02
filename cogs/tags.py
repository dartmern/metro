import discord
from discord.ext import commands

from utils.tag_utils import TagName
from utils.context import MyContext




class tags(commands.Cog, description='<:mtag:904863878792491018> Manage and create tags.'):
    def __init__(self, bot):
        self.bot = bot

    async def fetch_tag(self, guild_id : int, name : str, *, connection=None):
        def disambigute(rows, query):
            if rows is None or len(rows) == 0:
                raise RuntimeError('Tag not found.')

            names = '\n'.join(r['name'] for r in rows)
            raise RuntimeError(f'Tag not found. Did you mean...\n{names}')

        conn = connection or self.bot.db

        query = """
                SELECT tags.name, tags.content
                FROM tag_lookup
                INNER JOIN tags ON tags.id = tag_lookup.tag_id
                WHERE tag_lookup.location=$1 AND LOWER(tag_lookup.name)=$2;
                """

        row = await conn.fetchrow(query, guild_id, name)
        if row is None:
            query = """SELECT     tag_lookup.name
                       FROM       tag_lookup
                       WHERE      tag_lookup.location_id=$1 AND tag_lookup.name % $2
                       ORDER BY   similarity(tag_lookup.name, $2) DESC
                       LIMIT 3;
                    """
            return disambigute(await conn.fetch(query, guild_id, name), name)
        else:
            return row


    @commands.group(
        name='tag',
        invoke_without_command=True,
        case_insensitive=True
    )
    async def tag(self, ctx, *, name : TagName(lower=True)):
        """Retrive a tag by it's name."""

        try:
            tag = self.fetch_tag(ctx.guild.id, name, connection=self.bot.db)
        except RuntimeError as e:
            return await ctx.send(str(e))

        await ctx.send(tag['content'], reference=ctx.replied_reference)

        #update tag usage down here:
        #
        #
    
    @tag.command(
        name='create'
    )
    async def tag_create(self, ctx, name : TagName, *, content : commands.clean_content):
        """
        Create a new tag owned by you.

        This tag will be for this server only and cannot be used in other servers.
        """

        if len(content) > 2000:
            return await ctx.send('Tag content cannot contain more than 2000 characters.')

        await self.create_tag(ctx, name, content)
        

        



def setup(bot):
    bot.add_cog(tags(bot))