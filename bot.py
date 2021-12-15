import collections
from typing import List, Optional, Tuple, Union
import discord
from discord.ext import commands

from pathlib import Path
import os
import asyncpg
from discord.ext.commands.core import check
from discord.ext.commands.flags import F
import mystbin
import aiohttp
import logging
from utils.checks import check_dev

from utils.useful import Cooldown
from utils.json_loader import read_json
from utils.errors import UserBlacklisted
from utils.custom_context import MyContext

os.environ["JISHAKU_NO_UNDERSCORE"] = "True"

info_file = read_json('info')


logging.basicConfig(level=logging.INFO)
#logger = logging.getLogger('discord')
#logger.setLevel(logging.DEBUG)
#handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
#handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
#logger.addHandler(handler)

p_database = info_file['postgres_database']
p_user = info_file['postgres_user']
p_password = info_file['postgres_password']
token = info_file['bot_token']

async def create_db_pool(database, user, password) -> asyncpg.Pool:
    print("------")
    print("Creating database connection...")
    print('------')
    print(f"Database: {len(p_database) * '*'}")
    print(f"User: {len(p_user) * '*'}")
    print(f"Password: {len(p_password) * '*'}")
    print('------')
    return await asyncpg.create_pool(database=database,user=user,password=password)
    

async def load_blacklist():
    await bot.wait_until_ready()

    query = """
            SELECT member_id FROM blacklist WHERE is_blacklisted = True
            """

    records = await bot.db.fetch(query)
    if records:
        for record in records:
            bot.blacklist[record["member_id"]] = True


class MetroBot(commands.AutoShardedBot):
#class MetroBot(commands.Bot):
    PRE: tuple = ('m.', '?', 'm?')

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
            #owner_id=525843819850104842,
            owner_ids=[525843819850104842],
            #chunk_guilds_at_startup=False,
            help_command=None,
            slash_commands=True,
            slash_command_guilds=[812143286457729055, 917580286898888715],
            strip_after_prefix=True,
            #shard_count=10,
            max_messages=5000
        )
        self.session = aiohttp.ClientSession()
        self.mystbin_client = mystbin.Client()

        self.add_check(self.user_blacklisted)

        self.maintenance = False
        self.pres_views = False

        self.invite = 'https://discord.com/api/oauth2/authorize?client_id=788543184082698252&permissions=0&scope=applications.commands%20bot'
        self.support = 'https://discord.gg/2ceTMZ9qJh'
        self.donate = 'https://www.patreon.com/metrodiscordbot'

        self.noprefix = False
        self.started = False

        self.owner = 'dartmern#7563'
        #This is just a temp fix for something. I'll make this a user object later

        self.db = asyncpg.Pool = self.loop.run_until_complete(create_db_pool(p_database, p_user, p_password))

        #Cache
        self.prefixes = {}
        self.blacklist = {}

        #Tracking
        self.message_stats = collections.Counter()


    async def add_to_blacklist(self, ctx : MyContext, member : Union[discord.Member, discord.User], reason : str = None, *, silent : bool = False):
        if check_dev(self, member):
            raise commands.BadArgument("I have been hard configured to not blacklist this user.")

        query = """
                INSERT INTO blacklist(member_id, is_blacklisted, reason) VALUES ($1, $2, $3) 
                """
        try:
            await self.db.execute(query, member.id, True, reason)
        except asyncpg.exceptions.UniqueViolationError:
            raise commands.BadArgument(f"This user is already blacklisted.")
        self.blacklist[member.id] = True

        if silent is False:
            await ctx.send(f"{self.check} Added **{member}** to the bot blacklist.")

    async def remove_from_blacklist(self, ctx : MyContext, member : Union[discord.Member, discord.User]):
        query = """
                DELETE FROM blacklist WHERE member_id = $1
                """
        await self.db.execute(query, member.id)
        self.blacklist[member.id] = False
        await ctx.send(f"{self.check} Removed **{member}** from the bot blacklist.")


    async def on_ready(self):
        await self.wait_until_ready()

        from cogs.support_views import RoleView, TesterButton, AllRoles

        if not self.persistent_views:
            self.add_view(TesterButton(self))
            self.add_view(RoleView(self))
            self.add_view(AllRoles(self))
            
            self.pres_views = True

        self.uptime = discord.utils.utcnow()

        print(
            f"-----\nLogged in as: {self.user.name} : {self.user.id}\n-----\nMy default prefix{'es are' if len(self.PRE) >= 2 else ' is'}: {', '.join(self.PRE) if len(self.PRE) >= 2 else self.PRE[0]}\n-----")

        data = read_json('restart')
        user = self.get_user(525843819850104842)

        if data['dms']:
            await user.send("Restart complete!")
        else:
            channel = self.get_channel(data["channel_id"])
            if not channel is None:
                message = channel.get_partial_message(data["message_id"])
                try:
                    await message.edit(content=f'{self.check} Back online!')
                except discord.NotFound:
                    await user.send("Restart complete!")
            else:
                pass
        self.owner = user


    def add_command(self, command):
        """Override `add_command` to make a default cooldown for every command"""

        super().add_command(command)
        command.cooldown_after_parsing = True

        command.checks.append(Cooldown(3, 7, 4, 7, commands.BucketType.user))

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


    async def get_or_fetch_member(self, guild, member_id):
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


if __name__ == "__main__":
    # When running this file, if it is the 'main' file
    # I.E its not being imported from another python file run this


    for file in os.listdir(cwd + "/cogs"):
        if file.endswith(".py") and not file.startswith("_"):
            bot.load_extension(f"cogs.{file[:-3]}")

    bot.load_extension('jishaku')
    bot.loop.create_task(load_blacklist())
    bot.run(token)






