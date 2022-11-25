from typing import TYPE_CHECKING, Union
import discord
from discord.ext import commands
import pytz
import topgg
import datetime

from bot import MetroBot
from utils.constants import VOTE_LOGS_CHANNEL
from utils.custom_context import MyContext
from utils.json_loader import read_json
from utils.remind_utils import UserFriendlyTime, human_timedelta

if TYPE_CHECKING:
    from cogs.utility import utility, Timer
    
BOT_ID = 788543184082698252

async def setup(bot: MetroBot):
    await bot.add_cog(stats(bot))

info_file = read_json('info')
topgg_token = info_file['topgg_token']
vote_webhook_url = info_file['webhooks']['vote_webhook']

class VoteView(discord.ui.View):
    def __init__(self, duration: Union[datetime.datetime, str], *, ctx: MyContext):
        super().__init__(timeout=300)
        self.duration = duration
        self.message: discord.Message = None
        self.ctx = ctx
        self.top_gg = f"https://top.gg/bot/{ctx.me.id}/vote"

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.ctx.author.id:
            return True
        await interaction.response.send_message('This menu cannot be controlled by you, sorry!', ephemeral=True)
        return False

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)

    @discord.ui.button(label='Reminder', style=discord.ButtonStyle.green)
    async def reminder_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        await interaction.response.defer()
        command = interaction.client.get_command('reminder')
        if not command:
            await interaction.response.send_message('This feature is currently not available. Sorry.', ephemeral=True)
        else:
            if not isinstance(self.duration, str):
                duration = human_timedelta(self.duration, brief=True)
            else:
                duration = self.duration
            message = f"{duration} Vote for {self.ctx.me.name} on **top.gg**:\n<{self.top_gg}>"
            
            when = await UserFriendlyTime().convert(self.ctx, message)
            await self.ctx.invoke(command, when=when)
        await self.on_timeout()

class stats(commands.Cog, description='Bot statistics tracking related.'):
    def __init__(self, bot: MetroBot):
        self.bot = bot
        self.topgg_client = topgg.DBLClient(bot=bot, token=topgg_token, session=bot.session)

        self.topgg_webhook = topgg.WebhookManager(bot).dbl_webhook('/dbl', 'auth')
        self.topgg_webhook.run(25565)

        self.vote_webhook = discord.Webhook.from_url(vote_webhook_url, session=bot.session)

        self.top_gg = f"https://top.gg/bot/{BOT_ID}/vote"
        self.discordbotlist = f"https://discordbotlist.com/bots/{BOT_ID}"

    @property
    def emoji(self) -> str:
        return '\U0001f4c8'

    @commands.Cog.listener()
    async def on_dbl_vote(self, data: topgg.types.BotVoteData):

        next_vote = (discord.utils.utcnow() + datetime.timedelta(hours=12)).replace(tzinfo=None)
        votes = await self.bot.db.fetchval("SELECT votes FROM votes WHERE user_id = $1", int(data.user))
        if votes:
            query = """
                    UPDATE votes
                    SET votes = $1, has_voted = True, next_vote = $2
                    WHERE user_id = $3
                    """
            await self.bot.db.execute(query, votes + 1, next_vote, int(data.user))
        else:
            query = """
                    INSERT INTO votes (user_id, votes, has_voted, next_vote)
                    VALUES ($1, $2, $3, $4)
                    """
            await self.bot.db.execute(query, int(data.user), 1, True, next_vote)

        channel = self.bot.get_channel(VOTE_LOGS_CHANNEL)
        if not channel:
            await self.bot.error_logger.send('Vote log channel could not be found.')
            return 

        message = await self.vote_webhook.send(
            f"<@{data.user}> voted for {self.bot.user.name} on **Top.GG**! Thanks for your support. \n"\
            f"To vote click below: \n"\
            f"<https://top.gg/bot/{self.bot.user.id}/vote> \n"\
            f"<https://discordbotlist.com/bots/{self.bot.user.id}>"
        )

        user = self.bot.get_user(int(data.user))
        if not user:
            return 

        embed = discord.Embed(title='Thank you for voting!', color=discord.Color.purple())
        embed.description = f'Enjoy your premium perks. They will expire {discord.utils.format_dt(next_vote)} unless you vote again. \n'\
                            f'Voting helps {self.bot.user.name} grow and be able to reach more users.'\
                            f'This is also a way to support the bot for completely free!\n\n'\
                            f'> You can click the button below to set a reminder to vote.'
        
        ctx = self.bot.get_context(message)
        view = VoteView('12 hours', ctx=ctx)

        try:
            view.message = await user.send(embed=embed, view=view)
        except discord.HTTPException:
            pass

        reminder_cog: utility = self.bot.get_cog('utility')
        await reminder_cog.create_timer(
            next_vote,
            'vote_completion',
            user.id
        )
        self.bot.premium_users[int(data.user)] = True

    @commands.Cog.listener()
    async def on_vote_completion_timer_complete(self, timer):
        user_id = timer.args[0]

        query = 'UPDATE votes SET has_voted = False WHERE user_id = $1'
        await self.bot.db.execute(query, user_id)

        try:
            self.bot.premium_users.pop(int(user_id))
        except KeyError:
            pass

    @commands.hybrid_command(name='vote')
    async def _vote(self, ctx: MyContext):
        """Get how to vote for the bot and gain premium perks."""

        embed = discord.Embed(color=ctx.color)
        embed.set_author(name=str(self.bot.user), icon_url=self.bot.user.display_avatar.url)

        query = "SELECT (has_voted, next_vote) FROM votes WHERE user_id = $1"
        rows = await self.bot.db.fetchrow(query, ctx.author.id)

        if rows and rows['row'][0] is True:
            next_vote = pytz.utc.localize(rows['row'][1])
            value = f"Next vote {discord.utils.format_dt(next_vote, 'R')} \n"\
                "> Click the button below to set a reminder."
            view = VoteView(next_vote, ctx=ctx)
        else:
            value = f"[`CLICK HERE TO VOTE`]({self.top_gg})"
            view = None

        desc = "Voting on top.gg will grant you premium features for 12 hours. \n"\
                f"**top.gg**: \n{value}\n\n"\
                f"Want to continue the support? Vote on discordbotlist:\n<{self.discordbotlist}>"
        embed.description = desc            

        message = await ctx.send(embed=embed, view=view)
        if view:
            view.message = message
