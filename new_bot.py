import discord
from discord.ext import commands


class Bot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def on_ready(self):
        print('Logged in as {}'.format(self.user))

bot = Bot(command_prefix='?',slash_commands=False,intents=discord.Intents.all(),slash_command_guilds=[812143286457729055])




@bot.command(
    slash_command=True
)
async def pp(ctx):
    await ctx.send('m')



@bot.command()
async def info(ctx):
    
    cmd = bot.get_command('pp')
    if cmd.slash_command is True:
        st='slash_command is true'
    else:
        st='slashcmd flase'

    if cmd.message_command is True:
        mc ='msg cmd true'
    else:
        mc = 'msg flas'

    await ctx.send(f'{st}\n{mc}\n{cmd.slash_command_guilds}')

bot.run('why u looking here')
