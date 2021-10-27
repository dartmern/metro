import datetime
from typing import Optional
import discord
from discord import message
from discord.ext import commands


#3rd party libs
from pathlib import Path
import os
import asyncpg
import aiohttp
import asyncio
import time

#for eval cmd since i don't want to do it in a cog
import io
import contextlib
import textwrap
from utils.useful import Embed, clean_code, Pag, Cooldown
from traceback import format_exception

from utils.json_loader import read_json

os.environ["JISHAKU_NO_UNDERSCORE"] = "True"

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
        if message.author.id == 525843819850104842:
            return commands.when_mentioned_or('?','m.','')(bot, message)

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

    async def send(self, content : str = None, embed : discord.Embed = None, **kwargs):

        if content: 
            content=str(content)

            if self.bot.http.token in content:
                content = content.replace(self.bot.http.token, "[Token Hidden]")

        message = await super().send(content=content, embed=embed, **kwargs)
            
        return message

    async def st_send(self, content : str = None, embed : discord.Embed = None, hide : bool = False, **kwargs):

        if content: 
            content=str(content)

            if self.bot.http.token in content:
                content = content.replace(self.bot.http.token, "[Token Hidden]")
            
        try:
            message = await self.interaction.response.send_message(content=content, embed=embed, ephemeral=hide, **kwargs)
        except:
            message = await self.send(content=content, embed=embed, **kwargs)

        return message
        
        

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

        

        


class PresView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label='Check bot status',style=discord.ButtonStyle.green, custom_id='presistent_view:green')
    async def foo(self, button : discord.ui.Button, interaction : discord.Interaction):
        await interaction.response.send_message(f'The bot is currently online with **{round(self.bot.latency*1000)}ms** latency.\n\nIf there are problems, ask us in <#869693768582979715>',ephemeral=True)


    @discord.ui.button(label='Report an issue',style=discord.ButtonStyle.red, custom_id='presistent_view:red')
    async def boo(self, button : discord.ui.Button, interaction : discord.Interaction):

        await interaction.response.send_message(f'{self.bot.check} Messaged you a report ticket!',ephemeral=True)

        m = await interaction.user.send(f'Are you sure you want to make a ticket to report a bot issue?')
        await m.add_reaction(self.bot.check)
        await m.add_reaction(self.bot.cross)

        def check(reaction, user):

            if user == interaction.user and str(reaction.emoji) == self.bot.cross:
                raise commands.BadArgument('Canceled.')

            return user == interaction.user and str(reaction.emoji) == self.bot.check
        try:
            reaction, user = await self.bot.wait_for('reaction_add',check=check, timeout=60)
        except asyncio.TimeoutError:
            return await interaction.user.send('Timed out.') 

        else:

            await m.delete(silent=True)

            await interaction.user.send('Please type your report information.')
            def check(m):
                return m.author == interaction.user and m.guild is None

            try:
                m = await self.bot.wait_for('message',check=check, timeout=300)
            except asyncio.TimeoutError:
                return await interaction.user.send('Timed out.')

            await interaction.user.send('Thank you for your report! If needed you will be contacted through the bot.')

            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True),
            }
            category = self.bot.get_channel(897610105095323678)
            try:
                channel = await interaction.guild.create_text_channel(name=interaction.user, category=category,overwrites=overwrites)
            except:
                channel = await interaction.guild.create_text_channel(name=interaction.user.id, category=category,overwrites=overwrites)
            
            embed = Embed(title='New Report!',description=f'Author: `{interaction.user}` (ID: {interaction.user.id})\n\nReport Content: \n{str(m)}')
            await channel.send(embed=embed)
            return











class MetroBot(commands.AutoShardedBot):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.session = aiohttp.ClientSession()

        self.maintenance = False
        self.pres_views = False

        self.usage = {}

    async def on_ready(self):

        await bot.wait_until_ready()

        from cogs.support_views import RoleView, TesterButton, AllRoles, Verify

        if not self.persistent_views:
            self.add_view(TesterButton(self))
            self.add_view(RoleView(self))
            self.add_view(AllRoles(self))
            
            self.add_view(Verify(self))

            self.add_view(PresView(self))
            self.pres_views = True

        self.uptime = discord.utils.utcnow()

        print(
            f"-----\nLogged in as: {self.user.name} : {self.user.id}\n-----\nMy current default prefix is: m.\n-----")

        


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
    "slash_commands" : False,
    "slash_command_guilds" : [812143286457729055],
    'chunk_guilds_at_startup' : False
}

bot = MetroBot(**bot_data)
bot.maintenance = False






bot.check = "<:mCheck:819254444197019669>"
bot.cross = "<:mCross:819254444217860116>"






@bot.command(hidden=True)
async def statusview(ctx):
    """
    Start up the status views. (presviews)
    """
    await ctx.message.delete()
    await ctx.send('Click on the buttons below for status updates!',view=PresView(bot))




    









if __name__ == "__main__":
    # When running this file, if it is the 'main' file
    # I.E its not being imported from another python file run this


    for file in os.listdir(cwd + "/cogs"):
        if file.endswith(".py") and not file.startswith("_"):
            bot.load_extension(f"cogs.{file[:-3]}")

    bot.load_extension('jishaku')
    bot.loop.run_until_complete(create_db_pool(p_database, p_user, p_password))
    bot.run(token)






