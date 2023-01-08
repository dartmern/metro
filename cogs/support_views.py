import discord
from discord.ext import commands

from bot import MetroBot
from utils.constants import SUPPORT_GUILD, BOTS_ROLE, BOT_REQUESTS_CHANNEL
from utils.custom_context import MyContext
from utils.converters import BotUser
from utils.useful import Embed, dynamic_cooldown
from utils.checks import in_support

class support(commands.Cog, description='Support only commands.'):
    def __init__(self, bot : MetroBot):
        self.bot = bot
        

    @property
    def emoji(self) -> str:
        return '\U0001f9ea'
        
    @commands.Cog.listener()
    async def on_member_join(self, member : discord.Member):

        if member.guild.id != SUPPORT_GUILD:
            return

        if member.bot:
            await member.add_roles(discord.Object(id=BOTS_ROLE))

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id != SUPPORT_GUILD:
            return 

        if payload.channel_id != BOT_REQUESTS_CHANNEL:
            return

        #if self.bot.user.id == 795373951043633232:
            #return 
        if payload.user_id == self.bot.user.id:
            return # Lmao

        if str(payload.emoji) == "<:mCheck:819254444197019669>":
            channel = (
                self.bot.get_channel(payload.channel_id) or
                await self.bot.fetch_channel(payload.channel_id)
            )
            guild = self.bot.get_guild(SUPPORT_GUILD) # We're gonna assume it's the support server because we won't even be here
            message = await channel.fetch_message(payload.message_id)
            
            author_id = message.embeds[0].footer.text
            bot_id = message.embeds[0].author.name

            author = await self.bot.get_or_fetch_member(guild, author_id)

            embed = discord.Embed(color=discord.Colour.green())
            embed.description = f"The bot you requested, <@{bot_id}> was added to **{guild.name}**"
            
            return await author.send(embed=embed)

        if str(payload.emoji) == "<:mCross:819254444217860116>":
            channel = (
                self.bot.get_channel(payload.channel_id) or
                await self.bot.fetch_channel(payload.channel_id)
            )
            guild = self.bot.get_guild(SUPPORT_GUILD) # We're gonna assume it's the support server because we won't even be here
            message = await channel.fetch_message(payload.message_id)
            
            author_id = message.embeds[0].footer.text
            bot_id = message.embeds[0].author.name

            author = await self.bot.get_or_fetch_member(guild, author_id)

            embed = discord.Embed(color=discord.Colour.red())
            embed.description = f"The bot you requested, <@{bot_id}> was rejected from **{guild.name}**"
            
            await author.send(embed=embed)

    @commands.command(hidden=True)
    @commands.dynamic_cooldown(dynamic_cooldown, type=commands.BucketType.member)
    @in_support()
    async def addbot(
        self, 
        ctx : MyContext,
        user : BotUser,
        *,
        reason : str 
    ):
        """Request to add your bot to the server.
        
        To make a request you need your bot's user ID and a reason
        """

        confirm = await ctx.confirm(
            'This server\'s moderators have the right to kick or reject your bot for any reason.'
            '\nYou also agree that your bot does not have the following prefixes: `?`,`m?`,`m.`'
            '\nYour bot cannot have an avatar that might be considered NSFW, ping users when they join, post NSFW messages in not NSFW marked channels.'
            '\nRules that may apply to users should also be applied to bots.'
            '\n**This is not a exextensive list and you can see all the rules listed in <#814281422780235817>**'
            '\n\nHit the **Confirm** button below to submit your request and agree to these terms.', timeout=60
            )

        if not confirm.value:
            return

        else:
            
            url = f'https://discord.com/oauth2/authorize?client_id={user.id}&scope=bot&guild_id={ctx.guild.id}'
            description = f"{reason}\n\n[Invite URL]({url})"

            embed = Embed(title='Bot Request',description=description)
            embed.add_field(name='Author',value=f'{ctx.author} (ID: {ctx.author.id})',inline=False)
            embed.add_field(name='Bot',value=f'{user} (ID: {user.id})',inline=False)
            embed.timestamp = ctx.message.created_at

            embed.set_author(name=user.id, icon_url=user.display_avatar.url)
            embed.set_footer(text=ctx.author.id)

            try:
                channel = self.bot.get_channel(BOT_REQUESTS_CHANNEL)
                message = await channel.send(embed=embed)
            except discord.HTTPException as e:
                return await ctx.send(f'Failed to add your bot.\n{str(e)}')

            await message.add_reaction(self.bot._check)
            await message.add_reaction(self.bot.cross)

            await ctx.send('Your bot request has been submitted to the moderators. \nI will DM you about the status of your request.')

    @commands.command(name='solved')
    async def close_ticket(self, ctx: MyContext):
        """Make a thread as Solved."""

        if not isinstance(ctx.channel, discord.Thread):
            return

        await ctx.message.add_reaction(self.bot._check)
        await ctx.channel.add_tags(discord.Object(1019745545805365248))
        await ctx.channel.edit(
            locked=True, 
            archived=True, 
            reason=f'Marked solved by: {ctx.author} (ID: {ctx.author.id})',
            )
        

async def setup(bot):
    await bot.add_cog(support(bot))
