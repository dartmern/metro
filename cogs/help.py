from cogs.channel import MySource
from sys import prefix
from utils.pages import ExtraPages
import discord
from discord.ext.commands import BucketType
import discord.ext

from discord.ext import commands, menus
import contextlib

import asyncio
import textwrap

from discord.ui import view
from discord.ext.menus.views import ViewMenuPages

from utils.useful import Embed, Cooldown, RoboPages





class View(discord.ui.View):
    def __init__(self, author):
        super().__init__(timeout=60)
        self.user = author


    async def on_timeout(self) -> None:
        self.foo.disabled = True
        await self.message.edit(view=self)

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


class HelpMenu(RoboPages):
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
    def __init__(self, group, commands, *, prefix):
        super().__init__(entries=commands, per_page=9)
        self.group = group
        self.prefix = prefix
        self.title = f"`{self.group.name}`"
        self.description = self.group.description

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

        embed = Embed(title=self.title, description=self.description)

        cooldown = discord.utils.find(lambda x: isinstance(x, Cooldown), self.group.checks) or Cooldown(1, 3, 1, 1,
                                                                                                     discord.ext.commands.BucketType.user)
        default_cooldown = cooldown.default_mapping._cooldown.per
        

        embed.add_field(
            name="Cooldowns",
            value=f"Can be used `1` time every `{default_cooldown}` seconds",
        )
        embed.add_field(
            name="Aliases",
            value=f"```{','.join(self.group.aliases) or 'No aliases'}```",
            inline=False
        )

        sub_commands = []

        for command in commands:
            signature = f"`{command.name} {command.signature}` {command.short_doc}"
            sub_commands.append(signature)

        embed.add_field(name='Subcommands',value='\n'.join(sub_commands),inline=False)

        embed.set_footer(
            text=footer
        )
        return embed


class MetroHelp(commands.HelpCommand):



    @staticmethod
    def get_doc(command):
        _help = command.help or "This command has no description"
        return _help


    async def command_callback(self, ctx, *, command=None):
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
            return await self.send_error_message(string)

        for key in keys[1:]:
            try:
                found = cmd.all_commands.get(key)
            except AttributeError:
                string = await maybe_coro(self.subcommand_not_found, cmd, self.remove_mentions(key))
                return await self.send_error_message(string)
            else:
                if found is None:
                    string = await maybe_coro(self.subcommand_not_found, cmd, self.remove_mentions(key))
                    return await self.send_error_message(string)
                cmd = found

        if isinstance(cmd, commands.Group):
            return await self.send_group_help(cmd)
        else:
            return await self.send_command_help(cmd)

    def get_command_help(self, command) -> Embed:

        ctx = self.context
        # Base
        if command.signature == "":
            em = Embed(
                title=f"`{command.name}`",
                description=self.get_doc(command)
            )
        else:
            em = Embed(
                title=f"`{command.name}` `{command.signature}`",
                description=self.get_doc(command)
            )

        # Cooldowns
        cooldown = discord.utils.find(lambda x: isinstance(x, Cooldown), command.checks) or Cooldown(1, 3, 1, 1,
                                                                                                     commands.BucketType.user)

        default_cooldown = cooldown.default_mapping._cooldown.per

        em.add_field(
            name="Cooldowns",
            value=f"Can be used `1` time every `{default_cooldown}` seconds",
        )

        # Aliases
        em.add_field(
            name="Aliases",
            value=f"```{','.join(command.aliases) or 'No aliases'}```",
            inline=False
        )

        if not isinstance(command, commands.Group):

            return em

        all_subs = [
            f"`{sub.name}` {f'`{sub.signature}`' if sub.signature else ''} {sub.short_doc}" for sub in command.walk_commands()
        ]   

        if len(all_subs) == 0:
            em.add_field(name='No Subcommands',value="\u200b",inline=False)
            return em

        em.add_field(
            name="Subcommands",
            value="\n".join(all_subs)
        )

        return em
        

    async def handle_help(self, command):
        with contextlib.suppress(commands.CommandError):
            if not await command.can_run(self.context):
                raise commands.CommandError
            return await View.start(self.context, self.get_command_help(command))
        raise commands.BadArgument("You do not have the permissions to view this command's help.")



    async def send_bot_help(self, mapping):
        ctx = self.context
        bot = ctx.bot

        newline = '\n'
        cogs = []
        for cog in bot.cogs:
            cogs.append(cog.capitalize())

        cogs.remove('Jishaku')
        try:
            cogs.remove('Core')
            cogs.remove('Developer')
        except:
            pass


        channel = bot.get_channel(812527644855107584)
        

        embed = Embed(
            description=
            f"**Total Commands:** {len(list(bot.walk_commands()))} | **Usable by you (here):** {len(await self.filter_commands(list(bot.walk_commands()), sort=True))}"
            f"\n```diff\n- [] = optional argument\n- <> = required argument\n- Do not type these when using commands!\n+ Type {ctx.clean_prefix}help [Command/Module] for more help on a command```"
            f"[Support](https://discord.gg/2ceTMZ9qJh) | [Invite]({discord.utils.oauth_url(788543184082698252)}) | [Donate](https://www.patreon.com/metrodiscordbot) | [Source](https://vex.wtf)"
        )
        embed.add_field(
            name=f"**Modules: [{len(bot.cogs)-2}]**",
            value=f"```\n{newline.join(cogs)}```",
            inline=True
        )
        

        
        embed.set_author(
            name=self.context.author.name + " | Help Menu",
            icon_url=self.context.author.avatar.url,
        )
        embed.set_footer(text='Clicking on the support button will instantly join the server!')
        

        channel = self.get_destination()

        item = discord.ui.Button(label="Invite",emoji='\U00002795',url='https://discord.com/oauth2/authorize?client_id=788543184082698252&scope=bot&permissions=1077234753')
        item2 = discord.ui.Button(label='Support',emoji='\U0001f6e0',url='https://discord.gg/2ceTMZ9qJh')
        view = discord.ui.View()
        view.add_item(item)
        view.add_item(item2)


        await channel.send(embed=embed,view=view)


    async def send_command_help(self, command):
        await self.handle_help(command)

    async def send_group_help(self, group):

        if int(len(group.commands)) == 0:
            await self.handle_help(group)
            return

        entries = await self.filter_commands(group.commands)

        menu = HelpMenu(ButtonMenuSrc(group, entries, prefix=self.context.clean_prefix))
        await menu.start(self.context)
        

    async def send_cog_help(self, cog):
        entries = await self.filter_commands(cog.get_commands())

        menu = HelpMenu(GroupHelpPageSource(cog, entries, prefix=self.context.prefix))
        await menu.start(self.context)



    # Error handlers
    async def command_not_found(self, command):
        if command.lower() == "all":

            
            commands = await self.filter_commands(self.context.bot.commands)
            
            menu = ExtraPages(source=HelpSource(tuple(commands), prefix=self.context.prefix),)
            await menu.start(self.context)
            return

            

        return f"No command/category called `{command}` found."

    async def send_error_message(self, error):
        if error is None:
            return
        channel = self.get_destination()
        await channel.send(error)





class meta(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.old_help_command = bot.help_command
        bot.help_command = MetroHelp()
        bot.help_command.cog = self


    @commands.command(name='invite')
    async def _invite(self, ctx):

        basic = discord.Permissions.none()
        basic.create_instant_invite = True
        basic.manage_emojis = True
        basic.read_messages = True
        basic.send_messages = True
        basic.embed_links = True
        basic.read_message_history = True
        basic.add_reactions = True
        basic.use_external_emojis = True
        basic.connect = True
        basic.speak = True


        advan = discord.Permissions.none()
        advan.manage_guild = True
        advan.manage_roles = True
        advan.manage_channels = True
        advan.kick_members = True
        advan.ban_members = True
        advan.create_instant_invite = True
        advan.manage_emojis = True
        advan.read_messages = True
        advan.send_messages = True
        advan.manage_messages = True
        advan.embed_links = True
        advan.read_message_history = True
        advan.add_reactions = True
        advan.use_external_emojis = True
        advan.connect = True
        advan.speak = True
        advan.priority_speaker = True

        admin = discord.Permissions.none()
        admin.administrator = True

        basic_button = discord.ui.Button(label='Basic Perms',url=str(discord.utils.oauth_url(ctx.me.id, permissions=basic)))
        advan_button = discord.ui.Button(label='Advanced Perms',url=str(discord.utils.oauth_url(ctx.me.id, permissions=advan)))
        admin_button = discord.ui.Button(label='Admin Perms',url=str(discord.utils.oauth_url(ctx.me.id, permissions=admin)))

        view = discord.ui.View()
        view.add_item(basic_button)
        view.add_item(advan_button)
        view.add_item(admin_button)

        await ctx.send('Please choose a permission to invite me with below:',view=view)

    




    @commands.command()
    async def support(self, ctx):

        await ctx.reply(embed=Embed
            (description=
             f'Join my support server for help:'
             f'\nhttps://discord.gg/2ceTMZ9qJh')
                        )



def setup(bot):
    bot.add_cog(meta(bot))




