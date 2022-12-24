import datetime
from typing import Dict, List, Union
import discord
from discord.ext import commands, menus
import humanize
import pytz
import yarl
from waifuim.types import Image

from bot import MetroBot
from utils.custom_context import MyContext
from utils.pages import SimplePages

async def setup(bot: MetroBot):
    await bot.add_cog(NSFW(bot))

def nsfw_cooldown(ctx: MyContext):
    bot: MetroBot = ctx.bot
    if bot.premium_users.get(ctx.author.id):
        return commands.Cooldown(1, 2)
    return commands.Cooldown(1, 6)

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

class NSFW(commands.Cog, description='NSFW commands reserved for labeled channel or my DMs.', name='nsfw'):
    def __init__(self, bot: MetroBot):
        self.bot = bot
        self.topgg = 'https://top.gg/bot/788543184082698252/vote'
        self.nekobot_api = 'https://nekobot.xyz/api/'

    @property
    def emoji(self) -> str:
        return '\U0001f51e'

    async def cog_command_error(self, ctx: MyContext, error: Exception) -> None:
        if isinstance(error, commands.CommandOnCooldown):
            try_again = humanize.precisedelta(datetime.timedelta(seconds=error.retry_after), format='%.0f' if error.retry_after > 1 else '%.1f')

            embed = discord.Embed()
            embed.set_author(name='Command on cooldown!')
            embed.set_footer(text=f'Try again in {try_again}')
  
            if not self.bot.premium_users.get(ctx.author.id):
                embed.description = "You can vote for the bot to get reduced cooldowns.\n"\
                    f"> <{self.topgg}>\n"

            await ctx.send(embed=embed)
            return

        elif isinstance(error, commands.NSFWChannelRequired):
            await ctx.send("A NSFW marked channel is required to run this command.", hide=True)
            return
            
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
        
    @commands.hybrid_group(name='waifu', invoke_without_command=True, fallback='commands')
    @commands.is_nsfw()
    async def waifu(self, ctx: MyContext):
        """Base command for waifu. See my subcommands."""

        await ctx.help()

    async def get_waifu_request(self, ctx: MyContext, tags: List[str]) -> Union[List[Image], Image, Dict]:
        images = await self.bot.wf.search(included_tags=tags, is_nsfw=True, many=True)

        if not await self.has_voted(ctx.author.id):
            images = images[0:3]
            
        source = ImageSource(list(images), per_page=1)
        menu = SimplePages(source, ctx=ctx, compact=True)
        await menu.start()

    @waifu.command(name='ass')
    @commands.is_nsfw()
    @commands.dynamic_cooldown(nsfw_cooldown, type=commands.BucketType.member)
    async def ass_command(self, ctx: MyContext):
        """Sends some ass."""
        await self.get_waifu_request(ctx, ['ass'])
        
    @waifu.command(name='hentai')
    @commands.is_nsfw()
    @commands.dynamic_cooldown(nsfw_cooldown, type=commands.BucketType.member)
    async def hentai_command(self, ctx: MyContext):
        """Sends some hentai."""
        await self.get_waifu_request(ctx, ['hentai'])

    @waifu.command(name='milf')
    @commands.is_nsfw()
    @commands.dynamic_cooldown(nsfw_cooldown, type=commands.BucketType.member)
    async def milf_command(self, ctx: MyContext):
        """Sends some milf."""
        await self.get_waifu_request(ctx, ['milf'])

    @waifu.command(name='oral')
    @commands.is_nsfw()
    @commands.dynamic_cooldown(nsfw_cooldown, type=commands.BucketType.member)
    async def oral_command(self, ctx: MyContext):
        """Sends some oral."""
        await self.get_waifu_request(ctx, ['oral'])
        
    @waifu.command(name='ero')
    @commands.is_nsfw()
    @commands.dynamic_cooldown(nsfw_cooldown, type=commands.BucketType.member)
    async def ero_command(self, ctx: MyContext):
        """Sends some ero."""
        await self.get_waifu_request(ctx, ['ero'])

    async def make_request(self, ctx: MyContext, tag: str) -> None:
        url = yarl.URL(self.nekobot_api + '/image').with_query({'type': tag})
        async with self.bot.session.get(url) as resp:
            if resp.status != 200:
                raise commands.BadArgument('NekoBot API returned a bad response.')

            data = await resp.json()
        url = data['message'] # url of an image/gif
        
        embed = discord.Embed()
        embed.set_image(url=url)

        vote_embed = discord.Embed(color=discord.Color.yellow())
        vote_embed.description = 'You can vote to get reduced nsfw cooldowns, up to 30 pages for waifu and more.\n'\
            f'> <{self.topgg}>'

        if self.bot.premium_users.get(ctx.author.id):
            await ctx.send(embeds=[embed])
        else:
            await ctx.send(embeds=[embed, vote_embed])
        
    @commands.hybrid_command(name='anal')
    @commands.is_nsfw()
    @commands.dynamic_cooldown(nsfw_cooldown, type=commands.BucketType.member)
    async def anal(self, ctx: MyContext):
        """Sends some anal."""
        await self.make_request(ctx, 'anal')

    @commands.hybrid_command(name='4k')
    @commands.is_nsfw()
    @commands.dynamic_cooldown(nsfw_cooldown, type=commands.BucketType.member)
    async def _4k(self, ctx: MyContext):
        """Sends some 4k images/gifs."""
        await self.make_request(ctx, '4k')

    @commands.hybrid_command(name='pussy')
    @commands.is_nsfw()
    @commands.dynamic_cooldown(nsfw_cooldown, type=commands.BucketType.member)
    async def _pussy(self, ctx: MyContext):
        """Sends some pussy."""
        await self.make_request(ctx, 'pussy')

    @commands.hybrid_command(name='ass')
    @commands.is_nsfw()
    @commands.dynamic_cooldown(nsfw_cooldown, type=commands.BucketType.member)
    async def _ass(self, ctx: MyContext):
        """Sends some ass."""
        await self.make_request(ctx, 'ass')

    @commands.hybrid_command(name='boobs')
    @commands.is_nsfw()
    @commands.dynamic_cooldown(nsfw_cooldown, type=commands.BucketType.member)
    async def _boobs(self, ctx: MyContext):
        """Sends some boobs."""
        await self.make_request(ctx, 'boobs')

    @commands.hybrid_command(name='gif', aliases=['pgif', 'porn'])
    @commands.is_nsfw()
    @commands.dynamic_cooldown(nsfw_cooldown, type=commands.BucketType.member)
    async def _gif(self, ctx: MyContext):
        """Sends some porn gifs."""
        await self.make_request(ctx, 'pgif')
