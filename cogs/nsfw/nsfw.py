import datetime
import discord
from discord.ext import commands, menus
import pytz

from bot import MetroBot
from utils.custom_context import MyContext
from utils.new_pages import SimplePages

async def setup(bot: MetroBot):
    await bot.add_cog(NSFW(bot))

class ImageSource(menus.ListPageSource):
    async def format_page(self, menu, entries):

        maximum = self.get_max_pages()
        if maximum > 1:
            footer = f'Page {menu.current_page + 1}/{maximum} ({len(self.entries)} entries)'
            menu.embed.set_footer(text=footer)
        if len(self.entries) == 3:
            menu.embed.set_author(name='Want up to 30 images per command? Click here to vote!', url='https://top.gg/bot/788543184082698252/vote')
        menu.embed.set_image(url=entries.url)
        return menu.embed

async def cd(ctx: MyContext):
    if ctx.bot.premium_guilds.get(ctx.guild.id) or ctx.bot.premium_users.get(ctx.author.id):
        return commands.Cooldown(2, 6)
    return commands.Cooldown(2, 8)

class NSFW(commands.Cog, description='NSFW commands reserved for labeled channel or my DMs.', name='nsfw'):
    def __init__(self, bot: MetroBot):
        self.bot = bot
        self.topgg = 'https://top.gg/bot/788543184082698252/vote'

    @property
    def emoji(self) -> str:
        return '\U0001f51e'

    #@commands.is_nsfw()
    @commands.group(name='nsfw-info', invoke_without_command=True)
    async def nsfw_test(self, ctx: MyContext):
        """Information on NSFW commands."""

        cmds = ', '.join([f'`{c}`' for c in self.get_commands() if c.name != 'nsfw-info'])
        
        
        embed = discord.Embed(color=ctx.color)
        embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
        embed.description = "NSFW commands are only permitted to be used in NSFW labeled channels or my messages. \n"\
                             f'> You can run `{ctx.prefix}nsfw-info create <name>` to create a nsfw channel.'\
                            f'\n\nYou can vote for the bot for more features like **infinite scrolling** and **more commands**!\n'\
                            f'> [`CLICK HERE TO VOTE`]({self.topgg})'\
                            f'\n\n**Featured commands:**\n{cmds}'\
                            

        await ctx.send(embed=embed)

    @nsfw_test.command(name='create')
    @commands.has_permissions(manage_channels=True)
    async def nsfw_test_create(self, ctx: MyContext, *, name: str):
        """Create a NSFW labeled channel."""

        try:
            channel = await ctx.guild.create_text_channel(
                name, 
                nsfw=True, 
                reason=f'NSFW channel created by {ctx.author} (ID: {ctx.author.id})')
        except discord.HTTPException:
            await ctx.send('Had trouble creating a channel. Missing permissions?')
            return 

        await ctx.send(f'Created NSFW labeled channel. {channel.mention}')

    async def has_voted(self, user_id: int) -> bool:
        """Check if a user_id has voted or not."""

        query = "SELECT next_vote FROM votes WHERE user_id = $1"
        returned = await self.bot.db.fetchval(query, user_id)
        if not returned:
            return False
        next_vote = pytz.utc.localize(returned) + datetime.timedelta(hours=12)
        if discord.utils.utcnow() > next_vote:
            return False
        return True
        
    @commands.hybrid_command(name='ass')
    @commands.is_nsfw()
    async def ass_command(self, ctx: MyContext):
        """Sends some ass."""
        images = await self.bot.wf.search(included_tags=['ass'], is_nsfw=True, many=True)

        if not await self.has_voted(ctx.author.id):
            images = images[0:3]
            
        source = ImageSource(list(images), per_page=1)
        menu = SimplePages(source, ctx=ctx, compact=True)
        await menu.start()
        
    @commands.hybrid_command(name='hentai')
    @commands.is_nsfw()
    async def hentai_command(self, ctx: MyContext):
        """Sends some hentai."""
        images = await self.bot.wf.search(included_tags=['hentai'], is_nsfw=True, many=True)

        if not await self.has_voted(ctx.author.id):
            images = images[0:3]
            
        source = ImageSource(list(images), per_page=1)
        menu = SimplePages(source, ctx=ctx, compact=True)
        await menu.start()

    @commands.hybrid_command(name='milf')
    @commands.is_nsfw()
    async def milf_command(self, ctx: MyContext):
        """Sends some milf."""
        images = await self.bot.wf.search(included_tags=['milf'], is_nsfw=True, many=True)

        if not await self.has_voted(ctx.author.id):
            images = images[0:3]
            
        source = ImageSource(list(images), per_page=1)
        menu = SimplePages(source, ctx=ctx, compact=True)
        await menu.start()

    @commands.hybrid_command(name='oral')
    @commands.is_nsfw()
    async def oral_command(self, ctx: MyContext):
        """Sends some oral."""
        images = await self.bot.wf.search(included_tags=['oral'], is_nsfw=True, many=True)

        if not await self.has_voted(ctx.author.id):
            images = images[0:3]
            
        source = ImageSource(list(images), per_page=1)
        menu = SimplePages(source, ctx=ctx, compact=True)
        await menu.start()
        
    @commands.hybrid_command(name='ero')
    @commands.is_nsfw()
    async def ero_command(self, ctx: MyContext):
        """Sends some ero."""
        images = await self.bot.wf.search(included_tags=['ero'], is_nsfw=True, many=True)

        if not await self.has_voted(ctx.author.id):
            images = images[0:3]
            
        source = ImageSource(list(images), per_page=1)
        menu = SimplePages(source, ctx=ctx, compact=True)
        await menu.start()