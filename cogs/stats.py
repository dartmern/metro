import discord
from discord.ext import commands
import topgg
import datetime

from bot import MetroBot
from utils.json_loader import read_json

async def setup(bot: MetroBot):
    await bot.add_cog(stats(bot))

info_file = read_json('info')
topgg_token = info_file['topgg_token']

class stats(commands.Cog, description='Bot statistics tracking related.'):
    def __init__(self, bot: MetroBot):
        self.bot = bot
        self.topgg_client = topgg.DBLClient(bot=bot, token=topgg_token, session=bot.session)
        self.topgg_webhook = topgg.WebhookManager(bot).dbl_webhook('/dbl', 'auth')

        self.topgg_webhook.run(25565)

    @property
    def emoji(self) -> str:
        return '\U0001f4c8'

    @commands.Cog.listener()
    async def on_dbl_vote(self, data: topgg.types.BotVoteData):
        print('Voted', data)
        next_vote = discord.utils.utcnow() + datetime.timedelta(hours=12)
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


