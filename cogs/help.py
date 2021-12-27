import itertools
from typing import Any, List
from discord.embeds import E
from discord.ext.commands.core import command
from discord.ext.commands.errors import CommandError
from discord.ext.commands.help import HelpCommand
from bot import MetroBot
from utils.new_pages import SimplePages
from utils.pages import ExtraPages
import discord

import discord.ext

from discord.ext import commands, menus
import contextlib

import asyncio
import copy
import time

from utils.custom_context import MyContext
from utils.useful import Embed, Cooldown, OldRoboPages, get_bot_uptime

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
    



class InviteView(discord.ui.View):
    def __init__(self, ctx : MyContext):
        super().__init__()
        self.ctx = ctx

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
            f'\n- You can use [this calculator](https://discordapi.com/permissions.html) to calculate the permissions if you are unsure what to put.'
        
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.gray, label='None', url=discord.utils.oauth_url(self.ctx.bot.user.id, permissions=discord.Permissions(0))))
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.gray, label='Basic', url=discord.utils.oauth_url(self.ctx.bot.user.id, permissions=discord.Permissions(140663671873))))
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.blurple, label='Advanced', url=discord.utils.oauth_url(self.ctx.bot.user.id, permissions=discord.Permissions(140932115831))))
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.gray, label='Admin', url=discord.utils.oauth_url(self.ctx.bot.user.id, permissions=discord.Permissions(8))))
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.gray, label='All', url=discord.utils.oauth_url(self.ctx.bot.user.id, permissions=discord.Permissions(549755813887))))
        await self.ctx.send(embed=embed, view=self)

    async def start(self, interaction: discord.Interaction):

        embed = Embed()
        embed.colour = discord.Colour.blue()
        embed.description = "__**Choose a invite option below or press `Create custom permissions`**__"\
            f"\n\nIf you press `Create custom permissions` you are required to enter a vaild discord permissions integer."\
            f'\n- You can use [this calculator](https://discordapi.com/permissions.html) to calculate the permissions if you are unsure what to put.'
        
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.gray, label='None', url=discord.utils.oauth_url(self.ctx.bot.user.id, permissions=discord.Permissions(0))))
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.gray, label='Basic', url=discord.utils.oauth_url(self.ctx.bot.user.id, permissions=discord.Permissions(140663671873))))
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.blurple, label='Advanced', url=discord.utils.oauth_url(self.ctx.bot.user.id, permissions=discord.Permissions(140932115831))))
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.gray, label='Admin', url=discord.utils.oauth_url(self.ctx.bot.user.id, permissions=discord.Permissions(8))))
        self.add_item(discord.ui.Button(style=discord.ButtonStyle.gray, label='All', url=discord.utils.oauth_url(self.ctx.bot.user.id, permissions=discord.Permissions(549755813887))))
        
        await interaction.response.send_message(embed=embed, view=self)

    @discord.ui.button(row=1, label='Enter a custom permission value', style=discord.ButtonStyle.green)
    async def custom_perms(self, button: discord.ui.Button, interaction: discord.Interaction):
        
        await interaction.response.send_message(f"Please enter a permissions integer: ")
        
        def check(message : discord.Message) -> bool:
            return message.channel == self.ctx.channel and message.author == self.ctx.author and message.content.isdigit()

        try:
            message = await self.ctx.bot.wait_for("message", check=check, timeout=180)
        except asyncio.TimeoutError:
            return await interaction.followup.send("Timed out.")
        
        em = Embed()
        em.description = f"Permission Integer: {message.content}"\
            f"\n Invite URL: {discord.utils.oauth_url(self.ctx.bot.user.id, permissions=discord.Permissions(int(message.content)))}"
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

    @discord.ui.button(label='Go Home', emoji='🏘️', style=discord.ButtonStyle.blurple)
    async def go_home_button(self, _, interaction: discord.Interaction):
        await interaction.response.edit_message(embed=self.old_embed, view=self.old_view)
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

        for category, command in self.data:
            if category[0] == 'Jishaku':
                self.select_category.add_option(emoji=None, label=category[0].capitalize(), description='The Jishaku debug and diagnostic commands.')
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

        description = f" __**{cog.qualified_name.capitalize()}**__ \n"
        description += (
            '\n'.join(to_join)
        )
        embed.description = description
        embed.set_footer(text='A command marked with a ✅ means it\'s a group command.')
        return embed

    def home_page_embed(self) -> discord.Embed:
        embed = Embed(
            description=
            f"\n**Total Commands:** {len(list(self.ctx.bot.walk_commands()))} | **Total Categories:** {len(self.ctx.bot.cogs)}"
        )
        embed.add_field(
            name='Getting Help',
            value=f'\n • Use `{self.ctx.prefix}help <command>` for some help and examples on any command'\
                f'\n • Join my [support server]({self.ctx.bot.support}) for additional help'\
                f'\n • Use the select menu below to view the categories\' commands'\
                f'\n • Use `{self.ctx.prefix}help all` to view all my commands in one message',
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
        return embed

    @discord.ui.select(placeholder='Please select a category...', row=0)
    async def select_category(self, select : discord.ui.Select, interaction : discord.Interaction):

        if select.values[0] == 'home_page': 
            await interaction.response.edit_message(embed=self.home_page_embed(), view=self)
        else:
            cog = self.bot.get_cog(select.values[0].lower())
            if not cog:
                return await interaction.response.send_message(f"That category was somehow not found. Try using `{self.ctx.prefix}help {select.values[0]}`", ephemeral=True)
            await interaction.response.edit_message(embed=self.category_embed(cog))

    @discord.ui.button(label='Need help', emoji='❓', style=discord.ButtonStyle.red)
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

        embed = Embed(description=f'All commands: [{len(commands)}]')
        
        desc = ""

        for command in commands:
            desc += f"`{command.name}` {command.short_doc or 'No help provided...'}\n"

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
        docs_url = f"{self.ctx.bot.docs}/{self.group.cog_name}/{(self.group.qualified_name).replace(' ', '/')}"
        embed.set_author(name='Documentation Link', url=docs_url, icon_url=self.ctx.bot.user.display_avatar.url)


        cooldown = discord.utils.find(lambda x: isinstance(x, Cooldown), self.group.checks) or Cooldown(1, 3, 1, 1,
                                                                                                     discord.ext.commands.BucketType.user)

        default_cooldown_per = cooldown.default_mapping._cooldown.per
        altered_cooldown_per = cooldown.altered_mapping._cooldown.per

        default_cooldown_rate = cooldown.default_mapping._cooldown.rate
        altered_cooldown_rate = cooldown.altered_mapping._cooldown.rate

        embed.add_field(
            name="Cooldowns",
            value=f"Default: `{default_cooldown_rate}` time(s) every `{default_cooldown_per}` seconds"\
                    f"\nTester: `{altered_cooldown_rate}` time(s) every `{altered_cooldown_per}` seconds",
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
            examples = self.extras['examples'].replace("[p]", self.prefix)
            embed.add_field(
                name='Examples/Usage',
                value=examples,
                inline=False
            )

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

        if not command.cog_name == 'Jishaku':
            docs_url = f"https://metro-discord-bot.gitbook.io/metro-documentation/{command.cog_name}/{command.qualified_name.replace(' ', '/')}"
            em.set_author(name='Documentation Link', url=docs_url, icon_url='https://cdn.discordapp.com/embed/avatars/1.png')

        # Cooldowns
        cooldown = discord.utils.find(lambda x: isinstance(x, Cooldown), command.checks) or Cooldown(1, 3, 1, 1,
                                                                                                     commands.BucketType.user)

        default_cooldown_per = cooldown.default_mapping._cooldown.per
        altered_cooldown_per = cooldown.altered_mapping._cooldown.per

        default_cooldown_rate = cooldown.default_mapping._cooldown.rate
        altered_cooldown_rate = cooldown.altered_mapping._cooldown.rate

        em.add_field(
            name="Cooldowns",
            value=f"Default: `{default_cooldown_rate}` time(s) every `{default_cooldown_per}` seconds"\
                    f"\nTester: `{altered_cooldown_rate}` time(s) every `{altered_cooldown_per}` seconds",
                    inline=False
        )

        # Aliases
        em.add_field(
            name="Aliases",
            value=f"```{', '.join(command.aliases) or 'No aliases'}```",
            inline=False
        )
        if command_extras:
            examples = command_extras['examples'].replace("[p]", self.context.prefix)
            em.add_field(
                name='Examples/Usage',
                value=examples,
                inline=False
            )

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

        def get_category(command, *, no_category='No Category'):
            cog = command.cog
            if cog is None: return [no_category, 'Commands that do not have a category.']
            try:
                to_return = [cog.qualified_name, cog.description, cog.emoji]
                if cog.emoji == '':
                    return [cog.qualified_name, cog.description]
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
            
            menu = SimplePages(source=HelpSource(tuple(commands), prefix=self.context.prefix), ctx=self.context)
            await menu.start()
            await self.context.send("This part of the command kinda sucks and will be updated soon.")
            return


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
    async def invite(self, ctx):
        """Get invite links for the bot."""
        await InviteView(ctx).start_normal()

    @commands.command()
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def support(self, ctx):
        await ctx.reply(ctx.bot.support)


def setup(bot):
    bot.add_cog(meta(bot))