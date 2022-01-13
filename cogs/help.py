import itertools
from typing import Dict, List, Optional

from discord.ext.commands.help import HelpCommand
from bot import MetroBot
from utils.new_pages import SimplePages
import discord

import discord.ext

from discord.ext import commands, menus
import contextlib

import asyncio
import psutil
import time

from difflib import get_close_matches

from utils.custom_context import MyContext
from utils.remind_utils import UserFriendlyTime
from utils.useful import Embed, Cooldown, OldRoboPages, get_bot_uptime
from utils.converters import BotUserObject

"""
Hey, I highly discourage you taking code from this cog
mainly because of the bad practices I use that don't
always mean efficiency. Parts of it just isn't smart
but just me being lazy like the cog description and emojis
for the help command. If you have questions please ping
dartmern#7563 in my support server or in discord.py #playground.
"""

class SupportView(discord.ui.View):
    def __init__(self, ctx : MyContext):
        super().__init__()
        self.ctx = ctx
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.ctx.author.id:
            return True
        await interaction.response.send_message('This pagination menu cannot be controlled by you, sorry!', ephemeral=True)
        return False

    async def start(self, interaction: discord.Interaction):
        self.add_item(discord.ui.Button(label='Support Server', url='https://discord.gg/2ceTMZ9qJh'))

        embed = Embed()
        embed.colour = discord.Colour.orange()
        embed.description = '__**Are you sure you want to join my support server?**__'\
            f'\n Joining is completely at your own will. \nThis message is here to protect people from accidentally joining.'\
            f'\n You can kindly dismiss this message if you clicked by accident.'
        await interaction.response.send_message(embed=embed, ephemeral=True, view=self)

    async def start_normal(self):
        self.add_item(discord.ui.Button(label='Support Server', url='https://discord.gg/2ceTMZ9qJh'))

        embed = Embed()
        embed.colour = discord.Colour.orange()
        embed.description = '__**Are you sure you want to join my support server?**__'\
            f'\n Joining is completely at your own will. \nThis message is here to protect people from accidentally joining.'\
            f'\n You can kindly dismiss this message if you clicked by accident.'
        await self.ctx.send(embed=embed, ephemeral=True, view=self)

class VoteView(discord.ui.View):
    def __init__(self, ctx: MyContext, bot: discord.User, *, bot_instance: MetroBot):
        super().__init__(timeout=180)
        self.ctx = ctx
        self.bot: discord.User = bot  # This is a discord.User which is confirmed to be a *bot* 
                                    # THIS IT NOT AN INSTANCE OF METRO BUT CAN BE

        self.top_gg: str = None # both of these vars will get something in the start method
        self.discordbotlist: str = None

        self.bot_instance = bot_instance

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.ctx.author.id:
            return True
        await interaction.response.send_message('This pagination menu cannot be controlled by you, sorry!', ephemeral=True)
        return False

    async def start(self):
        """Start up the view."""

        if self.bot == self.bot_instance.user:
            self.top_gg = f"https://top.gg/bot/{self.bot.id}/vote"
            self.discordbotlist = f"https://discordbotlist.com/bots/{self.bot.id}"
        else:
            top_gg_response = await self.bot_instance.session.get(f"https://top.gg/bot/{self.bot.id}/vote")
            self.top_gg = f"https://top.gg/bot/{self.bot.id}/vote" if top_gg_response.status == 200 else "Not Found"

            discordbotlistresponse = await self.bot_instance.session.get(f"https://discordbotlist.com/bots/{self.bot.id}")
            self.discordbotlist = f"https://discordbotlist.com/bots/{self.bot.id}" if discordbotlistresponse.status == 200 else "Not Found"

            # Basically I send a request to see if they are on both bot lists but don't if it's my bot obv.

        embed = Embed()
        embed.set_author(name=self.bot, icon_url=self.bot.display_avatar.url)
        embed.description = f"**top.gg**: {self.top_gg}"\
            f"\n**discordbotlist.com**: {self.discordbotlist}"\
            f"\n\nThank you for voting it really helps grow and develop {self.bot.name}."\
            f"\n- You can click the button below to set a reminder to vote in 12 hours."

        await self.ctx.send(embed=embed, view=self)

    @discord.ui.button(label='Reminder', style=discord.ButtonStyle.green)
    async def foo(self, button: discord.ui.Button, interaction: discord.Interaction):
        button.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.defer()
        
        cmd = self.ctx.bot.get_command("reminder")
        if not cmd:
            return await interaction.response.send_message("This feature is currently not available.")
        await self.ctx.invoke(cmd, when=await UserFriendlyTime().convert(self.ctx, f'12 hours Vote for {self.bot.name}\n**top.gg**: <{self.top_gg}>\n**discordbotlist.com**: <{self.discordbotlist}>'))
        

class InviteView(discord.ui.View):
    def __init__(self, ctx : MyContext):
        super().__init__()
        self.ctx = ctx
        self.client = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.ctx.author.id:
            return True
        await interaction.response.send_message('This pagination menu cannot be controlled by you, sorry!', ephemeral=True)
        return False

    async def start_normal(self):
        embed = Embed()
        embed.colour = discord.Colour.blue()
        embed.description = "__**Choose a invite option below or press `Create custom permissions`**__"\
            f"\n\nIf you press `Create custom permissions` you are required to enter a vaild discord permissions integer."\
            f'\nYou can use [this calculator](https://discordapi.com/permissions.html) to find the permissions if you are unsure what to put.'
        
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.gray, label='None', url=discord.utils.oauth_url(self.ctx.bot.user.id, permissions=discord.Permissions(0))))
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.gray, label='Basic', url=discord.utils.oauth_url(self.ctx.bot.user.id, permissions=discord.Permissions(140663671873))))
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.blurple, label='Advanced', url=discord.utils.oauth_url(self.ctx.bot.user.id, permissions=discord.Permissions(140932115831))))
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.gray, label='Admin', url=discord.utils.oauth_url(self.ctx.bot.user.id, permissions=discord.Permissions(8))))
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.gray, label='All', url=discord.utils.oauth_url(self.ctx.bot.user.id, permissions=discord.Permissions(549755813887))))
        await self.ctx.send(embed=embed, view=self)

    async def start(self, interaction: Optional[discord.Interaction] = None, client: Optional[BotUserObject] = None):
        if interaction:
            _send = interaction.response.send_message
        else:
            _send = self.ctx.send

        client = client or self.ctx.bot.user
        self.client = client

        embed = Embed()
        embed.colour = discord.Colour.blue()
        embed.description = "__**Choose a invite option below or press `Create custom permissions`**__"\
            f'\n\nUse [this calculator](https://discordapi.com/permissions.html) to find the permission value if you are unsure what to put.'
        
        if client == self.ctx.bot.user:
            embed.set_author(name=client, icon_url=client.display_avatar.url)
        else:
            embed.set_author(name='Invite %s to your server' % client, icon_url=client.display_avatar.url)
            embed.set_footer(text='This is inviting %s to your server and not Metro. \nI am not responsible for any damages.' % client)
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.gray, label='None', url=discord.utils.oauth_url(client.id, permissions=discord.Permissions(0), scopes=('bot', 'applications.commands'))))
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.gray, label='Basic', url=discord.utils.oauth_url(client.id, permissions=discord.Permissions(140663671873), scopes=('bot', 'applications.commands'))))
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.blurple, label='Advanced', url=discord.utils.oauth_url(client.id, permissions=discord.Permissions(140932115831), scopes=('bot', 'applications.commands'))))
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.gray, label='Admin', url=discord.utils.oauth_url(client.id, permissions=discord.Permissions(8), scopes=('bot', 'applications.commands'))))
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.gray, label='All', url=discord.utils.oauth_url(client.id, permissions=discord.Permissions(-1), scopes=('bot', 'applications.commands'))))
        
        await _send(embed=embed, view=self)

    @discord.ui.button(row=1, label='Create custom permissions', style=discord.ButtonStyle.green)
    async def custom_perms(self, button: discord.ui.Button, interaction: discord.Interaction):
        
        await interaction.response.send_message(f"Please enter a permissions integer: ")
        
        def check(message : discord.Message) -> bool:
            return message.channel == self.ctx.channel and message.author == self.ctx.author

        try:
            message = await self.ctx.bot.wait_for("message", check=check, timeout=30)
        except asyncio.TimeoutError:
            return await interaction.followup.send("Timed out.")

        try:
            perms = int(message.content)
        except ValueError:
            embed = Embed(color=discord.Colour.red())
            embed.set_author(name='Invaild permission value.')
            embed.description = "Use [this calculator](https://discordapi.com/permissions.html) to find the permission value if you are unsure what to put."
            return await interaction.followup.send(embed=embed)
        
        em = Embed()
        em.description = f"Permission Integer: {message.content}"\
            f"\n Invite URL: {discord.utils.oauth_url(self.client.id, permissions=discord.Permissions(int(message.content)))}"
        await interaction.followup.send(embed=em)

    @discord.ui.button(emoji='🗑️', style=discord.ButtonStyle.red, row=1)
    async def stop_pages(self, button: discord.ui.Button, interaction: discord.Interaction):
        """
        Stop the pagination session. 
        Unless this pagination menu was invoked with a slash command
        """
        if self.ctx.interaction:
            return await interaction.response.send_message(f"This pagination menu was invoked with a slash command. \nPlease click *dismiss message* to quit.", ephemeral=True)

        await interaction.response.defer()
        await interaction.delete_original_message()
        self.stop()

class NeedHelp(discord.ui.View):
    def __init__(self, ctx: MyContext, old_view: discord.ui.View):
        super().__init__()
        self.ctx = ctx
        self.old_embed = None
        self.old_view = old_view # For the go home button

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.ctx.author.id:
            return True
        await interaction.response.send_message('This pagination menu cannot be controlled by you, sorry!', ephemeral=True)
        return False

    async def start(self, interaction: discord.Interaction):
        self.old_embed = interaction.message.embeds[0] # interaction.message.embeds[0] is just the home page embed
        
        embed = Embed(title="Argument Help Menu")
        embed.description = "__**Do not not include these brackets when running a command!**__"
        embed.add_field(
            name="How do I use this bot?",
            value="Reading the bot signature is pretty simple.",
        )

        embed.add_field(name="`<argument>`", value="Means that this argument is __**required**__", inline=False)
        embed.add_field(name="`[argument]`", value="Means that this argument is __**optional**__", inline=False)
        embed.add_field(name="`[argument='default']`",
                        value="Means that this argument is __**optional**__ and has a default value", inline=False)
        embed.add_field(name="`[argument]...` or `[argument...]`",
                        value="Means that this argument is __**optional**__ and can take __**multiple entries**__",
                        inline=False)
        embed.add_field(name="`<argument>...` or `<argument...>`",
                        value="Means that this argument is __**required**__ and can take __**multiple entries**__", inline=False)
        embed.add_field(name="`[X|Y|Z]`", value="Means that this argument can be __**either X, Y or Z**__",
                        inline=False)

        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label='Go Back', emoji='🏘️', style=discord.ButtonStyle.blurple)
    async def go_home_button(self, _, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=self.old_embed, view=self.old_view)
        self.stop()

    @discord.ui.button(emoji='🗑️', style=discord.ButtonStyle.red)
    async def stop_pages(self, button: discord.ui.Button, interaction: discord.Interaction):
        """
        Stop the pagination session. 
        """
        
        await interaction.response.defer()
        await interaction.delete_original_message()
        self.stop()

class NewHelpView(discord.ui.View):
    def __init__(self, ctx : MyContext, data : List, help_command):
        super().__init__(timeout=None)
        self.ctx : MyContext = ctx
        self.bot : MetroBot = ctx.bot #get typehinted bot and better to remember
        self.help_command : HelpCommand = help_command
        self.data : List = data #List[cog.name, Optional[cog.emoji]]

    def start_select(self) -> None:
        self.select_category : discord.ui.Select
        self.select_category.options = []

        self.select_category.add_option(emoji='🏘️', label='Home Page', value='home_page')
        self.select_category.add_option(emoji='<:bot:925107948789837844>', label='Bot Information', value='bot_information')
        self.select_category.add_option(emoji='📙', label='All commands', value='all_commands')

        for category, command in self.data:
            if category[0] == 'Jishaku':
                continue

            try:
                _emoji = category[2]
            except IndexError:
                _emoji = None
            self.select_category.add_option(emoji=_emoji, label=category[0].capitalize(), description=category[1])

    def category_embed(self, cog : commands.Cog) -> discord.Embed:

        to_join = []
        for command in cog.get_commands():
            if len(command.name) < 15:
                group_mark = '✅' if isinstance(command, commands.Group) else ''
                empty_space = 15 - len(command.name)
                if not group_mark == '':
                    empty_space = empty_space - 2
                short_doc = command.short_doc or "No help provided..."
                signature = f"`{command.name}{' '*empty_space}{group_mark}:` {short_doc if len(short_doc) < 58 else f'{short_doc[0:58]}...'}"
            else:
                group_mark = '\✅' if isinstance(command, commands.Group) else ''
                signature = f"`{command.name[0:12]}...{group_mark}` {short_doc if len(short_doc) < 58 else f'{short_doc[0:58]}...'}"
            to_join.append(signature)

        embed = Embed()
        embed.set_author(
            name=self.ctx.author.name + " | Help Menu",
            icon_url=self.ctx.author.display_avatar.url,
        )

        description = f"{cog.emoji if cog.emoji != '' else ''} __**{cog.qualified_name.capitalize()}**__ {cog.description if len(cog.description) < 57 else f'{cog.description[0:57]}...'}\n\n"
        description += (
            '\n'.join(to_join)
        )
        embed.description = description
        embed.set_footer(text='A command marked with a ✅ means it\'s a group command.')
        return embed

    async def bot_info_embed(self) -> discord.Embed:
        embed = Embed()
        embed.description = f'\n <:mdiscord:904157585266049104> [Support Server]({self.ctx.bot.support})'\
                f'\n <:inviteme:924868244525940807> [Invite Link]({self.ctx.bot.invite})'\
                f'\n <:github:744345792172654643> [Github]({self.ctx.bot.github})'\
                f'\n <:readthedocs:596577085036953611> [Documentation]({self.ctx.bot.docs})' 
        
        embed.set_author(name=f"Created by {self.ctx.bot.owner}", icon_url=self.ctx.bot.owner.display_avatar.url)
        embed.colour = self.ctx.guild.me.colour

        total_members = 0
        total_unique_members = len(self.ctx.bot.users)

        text = 0
        voice = 0
        total = 0
        guilds = 0

        for guild in self.ctx.bot.guilds:
            guild : discord.Guild

            guilds += 1
            if guild.unavailable:
                continue
            
            total_members += guild.member_count
            for channel in guild.channels:
                total += 1
                if isinstance(channel, discord.TextChannel):
                    text += 1
                if isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
                    voice += 1

        embed.add_field(name='Members', value=f'{total_members:,} total \n {total_unique_members:,} unique')
        embed.add_field(name='Channels', value=f'{total:,} total \n {text:,} text \n {voice:,} voice')

        memory_usage = psutil.Process().memory_full_info().uss / 1024 ** 2
        cpu_usage = psutil.cpu_percent()

        embed.add_field(name='Process', value=f'{memory_usage:.2f} MiB\n{cpu_usage:.2f}% CPU')

        embed.add_field(name='Guilds', value=guilds)

        count = await self.bot.db.fetchval('SELECT COUNT(*) as c FROM messages')

        embed.add_field(name='Messages', value=f"{count:,}")
        embed.add_field(name='Uptime', value=get_bot_uptime(self.bot, brief=True))
        return embed

    async def all_commands_embed(self) -> discord.Embed:
        embed = Embed(
            title=f'All commands [{len(self.bot.commands)}]'
        )
        
        embed.description = ', '.join([f"`{command}`" for command in self.bot.commands])
        embed.description += '\n\n__**This is a simplified list of my commands.\n Run `?help all` for a more detailed version**__'
        return embed

    def home_page_embed(self) -> discord.Embed:
        embed = Embed(
            description=
            f"\n**Total Commands:** {len(list(self.ctx.bot.walk_commands()))} | **Total Categories:** {len(self.ctx.bot.cogs)}"
        )
        embed.add_field(
            name='Getting Help',
            value=f'\n • Use `{self.ctx.clean_prefix}help <command | category>` for some help and examples on any command'\
                f'\n • Join my [support server]({self.ctx.bot.support}) for additional help'\
                f'\n • Use the select menu below to view the categories\' commands'\
                f'\n • Use `{self.ctx.clean_prefix}search <query>` to search for a particular command',
            inline=True
        )
        embed.add_field(
            name='Quick Links',
            value=f'\n <:mdiscord:904157585266049104> [Support Server]({self.ctx.bot.support})'\
                f'\n <:inviteme:924868244525940807> [Invite Link]({self.ctx.bot.invite})'\
                f'\n <:github:744345792172654643> [Github]({self.ctx.bot.github})'\
                f'\n <:readthedocs:596577085036953611> [Documentation]({self.ctx.bot.docs})' 
        )
        embed.set_author(
            name=self.ctx.author.name + " | Help Menu",
            icon_url=self.ctx.author.display_avatar.url,
        )
        embed.set_footer(text=f'Made by {self.bot.owner if self.bot.owner else "dartmern#7563"} with 💖 and discord.py')
        return embed

    @discord.ui.select(placeholder='Please select a category...', row=0)
    async def select_category(self, select : discord.ui.Select, interaction : discord.Interaction):

        if select.values[0] == 'home_page': 
            await interaction.response.edit_message(embed=self.home_page_embed(), view=self)
        elif select.values[0] == 'bot_information':
            await interaction.response.edit_message(embed=await self.bot_info_embed())
        elif select.values[0] == 'all_commands':
            await interaction.response.edit_message(embed=await self.all_commands_embed())
        else:
            cog = self.bot.get_cog(select.values[0].lower())
            if not cog:
                return await interaction.response.send_message(f"That category was somehow not found. Try using `{self.ctx.clean_prefix}help {select.values[0]}`", ephemeral=True)
            await interaction.response.edit_message(embed=self.category_embed(cog))

    @discord.ui.button(label='Need help', emoji='❓', style=discord.ButtonStyle.green)
    async def help_button(self, button : discord.ui.Button, interaction : discord.Interaction):
        await NeedHelp(self.ctx, self).start(interaction) 

    @discord.ui.button(label='Support Server', style=discord.ButtonStyle.blurple)
    async def support_url(self, button: discord.ui.Button, interaction: discord.Interaction):

        view = SupportView(self.ctx)
        await view.start(interaction)
        
    @discord.ui.button(label='Invite Me')
    async def invite_url(self, button: discord.ui.Button, interaction: discord.Interaction):
        
        view = InviteView(self.ctx)
        await view.start(interaction)

    @discord.ui.button(emoji='🗑️', style=discord.ButtonStyle.red)
    async def stop_pages(self, button: discord.ui.Button, interaction: discord.Interaction):
        """
        Stop the pagination session. 
        """

        await interaction.response.defer()
        await interaction.delete_original_message()
        self.stop()


    async def start(self) -> discord.Message:
        self.start_select()
        self.message = await self.ctx.send(embed=self.home_page_embed(), view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.ctx.author.id:
            return True
        await interaction.response.send_message('This pagination menu cannot be controlled by you, sorry!', ephemeral=True)
        return False


class View(discord.ui.View):
    def __init__(self, author):
        super().__init__(timeout=60)
        self.user = author


    async def on_timeout(self) -> None:
        self.foo.disabled = True
        try:
            await self.message.edit(view=self)
        except:
            pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.user == interaction.user:
            return True
        await interaction.response.send_message(f"Only {self.user} can use this menu. Run the command yourself to use it.",
                                                ephemeral=True)
        return False

    @discord.ui.button(emoji='<:mCross:819254444217860116>', style=discord.ButtonStyle.gray)
    async def foo(self, _, interaction: discord.Interaction) -> None:
        await interaction.message.delete()

    @classmethod
    async def start(cls, ctx, embed):
        self = cls(ctx.author)
        self.message = await ctx.channel.send(embed=embed, view=self)
        return self


class HelpSource(menus.ListPageSource):
    def __init__(self, data, *, prefix):
        super().__init__(data, per_page=10)
        self.prefix = prefix

    async def format_page(self, menu, commands):
        maximum = self.get_max_pages()

        embed = Embed()
        embed.title = f'All commands [{len(self.entries)}]'
        embed.colour = discord.Colour.green()

        desc = ""

        for command in commands:
            if len(command.name) < 15:
                empty_space = 15 - len(command.name)
                signature = f"\n `{command.name}{' '*empty_space}:` {command.short_doc if len(command.short_doc) < 58 else f'{command.short_doc[0:58]}...'}"
            else:
                signature = f"\n `{command.name[0:14]}...` {command.short_doc if len(command.short_doc) < 58 else f'{command.short_doc[0:58]}...'}"

            desc += signature

        embed.description = desc
        embed.set_footer(text=f'Type "{self.prefix}help [Command | Category]" for more information | [{menu.current_page + 1}/{maximum}]')

        return embed

class GroupHelpPageSource(menus.ListPageSource):
    def __init__(self, group, commands, *, prefix):
        super().__init__(entries=commands, per_page=4)
        self.group = group
        self.prefix = prefix
        self.title = f"{self.group.qualified_name.upper()}"
        self.description = self.group.description

    async def format_page(self, menu, commands):
        
        maximum = self.get_max_pages()
        if maximum > 1:
            try:
                title = (
                    f'{self.group.qualified_name.capitalize()} Module'
                    + f" | [{menu.current_page + 1}/{maximum}]"
                )
            except KeyError:
                title = self.title + f" | [{menu.current_page + 1}/{maximum}]"
        else:
            try:
                title = f'{self.group.qualified_name.capitalize()} Module'
            except KeyError:
                title = self.title

        embed = Embed(title=title, description=self.description)

        for command in commands:
            signature = f"{command.qualified_name} {command.signature}"
            embed.add_field(
                name=signature,
                value=command.short_doc or "No help provided...",
                inline=False,
            )

        embed.set_footer(
            text=f'Type "{self.prefix}help [Command | Module]" for more information.'
        )
        return embed


class HelpMenu(OldRoboPages):
    def __init__(self, source):
        super().__init__(source)

    @menus.button("\N{WHITE QUESTION MARK ORNAMENT}", position=menus.Last(5))
    async def show_bot_help(self, payload):
        """Shows how to use the bot"""

        embed = Embed(title="Argument Help Menu")

        entries = (
            ("<argument>", "This means the argument is __**required**__."),
            ("[argument]", "This means the argument is __**optional**__."),
            ("[A|B]", "This means that it can be __**either A or B**__."),
            (
                "[argument...]",
                "This means you can have multiple arguments.\n"
                "Now that you know the basics, it should be noted that...\n"
                "__**You do not type in the brackets!**__",
            ),
        )

        embed.add_field(
            name="How do I use this bot?",
            value="Reading the bot signature is pretty simple.",
        )

        for name, value in entries:
            embed.add_field(name=name, value=value, inline=False)

        embed.set_footer(
            text=f"We were on page {self.current_page + 1} before this message."
        )

        await self.message.edit(embed=embed)

        async def go_back_to_current_page():
            await asyncio.sleep(30.0)
            await self.show_page(self.current_page)

        self.bot.loop.create_task(go_back_to_current_page())


class ButtonMenuSrc(menus.ListPageSource):
    def __init__(self, group, commands, *, prefix, ctx : MyContext):
        super().__init__(entries=commands, per_page=9)
        self.group = group
        self.prefix = prefix
        self.description = self.group.help  
        self.extras = self.group.extras
        self.ctx = ctx
        

    async def format_page(self, menu, commands):

        maximum = self.get_max_pages()
        if maximum > 1:
            try:
                footer = (
                    f'Type "{self.prefix}help [Command | Module]" for more information'
                    + f" | [{menu.current_page + 1}/{maximum}]"
                )
            except KeyError:
                footer = f'Type "{self.prefix}help [Command | Module]" for more information' + f" | [{menu.current_page + 1}/{maximum}]"
        else:   
            footer = f'Type "{self.prefix}help [Command | Module] for more information' + " | [1/1]"

        if self.group.signature == '':
            title = f'`{self.group}`'
        else:
            title = f"`{self.group}` `{self.group.signature}`"

        embed = Embed(title=title, description=self.description)


        cooldown = discord.utils.find(lambda x: isinstance(x, Cooldown), self.group.checks) or Cooldown(1, 3, 1, 1,
                                                                                                     discord.ext.commands.BucketType.user)

        default_cooldown_per = cooldown.default_mapping._cooldown.per
        default_cooldown_rate = cooldown.default_mapping._cooldown.rate

        embed.add_field(
            name="Cooldowns",
            value=f"Default: `{default_cooldown_rate}` time(s) every `{default_cooldown_per}` seconds",
            inline=False
        )
        embed.add_field(
            name="Aliases",
            value=f"```{', '.join(self.group.aliases) or 'No aliases'}```",
            inline=False
        )

        sub_commands = []

        for command in commands:
            if len(command.name) < 15:
                empty_space = 15 - len(command.name)
                signature = f"`{command.name}{' '*empty_space}:` {command.short_doc if len(command.short_doc) < 58 else f'{command.short_doc[0:58]}...'}"
            else:
                signature = f"`{command.name[0:14]}...` {command.short_doc if len(command.short_doc) < 58 else f'{command.short_doc[0:58]}...'}"

            sub_commands.append(signature)
        
        embed.add_field(name='Subcommands',value='\n'.join(sub_commands),inline=False)

        if self.extras:
            try:
                examples = self.extras['examples'].replace("[p]", self.prefix)
                embed.add_field(
                    name='Examples/Usage',
                    value=examples,
                    inline=False
                )
            except KeyError:
                pass

            try:
                perms: Dict = self.extras['perms']
                clean_perms = [f"`{perm.replace('_', ' ').replace('guild', 'server').title()}`" for perm in perms.keys()]
                embed.add_field(
                    name='Permissions',
                    value=', '.join(clean_perms)
                )
            except KeyError:
                pass

        embed.set_footer(
            text=footer
        )
        return embed


class MetroHelp(commands.HelpCommand):

    @staticmethod
    def get_doc(command : commands.Command):
        _help = command.help or "This command has no description"
        return _help

    async def command_callback(self, ctx : MyContext, *, command : str =None):
        await self.prepare_help_command(ctx, command)
        bot = ctx.bot

        if command is None:
            mapping = self.get_bot_mapping()
            return await self.send_bot_help(mapping)

        # Check if it's a cog
        cog = bot.get_cog(command.lower())
        if cog is not None:
            return await self.send_cog_help(cog)

        maybe_coro = discord.utils.maybe_coroutine

        # If it's not a cog then it's a command.
        # Since we want to have detailed errors when someone
        # passes an invalid subcommand, we need to walk through
        # the command group chain ourselves.
        keys = command.split(' ')
        cmd = bot.all_commands.get(keys[0])
        if cmd is None:
            string = await maybe_coro(self.command_not_found, self.remove_mentions(keys[0]))
            return await self.send_error_message(ctx, string)

        for key in keys[1:]:
            try:
                found = cmd.all_commands.get(key)
            except AttributeError:
                string = await maybe_coro(self.subcommand_not_found, cmd, self.remove_mentions(key))
                return await self.send_error_message(ctx, string)
            else:
                if found is None:
                    string = await maybe_coro(self.subcommand_not_found, cmd, self.remove_mentions(key))
                    return await self.send_error_message(ctx, string)
                cmd = found

        if isinstance(cmd, commands.Group):
            return await self.send_group_help(cmd)
        else:
            return await self.send_command_help(cmd)

    async def get_command_help(self, command : commands.Command) -> Embed:

        command_extras = command.extras
        # Base
        if command.signature == "":
            em = Embed(
                title=f"`{command.qualified_name}`",
                description=self.get_doc(command)
            )
        else:
            em = Embed(
                title=f"`{command.qualified_name}` `{command.signature}`",
                description=self.get_doc(command)
            )

        # Cooldowns
        cooldown = discord.utils.find(lambda x: isinstance(x, Cooldown), command.checks) or Cooldown(1, 3, 1, 1,
                                                                                                     commands.BucketType.user)

        default_cooldown_per = cooldown.default_mapping._cooldown.per
        default_cooldown_rate = cooldown.default_mapping._cooldown.rate

        em.add_field(
            name="Cooldowns",
            value=f"Default: `{default_cooldown_rate}` time(s) every `{default_cooldown_per}` seconds",     
            inline=False
        )

        # Aliases
        em.add_field(
            name="Aliases",
            value=f"```{', '.join(command.aliases) or 'No aliases'}```",
            inline=False
        )
        if command_extras:
            try:
                examples = command_extras['examples'].replace("[p]", self.context.clean_prefix)
                em.add_field(
                    name='Examples/Usage',
                    value=examples,
                    inline=False
                )
            except KeyError:
                pass

            try:
                perms: Dict = command_extras['perms']
                clean_perms = [f"`{perm.replace('_', ' ').replace('guild', 'server').title()}`" for perm in perms.keys()]
                em.add_field(
                    name='Permissions',
                    value=', '.join(clean_perms),
                    inline=False
                )
            except KeyError:
                pass



        if not isinstance(command, commands.Group):
            return em

        group = await self.filter_commands(command.walk_commands())

        all_subs = [
            f"`{sub.name}` {f'`{sub.signature}`' if sub.signature else ''} {sub.short_doc}" for sub in group
        ]   

        if len(all_subs) == 0:
            em.add_field(name='No Subcommands',value="\u200b",inline=False)
            return em

        em.add_field(
            name="Subcommands",
            value="\n".join(all_subs)
        )

        return em
        

    async def handle_help(self, command, old_ctx : MyContext = None):
        with contextlib.suppress(commands.CommandError):
            if not await command.can_run(old_ctx):
                raise commands.CommandError
            if old_ctx.interaction:
                return await old_ctx.interaction.response.send_message(embed=self.get_command_help(command),ephemeral=True)
            else:
                return await old_ctx.send(embed=await self.get_command_help(command, old_ctx),view=View(old_ctx))
        raise commands.BadArgument("You do not have the permissions to view this command's help.")


    async def send_bot_help(self, mapping):

        #This is a very bad implantation of the base help command but it works

        def get_category(command, *, no_category='No Category'):
            cog = command.cog
            if cog is None: return [no_category, 'Commands that do not have a category.']
            try:
                to_return = [cog.qualified_name, cog.description.split('\n')[0], cog.emoji]
                if cog.emoji == '':
                    return [cog.qualified_name, cog.description.split('\n')[0]]
                else:
                    return to_return
            except AttributeError:
                return [cog.qualified_name]
            
        filtered = await self.filter_commands(self.context.bot.commands, sort=True, key=get_category)
        to_iterate = itertools.groupby(filtered, key=get_category)

        view = NewHelpView(self.context, to_iterate, self)
        await view.start()

    
    async def send_command_help(self, command):
        return await self.context.send(embed=await self.get_command_help(command),view=View(self.context.author), hide=True)

    async def send_group_help(self, group):
        
        entries = list(group.commands)
        
        if int(len(group.commands)) == 0 or len(entries) == 0:
            return await self.context.send(embed=await self.get_command_help(group),view=View(self.context.author), hide=True)

        menu = SimplePages(ButtonMenuSrc(group, entries, prefix=self.context.clean_prefix, ctx=self.context),ctx=self.context)
        await menu.start()
        

    async def send_cog_help(self, cog: commands.Cog):
        to_join = []
        for command in cog.get_commands():
            if len(command.name) < 15:
                group_mark = '✅' if isinstance(command, commands.Group) else ''
                empty_space = 15 - len(command.name)
                if not group_mark == '':
                    empty_space = empty_space - 2
                short_doc = command.short_doc or "No help provided..."
                signature = f"`{command.name}{' '*empty_space}{group_mark}:` {short_doc if len(short_doc) < 58 else f'{short_doc[0:58]}...'}"
            else:
                group_mark = '\✅' if isinstance(command, commands.Group) else ''
                signature = f"`{command.name[0:12]}...{group_mark}` {short_doc if len(short_doc) < 58 else f'{short_doc[0:58]}...'}"
            to_join.append(signature)

        embed = Embed()
        embed.set_author(
            name=self.context.author.name + " | Help Menu",
            icon_url=self.context.author.display_avatar.url,
        )

        description = f" __**{cog.qualified_name.capitalize()}**__ \n"
        description += (
            '\n'.join(to_join)
        )
        embed.description = description
        embed.set_footer(text='A command marked with a ✅ means it\'s a group command.')
        
        return await self.context.send(embed=embed)

    async def command_not_found(self, command):
        if command.lower() == "all":
            commands = await self.filter_commands(self.context.bot.commands)
            
            menu = SimplePages(source=HelpSource(tuple(commands), prefix=self.context.clean_prefix), ctx=self.context)
            return await menu.start()

        return f"No command/category called `{command}` found."

    async def send_error_message(self, ctx, error):
        if error is None:
            return
        return await ctx.send(error, hide=True)
       

class meta(commands.Cog, description='Get bot stats and information.'):
    def __init__(self, bot):

        attrs = {
            'name' : 'help',
            'description' : 'Show bot help or help for a command',
            'aliases' : ['h','command'],
            'slash_command' : True,
            'message_command' : True,
            'extras' : {'examples' : "[p]help ban\n[p]help config enable\n[p]help invite"}
        }

        self.bot = bot
        self.old_help_command = bot.help_command
        bot.help_command = MetroHelp(command_attrs=attrs)
        bot.help_command.cog = self

    @property
    def emoji(self) -> str:
        return 'ℹ️'


    @commands.command(slash_command=True)
    @commands.bot_has_permissions(send_messages=True)
    async def uptime(self, ctx):
        """Get the bot's uptime."""

        await ctx.send(f'I have an uptime of: **{get_bot_uptime(self.bot, brief=False)}**',hide=True)


    @commands.command()
    @commands.check(Cooldown(1, 5, 1, 3, commands.BucketType.member))
    async def ping(self, ctx):
        """Show the bot's latency in milliseconds.
        Useful to see if the bot is lagging out."""

        start = time.perf_counter()
        message = await ctx.send('Pinging...')
        end = time.perf_counter()

        typing_ping = (end - start) * 1000

        start = time.perf_counter()
        await self.bot.db.execute('SELECT 1')
        end = time.perf_counter()

        database_ping = (end - start) * 1000

        typing_emoji = self.bot.get_emoji(904156199967158293)

        if ctx.guild is None:
            mess = "`Note that my messages are on shard 0 so it isn't guaranteed your server is online.`" 
            shard = self.bot.get_shard(0)
        else:
            mess = ""
            shard = self.bot.get_shard(ctx.guild.shard_id)

        await message.edit(
            content=f'{typing_emoji} **Typing:** | {round(typing_ping, 1)} ms'
                    f'\n<:msql:904157158608867409> **Database:** | {round(database_ping, 1)} ms'
                    f'\n<:mdiscord:904157585266049104> **Websocket:** | {round(self.bot.latency*1000)} ms'
                    f'\n:infinity: **Shard Latency:** | {round(shard.latency *1000)} ms \n{mess}')


    @commands.command(name='invite',slash_command=True)
    @commands.bot_has_permissions(send_messages=True)
    async def invite(self, ctx: MyContext, *, bot: discord.User = None):
        """Get invite links for a bot."""
        bot = bot or self.bot.user
        if not bot.bot:
            raise commands.BadArgument("This is not a bot.")
        await InviteView(ctx).start(None, bot)

    @commands.command()
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def support(self, ctx: MyContext):
        await SupportView(ctx).start_normal()

    @commands.command(name='search', aliases=['commandsearch'])
    async def search(self, ctx: MyContext, *, search_query: str):
        """
        Search through my commands and find that hidden command.
        """

        commands = [str(command) for command in self.bot.walk_commands()]
         
        matches = get_close_matches(search_query, commands)

        embed = Embed()

        if len(matches) > 0:
            to_send = []
            for command in matches:
                command = self.bot.get_command(command)
                if len(command.name) < 15:
                    empty_space = 15 - len(command.name)
                    signature = f"`{command.qualified_name}{' '*empty_space}:` {command.short_doc if len(command.short_doc) < 58 else f'{command.short_doc[0:58]}...'}"
                else:
                    signature = f"`{command.qualified_name[0:14]}...` {command.short_doc if len(command.short_doc) < 58 else f'{command.short_doc[0:58]}...'}"
                to_send.append(signature)

            embed.colour = discord.Colour.green()
            embed.description = "\n".join(to_send)
            embed.set_footer(text=f'{len(matches)} matches.')

            await ctx.send(embed=embed)
        else:
            await ctx.send("No matches were found. Try again with a different query.")
            
    @commands.command()
    async def vote(self, ctx: MyContext, *, bot: Optional[discord.User]):
        """Get vote links for the bot."""
        bot = bot or self.bot.user
        if not bot.bot:
            raise commands.BadArgument("This is not a bot.")
        view = VoteView(ctx, bot, bot_instance=self.bot)
        await view.start()

    @commands.command(name='bot-info', aliases=['botinfo', 'bi', 'info'])
    async def _bot_info(self, ctx: MyContext):
        """Get all the information about me."""
        embed = await NewHelpView(ctx, {}, ctx.bot.help_command).bot_info_embed()
        await ctx.reply(embed=embed)

    @commands.command()
    async def privacy(self, ctx: MyContext):
        """Privacy for the bot."""

        desc = ""

        desc += (
            """
            - By interacting with Metro which will be refered to as "bot", 
            you agree that message data (the message id, message author, 
            the time the message was sent) WILL be recorded but 
            message CONTENT (the content of the messages sent, this includes 
            attachments, embeds and the actual content) will NOT be recorded.
            Your user id (to identify you) is another piece of information
            will be recorded in my database. This data is encrypted in a 
            secure database that only developers have access to. The bot 
            collects this data for moderation purpose and to track stats 
            with the tracking module which tracks message count. If
            you do not consent to having your data tracking please join the
            bot's support server. The bot does not collect data like presences, 
            statuses, about me, connections about you.
            """
        )
        desc +=(
            """
            - By inviting Metro to your server you agree that your guild's 
            messages are recorded (except message content) for stat purposes. 
            You can view this in the tracking module (message count). The bot 
            will not store but access guild member count and channel count for 
            bot stats which you may view on my help command.
            """
        )
        desc += (
            """
            \nIf you have any privacy concerns you may view the source code
            for **any** command with the `source` command. You can view
            the entire github repository by clicking [here](https://github.com/dartmern/metro) <:github:744345792172654643>
            """
        )
        desc += (
            """
            \nAny concerns? Join my [support server](https://discord.gg/2ceTMZ9qJh) if you have any concerns or issues.
            """
        )
        desc += (
            f"""
            \nYou can now optout of having your messages tracked by running `{ctx.clean_prefix}optout`
            Add the `--remove` flag to remove previously stored data.
            """
        )
        embed = discord.Embed(color=ctx.color)
        embed.description = desc
        await ctx.reply(embed=embed)
        



def setup(bot):
    bot.add_cog(meta(bot))