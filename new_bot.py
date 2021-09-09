from typing import Optional, Union
import discord
from discord.ext import commands
from discord.mentions import AllowedMentions


class MyBot(commands.Bot):

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        print(f'---------------')




bot = MyBot(intents=discord.Intents.all(), command_prefix='!!',slash_commands=False)





@bot.command(slash_command=True, message_command=False, slash_command_guilds=[812143286457729055])
async def member(ctx, member : discord.Member):
    """
    Get member information.
    """
    await ctx.interaction.response.send_message(f'{member.mention} `{member}` (ID: {member.id})',ephemeral=True)


@bot.command(slash_command=True, message_command=False, slash_command_guilds=[812143286457729055]) 
async def dm(ctx, member : discord.User, message : str):
    """
    Send a message to a member/user.
    """

    try:
        await member.send(message, allowed_mentions=discord.AllowedMentions.none())
    except:
        return await ctx.interaction.response.send_message(f'Could not send a message to {member.mention} (ID: {member.id})',ephemeral=True)

    else:
        await ctx.interaction.response.send_message(f'The following was sent to {member.mention} `{member}` (ID: {member.id})\n> {message}',ephemeral=True)


@bot.command()
async def info(ctx):
    await ctx.send(embed=discord.Embed(description='Information'))


@bot.event
async def on_command_error(ctx, error):

    if isinstance(error, commands.errors.DisabledCommand):
        await ctx.send(str(error))

    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send_help(ctx.command)

    



    

bot.run('Nzg4NTQzMTg0MDgyNjk4MjUy.X9lCEQ.NK9Gbv_OsW9bZwyWIuvYLN7xjI0')