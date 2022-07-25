import asyncio
import collections
import datetime
import re
from typing import List, Optional, Union
import typing
import asyncpixel
import discord
from discord.ext import commands

from pathlib import Path
import os
import async_cse
import asyncpg
import traceback

import mystbin
import aiohttp
import logging
from config.view import SupportView

from utils.checks import check_dev
from utils.constants import BOT_LOGGER_CHANNEL, BOT_OWNER_ID, DEFAULT_INVITE, DEVELOPER_IDS, DOCUMENTATION, EMOTES, GITHUB_URL, PATREON_URL, PRIVACY_POLICY, SLASH_GUILDS, SUPPORT_GUILD, SUPPORT_STAFF, SUPPORT_URL, TEST_BOT_ID
from utils.remind_utils import human_timedelta

from utils.useful import Cooldown, ts_now
from utils.json_loader import read_json
from utils.errors import UserBlacklisted
from utils.custom_context import MyContext

os.environ["JISHAKU_NO_UNDERSCORE"] = "True"
os.environ["JISHAKU_NO_DM_TRACEBACK"] = "True"

info_file = read_json('info')


logging.basicConfig(level=logging.INFO)
#logger = logging.getLogger('discord')
#logger.setLevel(logging.DEBUG)
#handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
#handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
#logger.addHandler(handler)

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
    
async def execute_scripts():
    await bot.wait_until_ready()

    scripts = [x[:-4] for x in sorted(os.listdir("./database")) if x.endswith(".sql")]

    for script in scripts:
        with open(f"./database/{script}.sql", "r", encoding='utf-8') as script:
            try:
                await bot.db.execute(script.read())
            except Exception as e:
                etype = type(e)
                trace = e.__traceback__

                lines = traceback.format_exception(etype, e, trace)

                to_p = ''.join(lines)
                print(to_p)

async def load_blacklist():
    await bot.wait_until_ready()

    query = """
            SELECT member_id FROM blacklist WHERE is_blacklisted = True
            """

    records = await bot.db.fetch(query)
    if records:
        for record in records:
            bot.blacklist[record["member_id"]] = True

async def load_guildblacklist():
    await bot.wait_until_ready()

    query = """
            SELECT guild FROM guild_blacklist WHERE verify = True
            """
    records = await bot.db.fetch(query)
    if records:
        for record in records:
            bot.guildblacklist[record["guild"]] = True

async def load_premiumguilds():
    await bot.wait_until_ready()

    query = """
            SELECT server FROM premium_guilds WHERE is_premium = True
            """
    records = await bot.db.fetch(query)
    if records:
        for record in records:
            bot.premium_guilds[record['server']] = True


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
        intents = discord.Intents.all()
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
            max_messages=5000
        )

        self.db: asyncpg.Pool = discord.utils.MISSING
        
        self.mystbin_client = mystbin.Client()
        self.google_client = async_cse.Search(google_token)
        self.hypixel = asyncpixel.Hypixel(info_file['hypixel_api_key'])

        self.add_check(self.user_blacklisted)

        self.maintenance = False
        self.owner = None

        self.support_staff = SUPPORT_STAFF

        self.noprefix = False
        self.started = False

        self.uptime = discord.utils.utcnow()

        #Cache
        self.prefixes = {}
        self.blacklist = {}
        self.guildblacklist = {}
        
        #self.premium_users = {} --soon
        self.premium_guilds = {}

        #Tracking
        self.message_stats = collections.Counter()
        self.command_stats = {}
        
        #Emojis
        self.emotes = EMOTES
        self.TEST_BOT_ID = TEST_BOT_ID

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

    async def on_shard_disconnect(self, shard_id: int):
        if self.user.id == self.TEST_BOT_ID:
            return 
        embed = discord.Embed(color=discord.Color.red(), description=f"{self.emotes['dnd']} Shard #{shard_id} has disconnected.")
        await self.status_logger.send(embed=embed)

    async def on_shard_ready(self, shard_id: int):
        if self.user.id == self.TEST_BOT_ID:
            return 
        embed = discord.Embed(color=discord.Color.green(), description=f"{self.emotes['online']} Shard #{shard_id} is ready.")
        await self.status_logger.send(embed=embed)

    async def on_shard_resumed(self, shard_id: int):
        if self.user.id == self.TEST_BOT_ID:
            return 
        embed = discord.Embed(color=discord.Color.green(), description=f"{self.emotes['online']} Shard #{shard_id} has resumed.")
        await self.status_logger.send(embed=embed)

    async def on_shard_connect(self, shard_id: int):
        if self.user.id == self.TEST_BOT_ID:
            return 
        embed = discord.Embed(color=discord.Color.orange(), description=f"{self.emotes['idle']} Shard #{shard_id} has connected.")
        await self.status_logger.send(embed=embed)

    async def add_to_guildblacklist(self, guild: int, *, reason: Optional[str] = None, ctx: MyContext, silent: bool = False):
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

    async def remove_from_guildblacklist(self, guild: int, *, ctx: MyContext):
        query = """
                DELETE FROM guild_blacklist WHERE guild = $1
                """
        status = await self.db.execute(query, guild)
        if status == "DELETE 0":
            await ctx.send(f"{self.emotes['cross']} **{guild}** is not currently blacklisted.")
        else:
            self.guildblacklist[guild] = False
            await ctx.send(f"{self.emotes['check']} Removed **{guild}** from the blacklist.")

    async def add_to_blacklist(self, ctx : MyContext, member : Union[discord.Member, discord.User], reason : str = None, *, silent : bool = False):
        if check_dev(self, member):
            if silent is True:
                return
            raise commands.BadArgument("I have been hard configured to not blacklist this user.")

        query = """
                INSERT INTO blacklist(member_id, is_blacklisted, moderator, added_time, reason) VALUES ($1, $2, $3, $4, $5) 
                """
        try:
            await self.db.execute(query, member.id, True, ctx.author, (discord.utils.utcnow().replace(tzinfo=None)), reason)
        except asyncpg.exceptions.UniqueViolationError:
            raise commands.BadArgument(f"This user is already blacklisted.")
        self.blacklist[member.id] = True

        if silent is False:
            await ctx.send(f"{self.check} Added **{member}** to the bot blacklist.")

    async def remove_from_blacklist(self, ctx : MyContext, member : Union[discord.Member, discord.User]):
        query = """
                DELETE FROM blacklist WHERE member_id = $1
                """
        status = await self.db.execute(query, member.id)
        if status == "DELETE 0":
            await ctx.send(f"{self.emotes['cross']} **{member}** is not currently blacklisted.")
        else:
            self.blacklist[member.id] = False
            await ctx.send(f"{self.check} Removed **{member}** from the bot blacklist.")

    async def setup_hook(self) -> None:    
        self.add_view(SupportView())
    
    async def on_ready(self):
        await self.wait_until_ready()

        print(
            f"-----\nLogged in as: {self.user.name} : {self.user.id}\n-----\nMy default prefix{'es are' if len(self.PRE) >= 2 else ' is'}: {', '.join(self.PRE) if len(self.PRE) >= 2 else self.PRE[0]}\n-----")

        user = self.get_user(BOT_OWNER_ID)
        data = read_json("restart")
        if data:
            channel = self.get_channel(data['channel'])
            message = channel.get_partial_message(data['id'])
            dt = datetime.datetime.fromtimestamp(data['now'])
            
            try:
                await message.edit(content=f'{self.emotes["check"]} Restart complete after {human_timedelta(dt, suffix=False)}')
            except discord.HTTPException:
                pass # eh it's fine

        self.owner = user


    def add_command(self, command):
        """Override `add_command` to make a default cooldown for every command"""

        super().add_command(command)
        command.cooldown_after_parsing = True

        #command.checks.append(Cooldown(2, 10, 2, 6, commands.BucketType.user))

    async def get_context(self, message, *, cls=MyContext):
        """Making our custom context"""

        return await super().get_context(message, cls=cls)


    async def process_commands(self, message):
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
         

    async def fetch_prefixes(self, message : discord.Message):
        return tuple([x['prefix'] for x in
            await self.db.fetch('SELECT prefix from prefixes WHERE guild_id = $1', message.guild.id)]) or self.PRE


    async def get_or_fetch_member(self, guild, member_id) -> Optional[discord.Member]:
        """Looks up a member in cache or fetches if not found.
        Parameters
        -----------
        guild: Guild
            The guild to look in.
        member_id: int
            The member ID to search for.
        Returns
        ---------
        Optional[Member]
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


bot.check = "<:mCheck:819254444197019669>"
bot.cross = "<:mCross:819254444217860116>"

@bot.listen('on_message')
async def mention_prefix(message: discord.Message):
    if re.fullmatch(rf"<@!?{bot.user.id}>", message.content):
        return await message.channel.send(f"\U0001f44b My prefixes here are: {', '.join(await bot.get_pre(bot, message, raw_prefix=True))}")
    
@bot.event
async def on_guild_join(guild: discord.Guild):
    if bot.guildblacklist.get(guild.id) is True:
        embed = discord.Embed(color=discord.Color.red())
        embed.description = f"I have automatically left this server due to it being blacklisted.\nPlease consider joining my [suppport server]({bot.support}) for more details."

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

        channel = bot.get_channel(BOT_LOGGER_CHANNEL)

        embed = discord.Embed(color=discord.Colour.green())
        embed.title = "New Guild"
        embed.description = f"\n__**Name:**__ {guild.name} (ID: {guild.id})"\
                            f"\n__**Human/Bots:**__ {len(humans)}/{len(bots)}"\
                            f"\n__**Owner:**__ {guild.owner} (ID: {guild.owner_id})"\
                            f"\n__**Added*:**__ {ts_now('F')} ({ts_now('R')})"
        count = discord.Embed(color=discord.Colour.purple(), description="Guilds count: **%s**" % len(bot.guilds))
        await channel.send(embeds=[embed, count])

@bot.event
async def on_guild_remove(guild: discord.Guild):
    humans = [hum for hum in guild.members if not hum.bot]
    bots = [bot for bot in guild.members if bot.bot]

    channel = bot.get_channel(BOT_LOGGER_CHANNEL)

    embed = discord.Embed(color=discord.Colour.red())
    embed.title = "Left Guild"
    embed.description = f"\n__**Name:**__ {guild.name} (ID: {guild.id})"\
                            f"\n__**Human/Bots:**__ {len(humans)}/{len(bots)}"\
                            f"\n__**Owner:**__ {guild.owner} (ID: {guild.owner_id})"
    count = discord.Embed(color=discord.Colour.purple(), description="Guilds count: **%s**" % len(bot.guilds))
    await channel.send(embeds=[embed, count])


async def main():
    async with aiohttp.ClientSession() as session:
        async with bot:
            bot.session = session
            bot.db = await create_db_pool(user, password, database, host, port)
            bot.loop.create_task(load_blacklist())
            bot.loop.create_task(load_guildblacklist())
            bot.loop.create_task(load_premiumguilds())
            bot.loop.create_task(execute_scripts())

            bot.error_logger = discord.Webhook.from_url(webhooks['error_handler'], session=bot.session)
            bot.status_logger = discord.Webhook.from_url(webhooks['status_logger'], session=bot.session)

            folders = ['hypixel', 'context_menu', 'giveaway_rewrite']

            bot.owner = bot.get_user(BOT_OWNER_ID)

            for file in os.listdir(cwd + "/cogs"):
                if file.endswith(".py") and not file.startswith("_"):
                    await bot.load_extension(f"cogs.{file[:-3]}")
                if file in folders:
                    await bot.load_extension(f"cogs.{file}")

            await bot.load_extension('jishaku') # jishaku

            await bot.start(token)


if __name__ == "__main__":
    # When running this file, if it is the 'main' file
    # I.E its not being imported from another python file run this
    asyncio.run(main())