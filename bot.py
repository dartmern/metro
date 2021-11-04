from typing import List, Optional, Tuple
import discord
from discord.ext import commands

from pathlib import Path
import os
import asyncpg
import aiohttp

from utils.useful import Cooldown
from utils.json_loader import read_json

from utils.context import MyContext

os.environ["JISHAKU_NO_UNDERSCORE"] = "True"

info_file = read_json('info')


p_database = info_file['postgres_database']
p_user = info_file['postgres_user']
p_password = info_file['postgres_password']
token = info_file['bot_token']

async def create_db_pool(database, user, password) -> asyncpg.Pool:
    return await asyncpg.create_pool(database=database,user=user,password=password)
    

      


class MetroBot(commands.AutoShardedBot):
    PRE: tuple = ('m.',)

    def __init__(self):
        intents = discord.Intents.all()
        intents.typing = False

        allowed_mentions = discord.AllowedMentions(
            roles=False, users=True, everyone=False, replied_user=False)
        

        super().__init__(
            intents=intents,
            command_prefix=self.get_pre,
            case_insensitive=True,
            allowed_mentions=allowed_mentions,
            owner_id=525843819850104842,
            chunk_guilds_at_startup=False,
            help_command=None,
            slash_commands=False,
            slash_command_guilds=[812143286457729055]
        )
        self.session = aiohttp.ClientSession()

        self.maintenance = False
        self.pres_views = False

        self.noprefix = False
        self.started = False

        self.db = asyncpg.Pool = self.loop.run_until_complete(create_db_pool(p_database, p_user, p_password))

        #Cache
        self.prefixes = {}

    async def on_ready(self):

        await bot.wait_until_ready()

        from cogs.support_views import RoleView, TesterButton, AllRoles

        if not self.persistent_views:
            self.add_view(TesterButton(self))
            self.add_view(RoleView(self))
            self.add_view(AllRoles(self))
            
            self.pres_views = True

        self.uptime = discord.utils.utcnow()

        print(
            f"-----\nLogged in as: {self.user.name} : {self.user.id}\n-----\nMy current default prefix is: m.\n-----")

        data = read_json('restart')
        
        channel = self.get_channel(data["channel_id"])
        message = channel.get_partial_message(data["message_id"])

        try:
            await message.edit(content=f'{self.check} Back online!')
        except:
            pass


    def add_command(self, command):
        """Override `add_command` to make a default cooldown for every command"""

        super().add_command(command)
        command.cooldown_after_parsing = True

        command.checks.append(Cooldown(1, 1.5, 1, 1, commands.BucketType.user))

    async def get_context(self, message, *, cls=MyContext):
        """Making our custom context"""

        return await super().get_context(message, cls=cls)


    async def process_commands(self, message):
        """Override process_commands to check, and call typing every invoke."""

        if message.author.bot:
            return

        ctx = await self.get_context(message)
        if message.author.id == 525843819850104842:
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
                    await self.db.fetch("SELECT prefix from prefixes WHERE guild_id = $1", message.guild.id)] or self.PRE
            self.prefixes[message.guild.id] = prefix
        
        if message.author.id == bot.owner_id and self.noprefix is True:
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
    bot.run(token)






