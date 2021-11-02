from utils.new_pages import SimplePages
from utils.pages import ExtraPages
import discord

import discord.ext

from discord.ext import commands, menus
import contextlib

import asyncio


from utils.context import MyContext

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
    def __init__(self, group, commands, *, prefix):
        super().__init__(entries=commands, per_page=9)
        self.group = group
        self.prefix = prefix
        self.description = self.group.help  
        

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
            title = f'`{self.group.name}`'
        else:
            title = f"`{self.group.name}` `{self.group.signature}`"

        embed = Embed(title=title, description=self.description)

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
            
            if command.signature == '':
                signature = f"`{command.name}` {command.short_doc}"
            else:
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

    async def get_command_help(self, command) -> Embed:

        ctx = self.context
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
            try:
                return await self.context.interaction.response.send_message(embed=self.get_command_help(command),ephemeral=True)
            except:
                
                message = getattr(self.context.message.reference, "resolved", None)
                if message:
                    return await message.reply(embed=await self.get_command_help(command),view=View(self.context.author))
                return await self.context.send(embed=await self.get_command_help(command),view=View(self.context.author))


        raise commands.BadArgument("You do not have the permissions to view this command's help.")



    async def send_bot_help(self, mapping):
        ctx = self.context
        bot = ctx.bot

        nl = '\n'
        cogs = []
        bl_cogs = ['jishaku','developer','core']
        for cog in bot.cogs:
            if cog.lower() in bl_cogs:
                pass
            else:
                cog_object = bot.get_cog(cog)
                cogs.append(f'• **{cog.capitalize()}** - {cog_object.description}')

    
        embed = Embed(
            description=
            f"**Total Commands:** {len(list(bot.walk_commands()))} | **Usable by you (here):** {len(await self.filter_commands(list(bot.walk_commands()), sort=True))}"
            f"\n```diff\n- [] = optional argument\n- <> = required argument\n- Do not type these when using commands!\n+ Type {ctx.clean_prefix}help [Command/Module] for more help on a command```"
            f"[Support](https://discord.gg/2ceTMZ9qJh) | [Invite](https://discord.com/api/oauth2/authorize?client_id=788543184082698252&permissions=140663671873&scope=bot%20applications.commands) | [Donate](https://www.patreon.com/metrodiscordbot) | [Source](https://vex.wtf)"
        )
        embed.add_field(
            name=f"**Modules: [{len(cogs)}]**",
            value=f"{nl.join(cogs)}",
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

        try:
            await ctx.interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        except:
            await channel.send(embed=embed,view=view)


    async def send_command_help(self, command):
        await self.handle_help(command)

    async def send_group_help(self, group):
        
        entries = await self.filter_commands(group.commands)
        
        if int(len(group.commands)) == 0 or len(entries) == 0:
            await self.handle_help(group)
            return

        menu = SimplePages(ButtonMenuSrc(group, entries, prefix=self.context.clean_prefix),ctx=self.context)
        await menu.start()
        

    async def send_cog_help(self, cog):
        entries = await self.filter_commands(cog.get_commands())

        menu = SimplePages(GroupHelpPageSource(cog, entries, prefix=self.context.prefix), ctx=self.context)
        await menu.start()



    # Error handlers
    async def command_not_found(self, command):
        if command.lower() == "all":

            
            commands = await self.filter_commands(self.context.bot.commands)
            
            menu = ExtraPages(source=HelpSource(tuple(commands), prefix=self.context.prefix))
            await menu.start(self.context)
            return

            

        return f"No command/category called `{command}` found."

    async def send_error_message(self, ctx, error):
        if error is None:
            return

        try:
            return await ctx.interaction.response.send_message(error, ephemeral=True)
        except:
            return await ctx.send(error)
       





class meta(commands.Cog, description='ℹ️ Get bot stats and information.'):
    def __init__(self, bot):

        attrs = {
            'name' : 'help',
            'description' : 'Show bot help or help for a command',
            'aliases' : ['h','command'],
            'slash_command' : True,
            'message_command' : True
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

        await ctx.reply(embed=Embed
            (description=
             f'Join my support server for help:'
             f'\nhttps://discord.gg/2ceTMZ9qJh')
                        )



def setup(bot):
    bot.add_cog(meta(bot))




