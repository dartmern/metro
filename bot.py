from collections import Counter
import sys
import traceback
import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import AppCommand
from discord.abc import Snowflake

import asyncio
import datetime
import re
from typing import Any, List, Optional, Tuple, Union
import asyncpixel
from pathlib import Path
import os
import async_cse
import asyncpg
import mystbin
import aiohttp
import logging
import pytz
import topgg
import waifuim

from utils.checks import check_dev
from utils.constants import BOT_LOGGER_CHANNEL, BOT_OWNER_ID, DEFAULT_INVITE, DEVELOPER_IDS, DOCUMENTATION, EMOTES, GITHUB_URL, PATREON_URL, PRIVACY_POLICY, SUPPORT_GUILD, SUPPORT_STAFF, SUPPORT_URL, TEST_BOT_ID
from utils.logger import setup_logging
from utils.remind_utils import human_timedelta
from utils.json_loader import read_json
from utils.errors import UserBlacklisted
from utils.custom_context import MyContext
from utils.useful import ts_now

os.environ["JISHAKU_NO_UNDERSCORE"] = "True"
os.environ["JISHAKU_NO_DM_TRACEBACK"] = "True"

info_file = read_json('info')

setup_logging()

database_info = info_file['database_info']

database = database_info['database']
user = database_info['user']
password = database_info['password']
host = database_info['host']
port = database_info['port']

token = info_file['bot_token']

google_token = info_file['google_token']

webhooks = info_file['webhooks']

async def create_db_pool(user, password, database, host, port) -> asyncpg.Pool:
    details = {
        "user" : user,
        "password" : password,
        "database" : database,
        "host" : host,
        "port" : port
    }
    return await asyncpg.create_pool(**details)
    
class MetroBot(commands.AutoShardedBot):
#class MetroBot(commands.Bot):
    PRE: tuple = ('m.', 'm?')

    def user_blacklisted(self, ctx : MyContext):
        try:
            is_blacklisted = self.blacklist[ctx.author.id]
        except KeyError:
            is_blacklisted = False
        if ctx.author.id == self.owner_id:
            is_blacklisted = False
        
        if is_blacklisted is False:
            return True
        else:
            raise UserBlacklisted

    def __init__(self):
        intents = discord.Intents(
            emojis=True,
            guild_messages=True,
            guild_reactions=True,
            guilds=True,
            members=True,
            message_content=True,
            messages=True,
            presences=True,
            voice_states=True,
            webhooks=True)

        allowed_mentions = discord.AllowedMentions(
            roles=False, users=True, everyone=False, replied_user=False)

        super().__init__(
            intents=intents,
            command_prefix=self.get_pre,
            case_insensitive=True,
            allowed_mentions=allowed_mentions,
            owner_ids=DEVELOPER_IDS,
            help_command=None,
            strip_after_prefix=True,
            #shard_count=10,
            max_messages=250
        )

        self.db: asyncpg.Pool = discord.utils.MISSING
        
        self.mystbin_client = mystbin.Client(token=info_file['mystbin_key'])
        self.google_client = async_cse.Search(google_token)
        self.hypixel = asyncpixel.Hypixel(info_file['hypixel_api_key'])

        self.add_check(self.user_blacklisted)

        self.maintenance = False
        self.owner: Optional[discord.User] = None

        self.support_staff = SUPPORT_STAFF

        self.noprefix = False
        self.started = False

        self.uptime = discord.utils.utcnow()

        #Cache
        self.prefixes: dict[int, list[str]] = {}
        self.blacklist: dict[int, bool] = {}
        self.guildblacklist: dict[int, bool] = {}
        self.app_commands: dict[str, int] = {}
        
        self.premium_users: dict[int, bool] = {}
        self.premium_guilds: dict[int, bool] = {}

        #Tracking
        self.command_stats = Counter()
        self.command_types_used = Counter()
        
        #Emojis
        self.emotes = EMOTES
        self.TEST_BOT_ID = TEST_BOT_ID
        self._check = "<:mCheck:819254444197019669>"
        self.cross = "<:mCross:819254444217860116>"

        # logging
        self.logger = logging.getLogger()
        
        # typechecking stuff
        self.session: aiohttp.ClientSession
        self.error_logger: discord.Webhook
        self.status_logger: discord.Webhook
        self.topgg_webhook: topgg.WebhookManager
        self.wf: waifuim.WaifuAioClient

    @property
    def donate(self) -> str:
        return PATREON_URL

    @property
    def patreon(self) -> str:
        return self.donate

    @property
    def docs(self) -> str:
        return DOCUMENTATION

    @property
    def invite(self) -> str:
        return DEFAULT_INVITE

    @property
    def github(self) -> str:
        return GITHUB_URL

    @property
    def source(self) -> str:
        return self.github

    @property
    def support(self) -> str:
        return SUPPORT_URL

    @property
    def privacy_policy(self) -> str:
        return PRIVACY_POLICY

    def get_app_command(
        self, value: Union[str, int]) -> Optional[Tuple[str, int]]:
        """Get an app command as a tuple. (name, id)
        
        This is not an API call and it is from the cache."""

        for name, _id in self.app_commands.items():
            if value == name or value.isdigit() and int(value) == _id:
                return name, _id
        return None # not found in cache

    async def update_app_commands_cache(
        self,
        *,
        commands: Optional[List[AppCommand]] = None,
        guild: Optional[Snowflake] = None
    ) -> None:
        """
        Fill the cache of app commands.
        This is not called on startup but manually through a sync.
        
        Calling this without the commands argument will result in a api fetch.
        """
        if not commands:
            commands = await self.tree.fetch_commands(guild=guild.id if guild else None)
        self.app_commands = {cmd.name: cmd.id for cmd in commands}

    async def fill_bot_cache(self):
        """Fill the bot's utility cache.
        
        This is called upon startup or through a manual command."""

        await self.wait_until_ready()

        # premium guilds cache
        query = """
                SELECT server FROM premium_guilds WHERE is_premium = True
                """
        records = await self.db.fetch(query)
        if records:
            for record in records:
                self.premium_guilds[record['server']] = True

        # premium users / voters cache
        query = """
                SELECT (user_id, next_vote) FROM votes
                """
        records = await self.db.fetch(query)
        if records:
            for record in records:
                next_vote = pytz.utc.localize(record['row'][1])
                if discord.utils.utcnow() < (next_vote - datetime.timedelta(hours=12)):
                    self.premium_users[record['row'][0]] = True

        # guild blacklist cache
        query = """
                SELECT guild FROM guild_blacklist WHERE verify = True
                """
        records = await self.db.fetch(query)
        if records:
            for record in records:
                self.guildblacklist[record["guild"]] = True

        # member blacklist cache
        query = """
                SELECT member_id FROM blacklist WHERE is_blacklisted = True
                """

        records = await self.db.fetch(query)
        if records:
            for record in records:
                self.blacklist[record["member_id"]] = True
        
        # highlight cache
        utility_cog = self.get_cog('utility') # type: ignore
        query = """
                SELECT * FROM highlight
                """
        records = await self.db.fetch(query)
        if records:
            for record in records:
                if utility_cog.highlight_cache.get((record['guild_id'], record['author_id'])):
                    utility_cog.highlight_cache[(record['guild_id'], record['author_id'])].append(record['text'])
                else:
                    utility_cog.highlight_cache[(record['guild_id'], record['author_id'])] = [record['text']]

        # afk cache
        serverutils_cog = self.get_cog('serverutils')
        query = """
                SELECT _user FROM afk WHERE is_afk = True
                """

        records = await self.db.fetch(query)
        if records:
            for record in records:
                serverutils_cog.afk_users[record['_user']] = True
        
        logging.info('Bot\'s cache was refreshed.')

    async def add_to_guildblacklist(
        self, guild: int, *, reason: Optional[str] = None, 
        ctx: MyContext, silent: bool = False) -> discord.Message:
        """Add a guild to the blacklist."""

        if guild == SUPPORT_GUILD:
            return await ctx.send("I have been hard configurated to not blacklist this guild.", reply=False)

        query = """
                INSERT INTO guild_blacklist (guild, verify, moderator, added_time, reason)
                VALUES ($1, $2, $3, $4, $5)
                """
        try:
            await self.db.execute(query, guild, True, ctx.author.id, (discord.utils.utcnow().replace(tzinfo=None)), reason)
        except asyncpg.exceptions.UniqueViolationError:
            return await ctx.send("This guild is already blacklisted.", reply=False)
        self.guildblacklist[guild] = True

        if silent is False:
            return await ctx.send(f"{self.emotes['check']} Added **{guild}** to blacklist.")

    async def remove_from_guildblacklist(self, guild: int, *, ctx: MyContext) -> discord.Message:
        """Remove a guild from the blacklist."""

        query = """
                DELETE FROM guild_blacklist WHERE guild = $1
                """
        status = await self.db.execute(query, guild)
        if status == "DELETE 0":
            return await ctx.send(f"{self.emotes['cross']} **{guild}** is not currently blacklisted.")
        else:
            self.guildblacklist[guild] = False
            return await ctx.send(f"{self.emotes['check']} Removed **{guild}** from the blacklist.")

    async def add_to_blacklist(
        self, ctx: MyContext, member: Union[discord.Member, discord.User], 
        reason : str = None, *, silent : bool = False) -> discord.Message:
        """Add a user to the global blacklist."""

        if check_dev(self, member):
            if silent is True:
                return
            return await ctx.send("I have been hard configured to not blacklist this user.")

        query = """
                INSERT INTO blacklist(member_id, is_blacklisted, moderator, added_time, reason) VALUES ($1, $2, $3, $4, $5) 
                """
        try:
            await self.db.execute(query, member.id, True, ctx.author.id, (discord.utils.utcnow().replace(tzinfo=None)), reason)
        except asyncpg.exceptions.UniqueViolationError:
            return await ctx.send(f"This user is already blacklisted.")
        self.blacklist[member.id] = True

        if silent is False:
            return await ctx.send(f"{self._check} Added **{member}** to the bot blacklist.")

    async def remove_from_blacklist(
        self, ctx: MyContext, member : Union[discord.Member, discord.User]) -> discord.Message:
        """Remove a user from the global blacklist."""

        query = """
                DELETE FROM blacklist WHERE member_id = $1
                """
        status = await self.db.execute(query, member.id)
        if status == "DELETE 0":
            return await ctx.send(f"{self.emotes['cross']} **{member}** is not currently blacklisted.")
        else:
            self.blacklist[member.id] = False
            return await ctx.send(f"{self._check} Removed **{member}** from the bot blacklist.")

    async def startup(self) -> None:
        """Startup the bot. This is called at startup and not manually."""

        await self.wait_until_ready()

        user = self.get_user(BOT_OWNER_ID)
        self.owner = user

        data = read_json("restart")
        if data:
            channel = self.get_channel(data['channel'])
            if not channel:
                return 
            message = channel.get_partial_message(data['id']) # this can't be none
            dt = datetime.datetime.fromtimestamp(data['now'])
            
            try:
                await message.edit(content=f'{self.emotes["check"]} Restart complete after {human_timedelta(dt, suffix=False)}')
            except discord.HTTPException:
                pass

        await self.fill_bot_cache()
        # fill the bot cache

    def add_command(self, command: commands.Command):
        """Override `add_command` to make a default cooldown for every command"""

        super().add_command(command)
        command.cooldown_after_parsing = True

    async def get_context(self, message: Union[discord.Message, discord.Interaction], *, cls=MyContext):
        """Making our custom context"""

        return await super().get_context(message, cls=cls)


    async def process_commands(self, message: discord.Message) -> None:
        """Override process_commands to check, and call typing every invoke."""

        if message.author.bot:
            return

        ctx = await self.get_context(message)
        if check_dev(ctx.bot, ctx.author):
            await self.invoke(ctx)
            return

        if self.maintenance and ctx.valid:
            await message.channel.send(f"The bot is currently in maintenance. Please try again later.")
            return

        await self.invoke(ctx)

    async def get_pre(self, bot, message : discord.Message, raw_prefix : Optional[bool] = False) -> List[str]:
        if not message:
            return commands.when_mentioned_or(*self.PRE)(bot, message) if not raw_prefix else self.PRE
        if not message.guild:
            return commands.when_mentioned_or(*self.PRE)(bot, message) if not raw_prefix else self.PRE
        try:
            prefix = self.prefixes[message.guild.id]
          
        except KeyError:
            prefix = [x['prefix'] for x in 
                    await self.db.fetch("SELECT prefix FROM prefixes WHERE guild_id = $1", message.guild.id)] or self.PRE
            self.prefixes[message.guild.id] = prefix
        
        if check_dev(bot, message.author) and self.noprefix is True:
            return commands.when_mentioned_or(*prefix, "")(bot, message) if not raw_prefix else prefix
        return commands.when_mentioned_or(*prefix)(bot, message) if not raw_prefix else prefix 

    async def fetch_prefixes(self, guild_id: int):
        return tuple([x['prefix'] for x in
            await self.db.fetch('SELECT prefix from prefixes WHERE guild_id = $1', guild_id)]) or self.PRE

    async def get_or_fetch_member(self, guild: discord.Guild, member_id: int) -> Optional[discord.Member]:
        """Looks up a member in cache or fetches if not found.
        Parameters
        -----------
        guild: discord.Guild
            The guild to look in.
        member_id: int
            The member ID to search for.
        Returns
        ---------
        Optional[discord.Member]
            The member or None if not found.
        """

        member = guild.get_member(member_id)
        if member is not None:
            return member

        shard = self.get_shard(guild.shard_id)
        if shard.is_ws_ratelimited():
            try:
                member = await guild.fetch_member(member_id)
            except discord.HTTPException:
                return None
            else:
                return member

        members = await guild.query_members(limit=1, user_ids=[member_id], cache=True)
        if not members:
            return None
        return members[0]

cwd = Path(__file__).parents[0]
cwd = str(cwd)
print(f"{cwd}\n-----")

bot = MetroBot()
  
@bot.listen('on_message')
async def mention_prefix(message: discord.Message):
    if re.fullmatch(rf"<@!?{bot.user.id}>", message.content):
        return await message.channel.send(f"\U0001f44b My prefixes here are: {', '.join(await bot.get_pre(bot, message, raw_prefix=True))}")

@bot.event
async def on_error(event: str, *args: Any, **kwargs: Any) -> None:
    (exc_type, exc, tb) = sys.exc_info()
    # Silence command errors that somehow get bubbled up far enough here
    if isinstance(exc, commands.CommandInvokeError):
        return

    e = discord.Embed(title='Event Error', colour=0xA32952)
    e.add_field(name='Event', value=event)
    trace = "".join(traceback.format_exception(exc_type, exc, tb))
    e.description = f'```py\n{trace}\n```'
    e.timestamp = discord.utils.utcnow()

    args_str = ['```py']
    for index, arg in enumerate(args):
        args_str.append(f'[{index}]: {arg!r}')
    args_str.append('```')
    e.add_field(name='Args', value='\n'.join(args_str), inline=False)
    
    hook = bot.error_logger
    try:
        await hook.send(embed=e)
    except:
        pass

async def main():
    async with aiohttp.ClientSession() as session:
        async with bot:
            bot.session = session
            bot.db = await create_db_pool(user, password, database, host, port)
            bot.loop.create_task(bot.startup())

            bot.wf = waifuim.WaifuAioClient(session=session, appname='metrodiscordbot')

            bot.error_logger = discord.Webhook.from_url(webhooks['error_handler'], session=bot.session)

            folders = ['giveaway_rewrite', 'tags', 'nsfw']

            bot.owner = bot.get_user(BOT_OWNER_ID)

            for file in os.listdir(cwd + "/cogs"):
                if file.endswith(".py") and not file.startswith("_"):
                    await bot.load_extension(f"cogs.{file[:-3]}")
                if file in folders:
                    await bot.load_extension(f"cogs.{file}")

            await bot.load_extension('jishaku') # jishaku

            await bot.tree.set_translator(app_commands.Translator()) # translator

            await bot.start(token)


if __name__ == "__main__":
    # When running this file, if it is the 'main' file
    # I.E its not being imported from another python file run this
    asyncio.run(main())