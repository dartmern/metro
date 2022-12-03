# the command tracking part of taken from RoboDanny
# https://github.com/Rapptz/RoboDanny/blob/rewrite/cogs/stats.py
# this is licensed under MPL 2.0 which this bot is also licensed under

import asyncio
import random
import re
import asyncpg
from typing import TYPE_CHECKING, Any, Optional, TypedDict, Union
import discord
from discord.ext import commands, tasks
import pytz
import topgg
import datetime

from bot import MetroBot
from utils.constants import BOT_LOGGER_CHANNEL, VOTE_LOGS_CHANNEL
from utils.custom_context import MyContext
from utils.decos import is_support
from utils.json_loader import read_json
from utils.remind_utils import UserFriendlyTime, human_timedelta
from utils.useful import ts_now

if TYPE_CHECKING:
    from cogs.utility import utility, Timer
    
BOT_ID = 788543184082698252

async def setup(bot: MetroBot):
    await bot.add_cog(stats(bot))

info_file = read_json('info')
topgg_token = info_file['topgg_token']
vote_webhook_url = info_file['webhooks']['vote_webhook']
guild_webhook_url = info_file['webhooks']['guild_webhook']

_INVITE_REGEX = re.compile(r'(?:https?:\/\/)?discord(?:\.gg|\.com|app\.com\/invite)?\/[A-Za-z0-9]+')

def censor_invite(obj: Any, *, _regex=_INVITE_REGEX) -> str:
    return _regex.sub('[censored-invite]', str(obj))

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

class DataBatchEntry(TypedDict):
    guild: Optional[int]
    channel: int
    author: int
    used: str
    prefix: str
    command: str
    failed: bool
    app_command: bool

class stats(commands.Cog, description='Bot statistics tracking related.'):
    def __init__(self, bot: MetroBot):
        self.bot = bot
        self.topgg_client = topgg.DBLClient(bot=bot, token=topgg_token, session=bot.session)

        self.topgg_webhook = topgg.WebhookManager(bot).dbl_webhook('/dbl', 'auth')
        self.topgg_webhook.run(25565)

        self.vote_webhook = discord.Webhook.from_url(vote_webhook_url, session=bot.session)
        self.guild_webhook = discord.Webhook.from_url(guild_webhook_url, session=bot.session)

        self.top_gg = f"https://top.gg/bot/{BOT_ID}/vote"
        self.discordbotlist = f"https://discordbotlist.com/bots/{BOT_ID}"

        self.choices: list[str] = []
        self.stats_loop.start()

    @property
    def emoji(self) -> str:
        return '\U0001f4c8'

    def cog_unload(self) -> None:
        self.stats_loop.cancel()

    @tasks.loop(seconds=10)
    async def stats_loop(self):
        options = random.choice(self.choices)
        game = discord.Game(options)
        await self.bot.change_presence(activity=game)

    @stats_loop.before_loop
    async def before_stats_loop(self):
        await self.bot.wait_until_ready()

        self.choices = [
            '/play for music!',
            'join my support server!',
            f'with {len(self.bot.guilds)} guilds'
            ]

    @tasks.loop(minutes=10)
    async def post_guild_loop(self):

        if self.bot.user.id == BOT_ID:
            await self.topgg_client.post_guild_count(len(self.bot.guilds))

    @post_guild_loop.before_loop
    async def before_post_guild_loop(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_dbl_vote(self, data: topgg.types.BotVoteData):

        next_vote = (discord.utils.utcnow() + datetime.timedelta(days=1)).replace(tzinfo=None)
        votes = await self.bot.db.fetchval("SELECT votes FROM votes WHERE user_id = $1", int(data.user))
        if votes:
            query = """
                    UPDATE votes
                    SET votes = $1, next_vote = $2
                    WHERE user_id = $3
                    """
            await self.bot.db.execute(query, votes + 1, next_vote, int(data.user))
        else:
            query = """
                    INSERT INTO votes (user_id, votes, next_vote)
                    VALUES ($1, $2, $3)
                    """
            await self.bot.db.execute(query, int(data.user), 1, next_vote)

        channel = self.bot.get_channel(VOTE_LOGS_CHANNEL)
        if not channel:
            await self.bot.error_logger.send('Vote log channel could not be found.')
            return 

        embed = discord.Embed(color=discord.Color.gold())
        embed.description = (
            f"<@{data.user}> voted for {self.bot.user.name} on **Top.GG**! Thanks for your support. \n"\
            f"To vote click below: \n"\
            f"<https://top.gg/bot/{self.bot.user.id}/vote> \n"\
            f"<https://discordbotlist.com/bots/{self.bot.user.id}>"
        )
        message = await channel.send(embed=embed)

        user = self.bot.get_user(int(data.user))
        if not user:
            return 

        next_vote = pytz.utc.localize(next_vote)
        embed = discord.Embed(title='Thank you for voting!', color=discord.Color.purple())
        embed.description = f'Enjoy your premium perks. They will expire {discord.utils.format_dt(next_vote, "R")} unless you vote again. \n'\
                            f'Voting helps {self.bot.user.name} grow and be able to reach more users.'\
                            f'This is also a way to support the bot for completely free!\n\n'\
                            f'> You can click the button below to set a reminder to vote.'
        
        ctx = await self.bot.get_context(message)
        ctx.author = user
        ctx.channel = await user.create_dm()
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

        query = "SELECT (next_vote) FROM votes WHERE user_id = $1"
        rows = await self.bot.db.fetchval(query, user_id)

        next_vote = pytz.utc.localize(rows)
        real_vote_time = next_vote - datetime.timedelta(hours=12)
        if discord.utils.utcnow() < real_vote_time:
            return 
            
        try:
            self.bot.premium_users.pop(int(user_id))
        except KeyError:
            pass

    @commands.hybrid_command(name='vote')
    async def _vote(self, ctx: MyContext):
        """Get how to vote for the bot and gain premium perks."""

        embed = discord.Embed(color=ctx.color)
        embed.set_author(name=str(self.bot.user), icon_url=self.bot.user.display_avatar.url)

        query = "SELECT (next_vote) FROM votes WHERE user_id = $1"
        rows = await self.bot.db.fetchval(query, ctx.author.id)

        value = f"[`CLICK HERE TO VOTE`]({self.top_gg})"
        view = None
        if rows:
            next_vote = pytz.utc.localize(rows)
            real_vote_time = next_vote - datetime.timedelta(hours=12)
            if discord.utils.utcnow() > real_vote_time:
                pass
            else:
                value = f"Next vote {discord.utils.format_dt(real_vote_time, 'R')} \n"\
                    "> Click the button below to set a reminder."
                view = VoteView(real_vote_time, ctx=ctx)

        desc = "Voting on top.gg will grant you premium features for 24 hours. \n"\
                f"**top.gg**: \n{value}\n\n"\
                f"Want to continue the support? Vote on discordbotlist:\n<{self.discordbotlist}>"
        embed.description = desc            

        message = await ctx.send(embed=embed, view=view)
        if view:
            view.message = message

    async def register_command(self, ctx: MyContext) -> None:
        if ctx.command is None:
            return

        command = ctx.command.qualified_name
        is_app_command = ctx.interaction is not None
        if self.bot.command_stats[command]:
            self.bot.command_stats[command] += 1
        else:
            self.bot.command_stats[command] = 1
        self.bot.command_types_used[is_app_command] += 1
        message = ctx.message
        destination = None
        if ctx.guild is None:
            destination = 'Private Message'
            guild_id = None
        else:
            destination = f'#{message.channel} ({message.guild})'
            guild_id = ctx.guild.id

        if ctx.interaction and ctx.interaction.command:
            content = f'/{ctx.interaction.command.qualified_name}'
        else:
            content = message.content

        self.bot.logger.info(f'{message.created_at}: {message.author} in {destination}: {content}')
        query = """
                INSERT INTO commands (guild_id, channel_id, author_id, used, prefix, command, failed, app_command)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """
        await self.bot.db.execute(
            query, 
            guild_id, 
            ctx.channel.id, 
            ctx.author.id, 
            message.created_at.replace(tzinfo=None), 
            ctx.prefix, 
            command, 
            ctx.command_failed, 
            is_app_command)

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: MyContext):
        await self.register_command(ctx)

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        command = interaction.command
        # Check if a command is found and it's not a hybrid command
        # Hybrid commands are already counted via on_command_completion
        if (
            command is not None
            and interaction.type is discord.InteractionType.application_command
            and not command.__class__.__name__.startswith('Hybrid')  # Kind of awful, but it'll do
        ):
            # This is technically bad, but since we only access Command.qualified_name and it's
            # available on all types of commands then it's fine
            ctx = await self.bot.get_context(interaction)
            ctx.command_failed = interaction.command_failed or ctx.command_failed
            await self.register_command(ctx)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        if self.bot.guildblacklist.get(guild.id) is True:
            embed = discord.Embed(color=discord.Color.red())
            embed.description = f"I have automatically left this server due to it being blacklisted.\nPlease consider joining my [suppport server]({self.bot.support}) for more details."

            if guild.system_channel and guild.system_channel.permissions_for(guild.me).send_messages:
                
                await guild.system_channel.send(embed=embed)
                return await guild.leave()
            else:
                for channel in guild.text_channels:
                    if channel.permissions_for(guild.me).send_messages:
                        await channel.send(embed=embed)
                        break
                return await guild.leave()
        else:
            humans = [hum for hum in guild.members if not hum.bot]
            bots = [bot for bot in guild.members if bot.bot]

            embed = discord.Embed(color=discord.Colour.green())
            embed.title = "New Guild"
            embed.description = f"\n__**Name:**__ {guild.name} (ID: {guild.id})"\
                                f"\n__**Human/Bots:**__ {len(humans)}/{len(bots)}"\
                                f"\n__**Owner:**__ {guild.owner} (ID: {guild.owner_id})"\
                                f"\n__**Added:**__ {ts_now('F')} ({ts_now('R')})"
            count = discord.Embed(color=discord.Colour.purple(), description="Guilds count: **%s**" % len(self.bot.guilds))
            await self.guild_webhook.send(embeds=[embed, count])

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        humans = [hum for hum in guild.members if not hum.bot]
        bots = [bot for bot in guild.members if bot.bot]

        embed = discord.Embed(color=discord.Colour.red())
        embed.title = "Left Guild"
        embed.description = f"\n__**Name:**__ {guild.name} (ID: {guild.id})"\
                                f"\n__**Human/Bots:**__ {len(humans)}/{len(bots)}"\
                                f"\n__**Owner:**__ {guild.owner} (ID: {guild.owner_id})"
        count = discord.Embed(color=discord.Colour.purple(), description="Guilds count: **%s**" % len(self.bot.guilds))
        await self.guild_webhook.send(embeds=[embed, count])

    async def show_guild_stats(self, ctx: MyContext) -> None:
        lookup = (
            '\N{FIRST PLACE MEDAL}',
            '\N{SECOND PLACE MEDAL}',
            '\N{THIRD PLACE MEDAL}',
            '\N{SPORTS MEDAL}',
            '\N{SPORTS MEDAL}',
        )

        embed = discord.Embed(title='Server Command Stats', colour=discord.Colour.blurple())

        # total command uses
        query = "SELECT COUNT(*), MIN(used) FROM commands WHERE guild_id=$1;"
        count: tuple[int, datetime.datetime] = await self.bot.db.fetchrow(query, ctx.guild.id)  # type: ignore

        embed.description = f'{count[0]} commands used.'
        if count[1]:
            timestamp = count[1].replace(tzinfo=datetime.timezone.utc)
        else:
            timestamp = discord.utils.utcnow()

        embed.set_footer(text='Tracking command usage since').timestamp = timestamp

        query = """SELECT command,
                          COUNT(*) as "uses"
                   FROM commands
                   WHERE guild_id=$1
                   GROUP BY command
                   ORDER BY "uses" DESC
                   LIMIT 5;
                """

        records = await self.bot.db.fetch(query, ctx.guild.id)

        value = (
            '\n'.join(f'{lookup[index]}: {command} ({uses} uses)' for (index, (command, uses)) in enumerate(records))
            or 'No Commands'
        )

        embed.add_field(name='Top Commands', value=value, inline=True)

        query = """SELECT command,
                          COUNT(*) as "uses"
                   FROM commands
                   WHERE guild_id=$1
                   AND used > (CURRENT_TIMESTAMP - INTERVAL '1 day')
                   GROUP BY command
                   ORDER BY "uses" DESC
                   LIMIT 5;
                """

        records = await self.bot.db.fetch(query, ctx.guild.id)

        value = (
            '\n'.join(f'{lookup[index]}: {command} ({uses} uses)' for (index, (command, uses)) in enumerate(records))
            or 'No Commands.'
        )
        embed.add_field(name='Top Commands Today', value=value, inline=True)
        embed.add_field(name='\u200b', value='\u200b', inline=True)

        query = """SELECT author_id,
                          COUNT(*) AS "uses"
                   FROM commands
                   WHERE guild_id=$1
                   GROUP BY author_id
                   ORDER BY "uses" DESC
                   LIMIT 5;
                """

        records = await self.bot.db.fetch(query, ctx.guild.id)

        value = (
            '\n'.join(
                f'{lookup[index]}: <@!{author_id}> ({uses} bot uses)' for (index, (author_id, uses)) in enumerate(records)
            )
            or 'No bot users.'
        )

        embed.add_field(name='Top Command Users', value=value, inline=True)

        query = """SELECT author_id,
                          COUNT(*) AS "uses"
                   FROM commands
                   WHERE guild_id=$1
                   AND used > (CURRENT_TIMESTAMP - INTERVAL '1 day')
                   GROUP BY author_id
                   ORDER BY "uses" DESC
                   LIMIT 5;
                """

        records = await self.bot.db.fetch(query, ctx.guild.id)

        value = (
            '\n'.join(
                f'{lookup[index]}: <@!{author_id}> ({uses} bot uses)' for (index, (author_id, uses)) in enumerate(records)
            )
            or 'No command users.'
        )

        embed.add_field(name='Top Command Users Today', value=value, inline=True)
        await ctx.send(embed=embed)

    async def show_member_stats(self, ctx: MyContext, member: discord.Member) -> None:
        lookup = (
            '\N{FIRST PLACE MEDAL}',
            '\N{SECOND PLACE MEDAL}',
            '\N{THIRD PLACE MEDAL}',
            '\N{SPORTS MEDAL}',
            '\N{SPORTS MEDAL}',
        )

        embed = discord.Embed(title='Command Stats', colour=member.colour)
        embed.set_author(name=str(member), icon_url=member.display_avatar.url)

        # total command uses
        query = "SELECT COUNT(*), MIN(used) FROM commands WHERE guild_id=$1 AND author_id=$2;"
        count: tuple[int, datetime.datetime] = await self.bot.db.fetchrow(query, ctx.guild.id, member.id)  # type: ignore

        embed.description = f'{count[0]} commands used.'
        if count[1]:
            timestamp = count[1].replace(tzinfo=datetime.timezone.utc)
        else:
            timestamp = discord.utils.utcnow()

        embed.set_footer(text='First command used').timestamp = timestamp

        query = """SELECT command,
                          COUNT(*) as "uses"
                   FROM commands
                   WHERE guild_id=$1 AND author_id=$2
                   GROUP BY command
                   ORDER BY "uses" DESC
                   LIMIT 5;
                """

        records = await self.bot.db.fetch(query, ctx.guild.id, member.id)

        value = (
            '\n'.join(f'{lookup[index]}: {command} ({uses} uses)' for (index, (command, uses)) in enumerate(records))
            or 'No Commands'
        )

        embed.add_field(name='Most Used Commands', value=value, inline=False)

        query = """SELECT command,
                          COUNT(*) as "uses"
                   FROM commands
                   WHERE guild_id=$1
                   AND author_id=$2
                   AND used > (CURRENT_TIMESTAMP - INTERVAL '1 day')
                   GROUP BY command
                   ORDER BY "uses" DESC
                   LIMIT 5;
                """

        records = await self.bot.db.fetch(query, ctx.guild.id, member.id)

        value = (
            '\n'.join(f'{lookup[index]}: {command} ({uses} uses)' for (index, (command, uses)) in enumerate(records))
            or 'No Commands'
        )

        embed.add_field(name='Most Used Commands Today', value=value, inline=False)
        await ctx.send(embed=embed)

    def censor_object(self, obj: str | discord.abc.Snowflake) -> str:
        if not isinstance(obj, str) and obj.id in self.bot.blacklist:
            return '[censored]'
        return censor_invite(obj)

    @commands.group(name='stats', invoke_without_command=True, case_insensitive=True)
    @commands.guild_only()
    @commands.cooldown(1, 15.0, type=commands.BucketType.member)
    async def _stats_command(self, ctx: MyContext, *, member: discord.Member = None):
        """Send command stats of a guild or member."""

        async with ctx.typing():
            if member is None:
                await self.show_guild_stats(ctx)
            else:
                await self.show_member_stats(ctx, member)

    @_stats_command.command(name='global')
    @is_support()
    async def _stats_command_global(self, ctx: MyContext):
        """Global all time command statistics.
        
        This is a support only command due to how resource demanding it is."""

        query = "SELECT COUNT(*) FROM commands;"
        total: tuple[int] = await self.bot.db.fetchrow(query)  # type: ignore

        e = discord.Embed(title='Command Stats', colour=discord.Colour.blurple())
        e.description = f'{total[0]} commands used.'

        lookup = (
            '\N{FIRST PLACE MEDAL}',
            '\N{SECOND PLACE MEDAL}',
            '\N{THIRD PLACE MEDAL}',
            '\N{SPORTS MEDAL}',
            '\N{SPORTS MEDAL}',
        )

        query = """SELECT command, COUNT(*) AS "uses"
                   FROM commands
                   GROUP BY command
                   ORDER BY "uses" DESC
                   LIMIT 5;
                """

        records = await self.bot.db.fetch(query)
        value = '\n'.join(f'{lookup[index]}: {command} ({uses} uses)' for (index, (command, uses)) in enumerate(records))
        e.add_field(name='Top Commands', value=value, inline=False)

        query = """SELECT guild_id, COUNT(*) AS "uses"
                   FROM commands
                   GROUP BY guild_id
                   ORDER BY "uses" DESC
                   LIMIT 5;
                """

        records = await self.bot.db.fetch(query)
        value = []
        for (index, (guild_id, uses)) in enumerate(records):
            if guild_id is None:
                guild = 'Private Message'
            else:
                guild = self.censor_object(self.bot.get_guild(guild_id) or f'<Unknown {guild_id}>')

            emoji = lookup[index]
            value.append(f'{emoji}: {guild} ({uses} uses)')

        e.add_field(name='Top Guilds', value='\n'.join(value), inline=False)

        query = """SELECT author_id, COUNT(*) AS "uses"
                   FROM commands
                   GROUP BY author_id
                   ORDER BY "uses" DESC
                   LIMIT 5;
                """

        records = await self.bot.db.fetch(query)
        value = []
        for (index, (author_id, uses)) in enumerate(records):
            user = self.censor_object(self.bot.get_user(author_id) or f'<Unknown {author_id}>')
            emoji = lookup[index]
            value.append(f'{emoji}: {user} ({uses} uses)')

        e.add_field(name='Top Users', value='\n'.join(value), inline=False)
        await ctx.send(embed=e)

