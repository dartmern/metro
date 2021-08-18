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



from utils.mongo import Document

def get_prefix(bot, message):

    if message.author.id == 525843819850104842:
        return ["m.", ""]

    else:
        return ["m."]


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

        if self.maintenance and ctx.valid:
            await message.channel.send(f"The bot is currently in maintenance. Please try again later.")
            return

        await self.invoke(ctx)



intents = discord.Intents.default()
intents.members = True
intents.reactions = True

mentions = discord.AllowedMentions(
    roles=False, users=True, everyone=False, replied_user=False
)

cwd = Path(__file__).parents[0]
cwd = str(cwd)
print(f"{cwd}\n-----")



bot_data = {
    "intents" : intents,
    "case_insensitive" :True,
    "allowed_mentions" : mentions,
    "help_command" : None,
    "owner_id" : 525843819850104842,
    "command_prefix" : get_prefix
}

bot = MetroBot(**bot_data)

bot.connection_url = 'mongodb+srv://dartmern:huV443naj@metro.zusoh.mongodb.net/metro?retryWrites=true&w=majority'
token = "Nzg4NTQzMTg0MDgyNjk4MjUy.X9lCEQ.-3IJ3mOcpgAI_OCSj_bDGE7brbs"


bot.check = "<:mCheck:819254444197019669>"
bot.cross = "<:mCross:819254444217860116>"



def read_json(filename):
    """
    A function to read a json file and return the data.
    Params:
     - filename (string) : The name of the file to open
    Returns:
     - data (dict) : A dict of the data in the file
    """
    cwd = get_path()
    with open(cwd+'/bot_config/'+filename+'.json', 'r') as file:
        data = json.load(file)
    return data


@bot.event
async def on_ready():
    print(
        f"-----\nLogged in as: {bot.user.name} : {bot.user.id}\n-----\nMy current default prefix is: m.\n-----")

    bot.mongo = motor.motor_asyncio.AsyncIOMotorClient(str(bot.connection_url))
    bot.db = bot.mongo["bot_config"]

    bot.info = Document(bot.db, 'info')

    data = await bot.info.find_by_id(bot.user.id)

    if not data is None:
        message = data['message']
        channel = data['channel']
        author = data['author']

        channel = bot.get_channel(int(channel))
        

        msg = channel.get_partial_message(message)
        author = msg.guild.get_member(author)

        await msg.edit(content=f"Restart successful.")

        print('Restarted by {}'.format(author))

        await bot.info.delete(bot.user.id)









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
    bot.run(token)






