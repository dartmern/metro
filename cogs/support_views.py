import re
import discord
import time
from discord.ext import commands
from bot import MetroBot
from utils.constants import FEEDBACK_CHANNEL, SUPPORT_GUILD, SUPPORT_ROLE, BOTS_ROLE, BOT_REQUESTS_CHANNEL


from utils.custom_context import MyContext
from utils.converters import BotUser
from utils.useful import Cooldown, Embed, ts_now
from utils.decos import in_support, is_dev






class support(commands.Cog, description='Support only commands.'):
    def __init__(self, bot : MetroBot):
        self.bot = bot

    @property
    def emoji(self) -> str:
        return '🧪'
        
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

        if self.bot.user.id == 795373951043633232:
            return 
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

            
            await author.send(embed=embed)

        if str(payload.emoji) == "<:mCross:819254444217860116>":
            channel = (
                self.bot.get_channel(payload.channel_id) or
                await self.bot.fetch_channel(payload.channel_id)
            )
            guild = await self.bot.get_guild(SUPPORT_GUILD) # We're gonna assume it's the support server because we won't even be here
            message = await channel.fetch_message(payload.message_id)
            
            author_id = message.embeds[0].footer.text
            bot_id = message.embeds[0].author.name

            author = await self.bot.get_or_fetch_member(guild, author_id)

            embed = discord.Embed(color=discord.Colour.green())
            embed.description = f"The bot you requested, <@{bot_id}> was rejected from **{guild.name}**"
            
            try:
                await author.send(embed=embed)
            except discord.HTTPException:
                pass
            

    @commands.command(hidden=True)
    @commands.check(Cooldown(1, 10, 1, 10, bucket=commands.BucketType.member))
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
            '\nYou also agree that your bot does not have the following prefixes: `?`,`!`'
            '\nYour bot cannot have an avatar that might be considered NSFW, ping users when they join, post NSFW messages in not NSFW marked channels.'
            '\nRules that may apply to users should also be applied to bots.'
            '\n**This is not a exextensive list and you can see all the rules listed in <#814281422780235817>**'
            '\n\nHit the **Confirm** button below to submit your request and agree to these terms.', timeout=60  
            )

        if confirm is False:
            return await ctx.send('Canceled.')
        if confirm is None:
            return await ctx.send('Timed out.')

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
                channel = self.bot.get_channel(904184918840602684)
                message = await channel.send(embed=embed)
            except discord.HTTPException as e:
                return await ctx.send(f'Failed to add your bot.\n{str(e)}')

            await message.add_reaction(self.bot.check)
            await message.add_reaction(self.bot.cross)

            await ctx.send('Your bot request has been submitted to the moderators. \nI will DM you about the status of your request.')

    @commands.command(name='tester', hidden=True)
    @in_support()
    async def tester(self, ctx : MyContext):
        """Toggle the tester role for yourself."""

        role = ctx.guild.get_role(TESTER_ROLE)

        if role in ctx.author.roles:
            await ctx.author.remove_roles(role)
            return await ctx.message.add_reaction(self.bot.emotes['minus'])

        else:
            await ctx.author.add_roles(role)
            return await ctx.message.add_reaction(self.bot.emotes['plus'])

    @commands.command(name='feedback')
    @commands.check(Cooldown(1, 600, 1, 600, commands.BucketType.user))
    async def give_feedback(self, ctx: MyContext, *, message: str):
        """
        Give feedback about the bot.
        
        This can be almost anything from "good bot" to
        a long ass essay. Thank you for feedback!
        """
        channel = self.bot.get_channel(FEEDBACK_CHANNEL)
        if not channel:
            raise commands.BadArgument("This command is broken as of now....")

        embed = discord.Embed(color=discord.Color.green())
        embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
        embed.description = f"Feedback given: {ts_now('F')} ({ts_now('R')})\nUser ID: {ctx.author.id}\n\n{message}"
        embed.set_footer(text='You can use ?dm <id> <message> to thank them with a message.')
        await channel.send(embed=embed)
        await ctx.send(f"{self.bot.emotes['check']} Feedback submitted! Thank you.")

    @commands.command(name='dm', hidden=True)
    async def ___message(self, ctx: MyContext, id: int, *, message: str):
        """Send a message to a user id."""
        if ctx.guild.id != SUPPORT_GUILD:
            return 
        if SUPPORT_ROLE not in list(map(int, ctx.author.roles)):
            return 

        user = await self.bot.try_user(id)
        if not user:
            raise commands.BadArgument("User was not found....")
        try:
            await user.send(message)
            await ctx.check()
        except:
            await ctx.cross()      
    
def setup(bot):
    bot.add_cog(support(bot))
