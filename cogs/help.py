import itertools
from discord.ext.commands.core import command
from utils.new_pages import SimplePages
from utils.pages import ExtraPages
import discord

import discord.ext

from discord.ext import commands, menus
import contextlib

import asyncio

from utils.custom_context import MyContext
from utils.useful import Embed, Cooldown, OldRoboPages


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
        print(docs_url)
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
            
            if command.signature == '':
                signature = f"`{command.name}` {command.short_doc}"
            else:
                signature = f"`{command.name} {command.signature}` {command.short_doc}"
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
    def get_doc(command):
        _help = command.help or "This command has no description"
        return _help


    async def command_callback(self, ctx, *, command : str =None):
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

        ctx : MyContext = self.context
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

        docs_url = f"{ctx.bot.docs}/{command.cog_name}/{command.qualified_name}"
        em.set_author(name='Documentation Link', url=docs_url, icon_url=ctx.bot.user.display_avatar.url)

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
            examples = command_extras['examples'].replace("[p]", ctx.prefix)
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
        

    async def handle_help(self, command):
        with contextlib.suppress(commands.CommandError):
            if not await command.can_run(self.context):
                raise commands.CommandError
            if self.context.interaction:
                return await self.context.interaction.response.send_message(embed=self.get_command_help(command),ephemeral=True)
            else:
                return await self.context.send(embed=await self.get_command_help(command),view=View(self.context.author))
        raise commands.BadArgument("You do not have the permissions to view this command's help.")



    async def send_bot_help(self, mapping):
        ctx = self.context
        bot = ctx.bot

        to_append = []

        def get_category(command, *, no_category : str ='**•** No Category - :black_small_square: Commands without categories'):
            cog = command.cog
            return '**•** **' + cog.qualified_name.capitalize() + '** - ' + cog.description if cog is not None else no_category
        filtered = await self.filter_commands(bot.commands, sort=True, key=get_category)
        to_iterate = itertools.groupby(filtered, key=get_category)

        for category, commands in to_iterate:
            to_append.append(category)
        
        embed = Embed(
            description=
            f"**Total Commands:** {len(list(bot.walk_commands()))} | **Usable by you (here):** {len(await self.filter_commands(list(bot.walk_commands()), sort=True))}"
            f"\n```diff\n- [] = optional argument\n- <> = required argument\n- Do not type these when using commands!\n+ Type {ctx.clean_prefix}{ctx.invoked_with} [Command/Module] for more help on a command```"
            f"[Support]({ctx.bot.invite}) | [Invite]({ctx.bot.invite}) | [Donate]({ctx.bot.donate}) | [Documentation]({ctx.bot.docs})"
        )
        embed.add_field(
            name=f"**Modules: [{len(to_append)}]**",
            value='\n'.join(to_append),
            inline=True
        )
        
        embed.set_author(
            name=self.context.author.name + " | Help Menu",
            icon_url=self.context.author.avatar.url,
        )

        channel = self.get_destination()
        await channel.send(embed=embed, hide=True)

    async def send_missing_required_argument(self, ctx, error):
        missing = f"{error.param.name}"
        command = f"{ctx.clean_prefix}{ctx.command} {ctx.command.signature}"
        separator = (' ' * (len([item[::-1] for item in command[::-1].split(missing[::-1], 1)][::-1][0]) - 1)) + (8*' ')
        indicator = ('^' * (len(missing) + 2))
        return await ctx.send(
                                  f"\n```yaml\nSyntax: {command}\n{separator}{indicator}"
                                  f'\n{missing} is a required argument that is missing.\n```',
                                  embed=await self.get_command_help(ctx.command))

    async def send_command_help(self, command):
        return await self.context.send(embed=await self.get_command_help(command),view=View(self.context.author), hide=True)

    async def send_group_help(self, group):
        
        entries = await self.filter_commands(group.commands)
        
        if int(len(group.commands)) == 0 or len(entries) == 0:
            return await self.context.send(embed=await self.get_command_help(group),view=View(self.context.author), hide=True)

        menu = SimplePages(ButtonMenuSrc(group, entries, prefix=self.context.clean_prefix, ctx=self.context),ctx=self.context)
        await menu.start()
        

    async def send_cog_help(self, cog):
        entries = await self.filter_commands(cog.get_commands())
        #entries = cog.get_commands() 
        # No filters

        menu = SimplePages(GroupHelpPageSource(cog, entries, prefix=self.context.prefix), ctx=self.context, hide=True)
        await menu.start()



    # Error handlers
    async def command_not_found(self, command):
        if command.lower() == "all":
            commands = await self.filter_commands(self.context.bot.commands)
            
            menu = SimplePages(source=HelpSource(tuple(commands), prefix=self.context.prefix), ctx=self.context)
            await menu.start()
            return


        return f"No command/category called `{command}` found."

    async def send_error_message(self, ctx, error):
        if error is None:
            return
        return await ctx.send(error, hide=True)
       


class meta(commands.Cog, description='ℹ️ Get bot stats and information.'):
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


    @commands.command(name='invite',slash_command=True)
    @commands.bot_has_permissions(send_messages=True)
    async def invite(self, ctx):
        """Get invite links for the bot."""


        basic_button = discord.ui.Button(label='Basic Perms',url='https://discord.com/api/oauth2/authorize?client_id=788543184082698252&permissions=140663671873&scope=bot%20applications.commands')
        advan_button = discord.ui.Button(label='Advanced Perms',url='https://discord.com/api/oauth2/authorize?client_id=788543184082698252&permissions=140932115831&scope=bot%20applications.commands')
        admin_button = discord.ui.Button(label='Admin Perms',url='https://discord.com/api/oauth2/authorize?client_id=788543184082698252&permissions=8&scope=bot%20applications.commands')

        view = discord.ui.View()
        view.add_item(basic_button)
        view.add_item(advan_button)
        view.add_item(admin_button)

        await ctx.send('Please choose a permission to invite me with below:',view=view)


    @commands.command()
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def support(self, ctx):
        await ctx.reply(ctx.bot.support)


def setup(bot):
    bot.add_cog(meta(bot))