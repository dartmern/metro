import discord
from discord.ext import commands

from bot import MetroBot
from utils.custom_context import MyContext

async def setup(bot: MetroBot):
    await bot.add_cog(NSFW(bot))

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
        
    