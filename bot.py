import datetime
from typing import Optional
import discord
from discord.ext import commands


#3rd party libs
from pathlib import Path
import os
import asyncpg
import aiohttp
import motor.motor_asyncio

#for eval cmd since i don't want to do it in a cog
import io
import contextlib
import textwrap
from utils.useful import clean_code, Pag, Cooldown, ts_now
from traceback import format_exception

from utils.json_loader import read_json, write_json

info_file = read_json('info')


p_database = info_file['postgres_database']
p_user = info_file['postgres_user']
p_password = info_file['postgres_password']
token = info_file['bot_token']

async def create_db_pool(database, user, password):
    bot.db = await asyncpg.create_pool(database=database,user=user,password=password)
    print('Connected to database.')

async def get_prefix(bot, message):


    if not message.guild:
        return commands.when_mentioned_or('?','m.')(bot, message)

    prefix = await bot.db.fetch('SELECT prefix FROM prefixes WHERE "guild_id" = $1', message.guild.id)
    if len(prefix) == 0:
        await bot.db.execute('INSERT into prefixes ("guild_id", prefix) VALUES ($1, $2)', message.guild.id, 'm.')
        prefix = ['m.']

    else:
        prefix = prefix[0].get('prefix')

    if message.author.id == 525843819850104842:
        
        return commands.when_mentioned_or(prefix, '')(bot, message)
    return commands.when_mentioned_or(prefix)(bot, message)

class ConfirmationView(discord.ui.View):
    def __init__(self, *, timeout: float, author_id: int, ctx, delete_after: bool) -> None:
        super().__init__(timeout=timeout)
        self.value: Optional[bool] = None
        self.delete_after: bool = delete_after
        self.author_id: int = author_id
        self.ctx = ctx
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id == self.author_id:
            return True
        else:
            await interaction.response.send_message('This confirmation dialog is not for you.', ephemeral=True)
            return False

    async def on_timeout(self) -> None:
        self.confirm.disabled = True
        self.cancel.disabled = True
        self.value = None
        await self.message.edit(view=self)

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green)
    async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.value = True
        await interaction.response.defer()
        if self.delete_after:
            await interaction.delete_original_message()
        self.stop()

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.red)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.value = False
        await interaction.response.defer()
        if self.delete_after:
            await interaction.delete_original_message()
        self.stop()

class MyContext(commands.Context):

    async def check(self):
        emoji = self.bot.get_emoji(819254444197019669)

        try:
            await self.message.add_reaction(emoji)
        except discord.HTTPException:
            pass

    async def cross(self):
        emoji = self.bot.get_emoji(819254444217860116)

        try:
            await self.message.add_reaction(emoji)
        except discord.HTTPException:
            pass

    async def confirm(
        self,
        message : str,
        *,
        timeout : float = 60.0,
        delete_after : bool = True,
        author_id : Optional[int] = None

    ) -> Optional[bool]:

        author_id = author_id or self.author.id

        view = ConfirmationView(
            timeout=timeout,
            delete_after=delete_after,
            ctx=self,
            author_id=author_id

        )
        view.message = await self.send(message, view=view)
        await view.wait()
        return view.value

        

        










class MetroBot(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.session = aiohttp.ClientSession()

        self.maintenance = False

    def add_command(self, command):
        """Override `add_command` to make a default cooldown for every command"""

        super().add_command(command)
        command.cooldown_after_parsing = True

        command.checks.append(Cooldown(1, 3, 1, 1, commands.BucketType.user))

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

        if bot.maintenance and ctx.valid:
            await message.channel.send(f"The bot is currently in maintenance. Please try again later.")
            return

        await self.invoke(ctx)



intents = discord.Intents.all()


mentions = discord.AllowedMentions(
    roles=False, users=True, everyone=False, replied_user=False
)

cwd = Path(__file__).parents[0]
cwd = str(cwd)
print(f"{cwd}\n-----")



bot_data = {
    "intents" : intents,
    "case_insensitive" : True,
    "allowed_mentions" : mentions,
    "help_command" : None,
    "owner_id" : 525843819850104842,
    "command_prefix" : get_prefix,
    "slash_commands" : False
}

bot = MetroBot(**bot_data)
bot.maintenance = False






bot.check = "<:mCheck:819254444197019669>"
bot.cross = "<:mCross:819254444217860116>"






@bot.event
async def on_ready():
    print(
        f"-----\nLogged in as: {bot.user.name} : {bot.user.id}\n-----\nMy current default prefix is: m.\n-----")

        
       





@bot.command(name="eval", aliases=["exec","e"])
@commands.is_owner()
async def _eval(ctx, *, code):
    code = clean_code(code)

    local_variables = {
        "discord": discord,
        "commands": commands,
        "bot": bot,
        "ctx": ctx,
        "channel": ctx.channel,
        "author": ctx.author,
        "guild": ctx.guild,
        "message": ctx.message
    }

    stdout = io.StringIO()

    try:
        with contextlib.redirect_stdout(stdout):
            exec(
                f"async def func():\n{textwrap.indent(code, '    ')}", local_variables,
            )

            obj = await local_variables["func"]()
            result = f"{stdout.getvalue()}\n-- {obj}\n"
    except Exception as e:
        result = "".join(format_exception(e, e, e.__traceback__))

    pager = Pag(
        timeout=100,
        entries=[result[i: i + 2000] for i in range(0, len(result), 2000)],
        length=1,
        prefix="```py\n",
        suffix="```"
    )

    await pager.start(ctx)




if __name__ == "__main__":
    # When running this file, if it is the 'main' file
    # I.E its not being imported from another python file run this


    for file in os.listdir(cwd + "/cogs"):
        if file.endswith(".py") and not file.startswith("_"):
            bot.load_extension(f"cogs.{file[:-3]}")

    bot.load_extension('jishaku')
    bot.loop.run_until_complete(create_db_pool(p_database, p_user, p_password))
    bot.run(token)






