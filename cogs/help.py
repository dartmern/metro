import inspect
import itertools
import os
from typing import Dict, List, Optional

from discord.ext.commands.help import HelpCommand
from bot import MetroBot
from cogs.utility import StopView
from utils.constants import TESTING_GUILD
from utils.embeds import create_embed
from utils.new_pages import SimplePages
import discord
import pathlib

import discord.ext

from discord.ext import commands, menus
import contextlib

import asyncio
import psutil
import speedtest
import time

from difflib import get_close_matches

from utils.custom_context import MyContext
from utils.remind_utils import UserFriendlyTime
from utils.useful import Embed, Cooldown, OldRoboPages, get_bot_uptime
from utils.converters import BotUserObject, DiscordCommand

"""
Hey, I highly discourage you taking code from this cog
mainly because of the bad practices I use that don't
always mean efficiency. Parts of it just isn't smart
but just me being lazy like the cog description and emojis
for the help command. If you have questions please ping
dartmern#7563 in my support server or in discord.py #playground.
"""

class BotInfoExtended(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)
        self.embed = None

    @discord.ui.button(label='Linecount')
    async def linecount_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        if self.embed:
            return await interaction.response.send_message(embed=self.embed, ephemeral=True)

        await interaction.response.defer()

        embed = discord.Embed(color=discord.Color.yellow())

        p = pathlib.Path('./')
        cm = cr = fn = cl = ls = fc = 0
        for f in p.rglob('*.py'):
            if str(f).startswith("venv"):
                continue
            fc += 1
            with f.open(encoding='utf8',errors='ignore') as of:
                for l in of.readlines():
                    l = l.strip()
                    if l.startswith('class'):
                        cl += 1
                    if l.startswith('def'):
                        fn += 1
                    if l.startswith('async def'):
                        cr += 1
                    if '#' in l:
                        cm += 1
                    ls += 1
        embed.description = f"\nFiles: {fc:,}"\
            f"\nLines: {ls:,}"\
            f"\nClasses: {cl:,}"\
            f"\nFunctions: {fn:,}"\
            f"\nCoroutines: {cr:,}"\
            f"\nComments: {cm:,}"

        self.embed = embed        

        await interaction.followup.send(embed=embed, ephemeral=True)

class SupportView(discord.ui.View):
    def __init__(self, ctx : MyContext):
        super().__init__(timeout=300)
        self.ctx = ctx
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.ctx.author.id:
            return True
        await interaction.response.send_message('This pagination menu cannot be controlled by you, sorry!', ephemeral=True)
        return False

    async def start(self, interaction: Optional[discord.Interaction] = None):
        self.add_item(discord.ui.Button(label='Support Server', url='https://discord.gg/2ceTMZ9qJh'))

        embed = Embed()
        embed.colour = discord.Colour.orange()
        embed.description = '__**Are you sure you want to join my support server?**__'\
            f'\n Joining is completely at your own will. \nThis message is here to protect people from accidentally joining.'\
            f'\n You can kindly dismiss this message if you clicked by accident.'\
            f'\n\n If you have an issue with joining you can always send the bot owner an email. (`metrobot.receiving@gmail.com`)'
        if interaction:
            await interaction.response.send_message(embed=embed, ephemeral=True, view=self)
        else:
            await self.ctx.send(embed=embed, view=self)

class VoteView(discord.ui.View):
    def __init__(self, ctx: MyContext, bot: discord.User, *, bot_instance: MetroBot):
        super().__init__(timeout=300)
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
    async def foo(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.defer()
        
        cmd = self.ctx.bot.get_command("reminder")
        if not cmd:
            return await interaction.response.send_message("This feature is currently not available.")
        await self.ctx.invoke(cmd, when=await UserFriendlyTime().convert(self.ctx, f'12 hours Vote for {self.bot.name}\n**top.gg**: <{self.top_gg}>\n**discordbotlist.com**: <{self.discordbotlist}>'))
        

class ChoosePermissionsSelect(discord.ui.Select):
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

class WithAppCommandScopeView(discord.ui.View):
    def __init__(self, application: discord.Member, *, permissions: discord.Permissions, interaction: discord.Interaction):
        super().__init__(timeout=300)

        self.application = application
        self.permissions = permissions
        self.old_interaction = interaction
        self.with_app_scope = True
        
    @discord.ui.button(label='Remove app command scope', emoji='<:mCross:819254444217860116>', style=discord.ButtonStyle.red)
    async def applications_commands_toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Toggle switch for applications.commands scope."""
        await interaction.response.defer()

        if self.with_app_scope:
            self.with_app_scope = False
            button.label = 'Add app command scope'
            button.emoji = '<:mCheck:819254444197019669>'
            button.style = discord.ButtonStyle.green
            
        else:
            self.with_app_scope = True
            button.label = 'Remove app command scope'
            button.emoji = '<:mCross:819254444217860116>'
            button.style = discord.ButtonStyle.red

        if self.with_app_scope:
            scopes = ('bot', 'applications.commands')
        else:
            scopes = ('bot', )

        url = discord.utils.oauth_url(self.application, permissions=self.permissions, scopes=scopes)

        await interaction.edit_original_response(
            content=f'Here is your custom generated invite link: \n{url}', view=self
        )


class ChoosePermissionsView(discord.ui.View):
    def __init__(self, application: discord.Member):
        super().__init__(timeout=300)

        self.application = application

        perms = []
        for name, _ in discord.Permissions.all():
            perms.append(name)

        select_1 = ChoosePermissionsSelect(min_values=0, max_values=24)
        select_1.options = [discord.SelectOption(label=perm.replace('_', ' ').title(), value=perm) for perm in perms[0:24]]
        self.add_item(select_1)

        select_2 = ChoosePermissionsSelect(min_values=0, max_values=17)
        select_2.options = [discord.SelectOption(label=perm.replace('_', ' ').title(), value=perm) for perm in perms[24:]]
        self.add_item(select_2)

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green)
    async def confirm_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Called when the user confirms the permissions they want."""

        selected = self.children[1].values + self.children[2].values
        permissions = discord.Permissions()

        for perm in selected:
            setattr(permissions, perm, True)
            
        url = discord.utils.oauth_url(self.application.id, permissions=permissions, scopes=('bot', 'applications.commands'))
        await interaction.response.send_message(
            f'Here is your custom generated invite link: \n{url}', 
            ephemeral=True, view=WithAppCommandScopeView(self.application.id, permissions=permissions, interaction=interaction))

class InviteView(discord.ui.View):
    def __init__(self, ctx : MyContext):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.client = None
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.ctx.author.id:
            return True
        await interaction.response.send_message('This pagination menu cannot be controlled by you, sorry!', ephemeral=True)
        return False

    async def start(self, interaction: Optional[discord.Interaction] = None, client: Optional[BotUserObject] = None):
        if interaction:
            _send = interaction.response.send_message
        else:
            _send = self.ctx.send

        client = client or self.ctx.bot.user
        self.client = client

        embed = Embed(color=self.ctx.color)
        embed.description = f"\n\n• [No Permissions]({discord.utils.oauth_url(client.id, permissions=discord.Permissions(0), scopes=('bot', 'applications.commands'))})"\
            f"\n• [Basic Permissions]({discord.utils.oauth_url(client.id, permissions=discord.Permissions(140663671873), scopes=('bot', 'applications.commands'))})"\
            f"\n• [**Advanced Permissions**]({discord.utils.oauth_url(client.id, permissions=discord.Permissions(140932115831), scopes=('bot', 'applications.commands'))}) \U00002b50"\
            f"\n• [Admin Permissions]({discord.utils.oauth_url(client.id, permissions=discord.Permissions(8), scopes=('bot', 'applications.commands'))})"\
            f"\n• [All Permissions]({discord.utils.oauth_url(client.id, permissions=discord.Permissions(-1), scopes=('bot', 'applications.commands'))})"
        embed.set_author(name='Invite %s to your server' % client, icon_url=client.display_avatar.url)

        if client != self.ctx.bot.user:
            embed.set_footer(text=f'This is inviting {client} to your server and not {self.ctx.bot.user.name}. \nI am not responsible for any damages.')

        self.message = await _send(embed=embed, view=self, ephemeral=True)

    @discord.ui.button(row=1, label='Choose permissions', style=discord.ButtonStyle.green)
    async def custom_perms(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            'Choose the permissions you want. (Leave blank for no permissions)\nThen choose the **Confirm** button when your done.', 
            view=ChoosePermissionsView(self.client), 
            ephemeral=True)

    @discord.ui.button(emoji='🗑️', style=discord.ButtonStyle.red, row=1)
    async def stop_pages(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Stop the pagination session. 
        Unless this pagination menu was invoked with a slash command
        """

        await interaction.response.defer()
        await interaction.delete_original_response()
        self.stop()

class NeedHelp(discord.ui.View):
    def __init__(self, ctx: MyContext, old_view: discord.ui.View):
        super().__init__(timeout=None)
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
    async def go_home_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=self.old_embed, view=self.old_view)
        self.stop()

    @discord.ui.button(emoji='🗑️', style=discord.ButtonStyle.red)
    async def stop_pages(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Stop the pagination session. 
        """
        
        await interaction.response.defer()
        await interaction.delete_original_response()
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
        self.select_category.add_option(emoji=self.bot.emotes['bot'], label='Bot Information', value='bot_information')
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

        embed = Embed(color=self.ctx.color)
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
        embed = Embed(color=self.ctx.color)
        embed.description = f'\n{self.ctx.bot.emotes["discord"]} [Support Server]({self.ctx.bot.support})'\
                f'\n{self.ctx.bot.emotes["inviteme"]} [Invite Link]({self.ctx.bot.invite})'\
                f'\n{self.ctx.bot.emotes["github"]} [Github]({self.ctx.bot.github})'\
                f'\n{self.ctx.bot.emotes["docs"]} [Documentation]({self.ctx.bot.docs})' 
        
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

        embed.add_field(name='Messages', value=count)
        embed.add_field(name='Uptime', value=get_bot_uptime(self.bot, brief=True))
        return embed

    async def all_commands_embed(self) -> discord.Embed:
        embed = Embed(
            title=f'All commands [{len(self.bot.commands)}]',
            color=self.ctx.color
        )
        
        embed.description = ', '.join([f"`{command}`" for command in self.bot.commands])
        embed.description += '\n\n__**This is a simplified list of my commands.\n Run `?help all` for a more detailed version**__'
        return embed

    def home_page_embed(self) -> discord.Embed:
        embed = Embed(
            description=
            f"\n**Total Commands:** {len(list(self.ctx.bot.walk_commands()))} | **Total Categories:** {len(self.ctx.bot.cogs)}"
            ,color=self.ctx.color
        )
        embed.add_field(
            name='Getting Help',
            value=f'\n • Use `{self.ctx.clean_prefix}help <command | category>` for some help and examples on any command'\
                f'\n • Join my [support server]({self.ctx.bot.support}) for additional help'\
                f'\n • Use the select menu below to view the categories\' commands',
            inline=True
        )
        embed.add_field(
            name='Quick Links',
            value=f'\n{self.ctx.bot.emotes["discord"]} [Support Server]({self.ctx.bot.support})'\
                f'\n{self.ctx.bot.emotes["inviteme"]} [Invite Link]({self.ctx.bot.invite})'\
                f'\n{self.ctx.bot.emotes["github"]} [Github]({self.ctx.bot.github})'\
                f'\n{self.ctx.bot.emotes["docs"]} [Documentation]({self.ctx.bot.docs})' 
        )
        embed.set_author(
            name=self.ctx.author.name + " | Help Menu",
            icon_url=self.ctx.author.display_avatar.url,
        )
        embed.set_footer(text=f'Made by {self.bot.owner if self.bot.owner else "dartmern#7563"} with 💖 and discord.py')
        return embed

    @discord.ui.select(placeholder='Please select a category...', row=0)
    async def select_category(self, interaction : discord.Interaction, select : discord.ui.Select):

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
    async def help_button(self, interaction : discord.Interaction, button : discord.ui.Button):
        await NeedHelp(self.ctx, self).start(interaction) 

    @discord.ui.button(label='Support Server', style=discord.ButtonStyle.blurple)
    async def support_url(self, interaction: discord.Interaction, button: discord.ui.Button):

        view = SupportView(self.ctx)
        await view.start(interaction)
        
    @discord.ui.button(label='Invite Me')
    async def invite_url(self, interaction: discord.Interaction, button: discord.ui.Button):
        
        view = InviteView(self.ctx)
        await view.start(interaction)

    @discord.ui.button(emoji='🗑️', style=discord.ButtonStyle.red)
    async def stop_pages(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Stop the pagination session. 
        """

        await self.ctx.check()
        await interaction.response.defer()
        await interaction.delete_original_response()
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
    def __init__(self, ctx: MyContext, *, command: commands.Command):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.command = command

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.ctx.author == interaction.user:
            return True
        await interaction.response.send_message(f"Only {self.ctx.author} can use this menu. Run the command yourself to use it.",
                                                ephemeral=True)
        return False

    @discord.ui.button(emoji='\U0001f5d1', style=discord.ButtonStyle.red)
    async def foo(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await self.ctx.message.add_reaction(self.ctx.bot.emotes['check'])
        await interaction.message.delete()

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

        embed = Embed(title=title, description=self.description.replace("[p]", self.ctx.prefix), color=self.ctx.color)


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
                description=self.get_doc(command).replace('[p]', self.context.prefix),
                color=self.context.color
            )
        else:
            em = Embed(
                title=f"`{command.qualified_name}` `{command.signature}`",
                description=self.get_doc(command).replace('[p]', self.context.prefix),
                color=self.context.color
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
        view = View(self.context, command=command)
        view.message = await self.context.send(embed=await self.get_command_help(command),view=view, hide=True)

    async def send_group_help(self, group):
        
        entries = await self.filter_commands(list((group.commands)))
        
        if int(len(group.commands)) == 0 or len(entries) == 0:
            view = View(self.context, command=group)
            view.message = await self.context.send(embed=await self.get_command_help(group),view=view, hide=True)
            return 

        menu = SimplePages(ButtonMenuSrc(group, entries, prefix=self.context.clean_prefix, ctx=self.context),ctx=self.context, compact=True)
        await menu.start()
        

    async def send_cog_help(self, cog: commands.Cog):
        to_join = []
        for command in cog.get_commands():
            short_doc = command.short_doc or "No help provided..."
            if len(command.name) < 20:
                group_mark = '✅' if isinstance(command, commands.Group) else ''
                empty_space = 20 - len(command.name)
                if not group_mark == '':
                    empty_space = empty_space - 2
                signature = f"`{command.name}{' '*empty_space}{group_mark}:` {short_doc if len(short_doc) < 58 else f'{short_doc[0:58]}...'}"
            else:
                group_mark = '✅' if isinstance(command, commands.Group) else ''
                signature = f"`{command.name[0:15]}...{group_mark}:` {short_doc if len(short_doc) < 58 else f'{short_doc[0:58]}...'}"
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

from discord import app_commands

@app_commands.context_menu(name='Invite Bot')
async def invite_bot_context_menu(interaction: discord.Interaction, member: discord.Member):
    if not member.bot:
        return await interaction.response.send_message('This is not a bot.', ephemeral=True)

    await interaction.response.send_message(
            'Choose the permissions you want. (Leave blank for no permissions)\nThen choose the **Confirm** button when your done.', 
            view=ChoosePermissionsView(member), 
            ephemeral=True)
       
async def setup(bot: MetroBot):
    bot.tree.add_command(invite_bot_context_menu)
    await bot.add_cog(meta(bot))

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

        self.bot: MetroBot = bot
        self.old_help_command = bot.help_command
        bot.help_command = MetroHelp(command_attrs=attrs)
        bot.help_command.cog = self

    @property
    def emoji(self) -> str:
        return 'ℹ️'


    @commands.hybrid_command()
    @commands.bot_has_permissions(send_messages=True)
    async def uptime(self, ctx: MyContext):
        """Get the bot's uptime."""

        await ctx.send(f'I have an uptime of: **{get_bot_uptime(self.bot, brief=False)}**', hide=True)

    @commands.hybrid_command(name='ping', aliases=['pong'])
    @commands.check(Cooldown(1, 5, 1, 3, commands.BucketType.member))
    async def ping(self, ctx: MyContext):
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

    @commands.hybrid_command(name='invite')
    @commands.bot_has_permissions(send_messages=True)
    @app_commands.describe(bot='The bot you wish to invite. Defaults to me.')
    async def invite(self, ctx: MyContext, *, bot: discord.User = None):
        """Get invite links for a bot."""
        bot = bot or self.bot.user
        if not bot.bot:
            raise commands.BadArgument("This is not a bot.")
        await InviteView(ctx).start(None, bot)

    @commands.hybrid_command()
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def support(self, ctx: MyContext):
        """Get an invite link for my support server."""
        await SupportView(ctx).start(None)

    @commands.hybrid_command(aliases=['tos'])
    async def privacy(self, ctx: MyContext):
        """View the bot's privacy policy."""

        await ctx.send(f"My privacy policy: <{self.bot.privacy_policy}>")
            
    @commands.hybrid_command(aliases=['upvote'])
    @app_commands.describe(bot='The bot you wish to vote for. Defaults to me.')
    async def vote(self, ctx: MyContext, *, bot: Optional[discord.User]):
        """Get vote links for the bot."""
        bot = bot or self.bot.user
        if not bot.bot:
            await ctx.send("This is not a bot.", hide=True)
        view = VoteView(ctx, bot, bot_instance=self.bot)
        await view.start()

    @commands.hybrid_command(name='bot-info', aliases=['botinfo', 'bi', 'info', 'stats', 'about'])
    async def _bot_info(self, ctx: MyContext):
        """Get all the information about me."""
        embed = await NewHelpView(ctx, {}, ctx.bot.help_command).bot_info_embed()

        await ctx.reply(embed=embed, view=BotInfoExtended())

