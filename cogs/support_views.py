import re
import discord
import time
from discord.ext import commands


from utils.custom_context import MyContext
from utils.converters import BotUser
from utils.useful import Cooldown, Embed
from utils.checks import in_support, is_dev


import typing
import asyncio

SUPPORT_GUILD = 812143286457729055
TESTER_ROLE = 861141649265262592
 
class RoleView(discord.ui.View):
    def __init__(self, bot) -> None:
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label='Metro Updates', style=discord.ButtonStyle.blurple, row=0, custom_id='metro_updates_button')
    async def metro_updates_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        
        guild = self.bot.get_guild(812143286457729055)

        role = guild.get_role(828795116000378931)
        if role in interaction.user.roles:
            
            embed = Embed()
            embed.description = 'Removed **Metro Updates** from your roles.'
            embed.color = discord.Colour.red()
            await interaction.user.remove_roles(role)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        else:

            embed = Embed()
            embed.description = 'Added **Metro Updates** to your roles.'
            embed.color = discord.Colour.green()
            await interaction.user.add_roles(role)
            return await interaction.response.send_message(embed=embed, ephemeral=True)



    @discord.ui.button(label='Server Annoucements', style=discord.ButtonStyle.blurple, row=1, custom_id='server_annoucements_button')
    async def server_annoucements_button(self, button: discord.ui.Button, interaction: discord.Interaction):
        
        guild = self.bot.get_guild(812143286457729055)

        role = guild.get_role(828795624945614858)
        if role in interaction.user.roles:
            
            embed = Embed()
            embed.description = 'Removed **Server Annoucements** from your roles.'
            embed.color = discord.Colour.red()
            await interaction.user.remove_roles(role)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        else:

            embed = Embed()
            embed.description = 'Added **Server Annoucements** to your roles.'
            embed.color = discord.Colour.green()
            await interaction.user.add_roles(role)
            return await interaction.response.send_message(embed=embed, ephemeral=True)


class TesterButton(discord.ui.View):
    def __init__(self, bot) -> None:
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label='Tester', style=discord.ButtonStyle.blurple, custom_id='metro_tester')
    async def tester_button(self, button : discord.ui.Button, interaction : discord.Interaction):

        guild = self.bot.get_guild(812143286457729055)

        role = guild.get_role(861141649265262592)
        if role in interaction.user.roles:

            embed = Embed()
            embed.description = 'Removed **Tester** from your roles.'
            embed.color = discord.Colour.red()
            await interaction.user.remove_roles(role)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        else:
            embed = Embed()
            embed.description = 'Added **Tester** to your roles.'
            embed.color = discord.Colour.green()
            await interaction.user.add_roles(role)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

            
class AllRoles(discord.ui.View):
    def __init__(self, bot) -> None:
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label='Check my roles', style=discord.ButtonStyle.green, custom_id='all_roles')
    async def tester_button(self, button : discord.ui.Button, interaction : discord.Interaction):

        guild = self.bot.get_guild(812143286457729055)

        updates = guild.get_role(828795116000378931)
        annoucements = guild.get_role(828795624945614858)
        tester = guild.get_role(861141649265262592)

        if updates in interaction.user.roles:
            updates_y_n = self.bot.check
        else:
            updates_y_n = self.bot.cross

        if annoucements in interaction.user.roles:
            annouce_y_n = self.bot.check
        else:
            annouce_y_n = self.bot.cross

        if tester in interaction.user.roles:
            test_y_n = self.bot.check
        else:
            test_y_n = self.bot.cross


        embed = Embed()
        embed.title = 'Your Roles:'
        embed.description = f'**Metro Updates:** {updates_y_n} \n**Annoucements:** {annouce_y_n}\n\n**Tester:** {test_y_n}'
 
        await interaction.response.send_message(embed=embed, ephemeral=True)


        


class support(commands.Cog, description=':test_tube: Support only commands.'):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member):

        if member.guild.id != SUPPORT_GUILD:
            return

        if member.bot:
            await member.add_roles(discord.Object(id=904872199943491596))


    @commands.command(hidden=True)
    @commands.is_owner()
    @is_dev()
    async def support_roles(self, ctx : MyContext):

        await ctx.message.delete(silent=True)

        roles_channel = self.bot.get_channel(828466726659948576)

        embed = Embed()
        embed.title = 'Self-Roles'
        embed.description = 'Click on a button to add/remove that role.'

        tester_embed = Embed()
        tester_embed.title = 'Self-Roles'
        tester_embed.description = 'Click on a button to add/remove that role.'

        view = RoleView(ctx.bot)
        tester_view = TesterButton(ctx.bot)
        all_roles = AllRoles(ctx.bot)

        roles = Embed()
        roles.title='Check your roles'
        roles.description = 'Click below to see the roles you have'

        await roles_channel.send(embed=embed, view=view)
        await roles_channel.send(embed=tester_embed, view=tester_view)
        await roles_channel.send(embed=roles, view=all_roles)



    @commands.command(hidden=True)
    @commands.check(Cooldown(1, 10, 1, 10, bucket=commands.BucketType.member))
    @in_support()
    async def addbot(
        self, 
        ctx : MyContext,
        user : BotUser,
        *,
        reason : str 
    ):
        """Request to add your bot to the server.
        
        To make a request you need your bot's user ID and a reason
        """

        confirm = await ctx.confirm(
            'This server\'s moderators have the right to kick or reject your bot for any reason.'
            '\nYou also agree that your bot does not have the following prefixes: `?`,`!`'
            '\nYour bot cannot have an avatar that might be considered NSFW, ping users when they join, post NSFW messages in not NSFW marked channels.'
            '\nRules that may apply to users should also be applied to bots.'
            '\n**This is not a exextensive list and you can see all the rules listed in <#904215351833800744>**'
            '\n\nHit the **Confirm** button below to submit your request and agree to these terms.', timeout=60  
            )

        if confirm is False:
            return await ctx.send('Canceled.')
        if confirm is None:
            return await ctx.send('Timed out.')

        else:
            url = f'https://discord.com/oauth2/authorize?client_id={user.id}&scope=bot&guild_id={ctx.guild.id}'
            description = f"{reason}\n\n[Invite URL]({url})"

            embed = Embed(title='Bot Request',description=description)
            embed.add_field(name='Author',value=f'{ctx.author} (ID: {ctx.author.id})',inline=False)
            embed.add_field(name='Bot',value=f'{user} (ID: {user.id})',inline=False)
            embed.timestamp = ctx.message.created_at

            embed.set_author(name=user.id, icon_url=user.display_avatar.url)
            embed.set_footer(text=ctx.author.id)

            try:
                channel = self.bot.get_channel(904184918840602684)
                message = await channel.send(embed=embed)
            except discord.HTTPException as e:
                return await ctx.send(f'Failed to add your bot.\n{str(e)}')

            await message.add_reaction(self.bot.check)
            await message.add_reaction(self.bot.cross)

            await ctx.send('Your bot request has been submitted to the moderators. I will DM you about the status of your request.')


    @commands.command(hidden=True)
    @commands.is_owner()
    async def approve(self, ctx, user : discord.Member, bot : int):

        await user.send(f'Your bot (<@{bot}>) was added to {ctx.guild.name}')
        await ctx.check()

    @commands.command()
    async def foo(self, ctx : MyContext, args : typing.Literal[1,2,3]):
        await ctx.send(args, hide=True)

    @commands.command(
        name='tester',
        hidden=True
    )
    @in_support()
    async def tester(self, ctx : MyContext):
        """Toggle the tester role for yourself."""

        role = ctx.guild.get_role(TESTER_ROLE)

        if role in ctx.author.roles:
            await ctx.author.remove_roles(role)
            return await ctx.message.add_reaction('<:mminus:904450883587276870>')

        else:
            await ctx.author.add_roles(role)
            return await ctx.message.add_reaction('<:mplus:904450883633426553>')

    @commands.command()
    @in_support()
    async def faq(self, ctx : MyContext):
        """Show Metro's faq."""

        embeds = []

        embed = Embed()
        embed.colour = discord.Colour.yellow()
        embed.add_field(
            name='How to disable a certain command', 
            value='\n - You can do this with the `?config disable [entity] [commands...]` command.' \
                '\n An entity can be a channel/role/member.'\
                '\n You can disable commands for the entire guild by using `~` for entity.'
                '\n Example: `?config disable #general selfmute`'\
                '\n :mag: **Tip:** You can disable multiple commands like this: `?config disable ~ selfmute mute unmute`'
        )
        embeds.append(embed)

        embed = Embed()
        embed.colour = discord.Colour.yellow()
        embed.add_field(
            name='How to ignore commands in a channel',
            value='\n - You can do this with the `?config ignore [entities...]` command.'\
                '\n An entity can be a channel/role/member.'\
                '\n You can disable all commands by using `~` in place of entities.'
                '\n Example: `?config ignore #general`'
        )
        embeds.append(embed)

        embed = Embed()
        embed.colour = discord.Colour.light_gray()
        embed.add_field(
            name='How to setup a mute role with an exisiting role',
            value='\n - Run `?muterole` in your server and choose the `Set existing muterole` option.'\
                '\n Send the mention/name/id of the role you want to set the muterole as.'\
        )
        embeds.append(embed)

        embed = Embed()
        embed.colour = discord.Colour.light_gray()
        embed.add_field(
            name='Can I change the name or colour of my muterole after I configure it?',
            value='Yes. As long as you set the role using `?muterole` you can edit it to whatever you wish.'
        )
        embeds.append(embed)

        embed = Embed()
        embed.colour = discord.Colour.light_gray()
        embed.add_field(
            name='How do I mute members?',
            value='\n Using the mute command, you pass in the member(s) you want to mute as the first argument.'\
                '\n The arguments after that can either be the duration followed by the reason or just simply the reason.'\
                '\n Examples: '\
                '\n `?mute @dartmern @Pickles 1 hour spamming commands`'\
                '\n `?mute @dartmern misuse of channels`'\
        )
        embeds.append(embed)

        embed = Embed()
        embed.colour = discord.Colour.blue()
        embed.add_field(
            name='How do I search through documentation with the `rtfm` command?',
            value='\n Using the rtfm command, you pass in the library you want to search as the subcommand, then your query.'\
                '\n You can view all the accepted documentation types with `?help rtfm`'\
                '\n Example: `?rtfm python Dict`'\
                '\n :mag: **Tip:** Passing in no subcommand and a query searches through enhanced-discord.py docs.'
        )
        embeds.append(embed)

        embed = Embed()
        embed.colour = discord.Colour.orange()
        embed.add_field(
            name='How do I view my message stats?',
            value='\n Messages sent in this guild: `?messages_guild`'\
                '\n Messages a member has sent in this guild: `?messages [member]`'\
                '\n Messages a user has sent globally: `?messages_global [user]`'\
                '\n Messages I have seen globally use: `?messages_total`'\
                '\n :warning: I can only tracking messages in channels I can see and guilds that I am in.'
        )
        embeds.append(embed)

        await ctx.send(embeds=embeds)

    
    @commands.Cog.listener()
    async def on_message(self, message : discord.Message):

        if 788543184082698252 in map(int, message.mentions):
            await message.add_reaction("\U0001f440")

    @commands.command()
    @commands.check(Cooldown(3, 8, 3, 8, commands.BucketType.guild))
    @in_support()
    async def ping_staff(self, ctx : MyContext, *, question : str):
        """
        Ping staff with a question!
        
        I'm completely fine with you bothering me 👍
        """
        if isinstance(ctx.channel, discord.Thread):
            raise commands.BadArgument("This cannot be used in a thread.")

        await ctx.message.add_reaction('👍')

        embed = Embed()
        embed.colour = discord.Colour.red()
        embed.set_author(name=ctx.author, icon_url=ctx.author.display_avatar.url)
        embed.description = question[0:1800]
        embed.set_footer(text=f'ID: {ctx.author.id} | Asked at ')
        embed.timestamp = ctx.message.created_at
        
        message = await ctx.send(f"<a:mtyping:904156199967158293> Submitting question to moderators...")

        thread = await ctx.channel.create_thread(name=f"🙋{ctx.author.name[0:10]}-{ctx.author.discriminator}", message=message)

        await thread.send(f'<@&814018291353124895> - Assistance is needed! {ctx.author.mention}', embed=embed, allowed_mentions=discord.AllowedMentions(roles=True))
        await message.edit(f"{self.bot.check} Created {thread.mention}", delete_after=5)

    @commands.command()
    @commands.has_role(814018291353124895)
    @in_support()
    async def close(self, ctx : MyContext):
        """Close a support ticket."""

        if not '🙋' in ctx.channel.name:
            return await ctx.send("This can only be used in support tickets.", delete_after=5)

        await ctx.message.delete(silent=True)

        embed = Embed()
        embed.colour = discord.Colour.blue()
        embed.set_author(name='This channel has been moved resolved by moderators.')
        embed.description = "If your question was not answered or need more clarification please ping a staff."\
            "\nThis thread/ticket will close with 24 hours of inactivity. \nOpen a new ticket in <#869693768582979715> with `?ping_staff` if you have issues."\
            "\n\n If all your questions were answered please run `?resolved` in current thread."

        await ctx.send(embed=embed)

    @commands.command()
    @in_support()
    async def resolved(self, ctx : MyContext):
        """Archive a support ticket."""

        if not '🙋' in ctx.channel.name:
            return await ctx.send("This can only be used in support tickets.", delete_after=5)
        
        embed = Embed()
        embed.colour = discord.Colour.green()
        embed.description = "This channel has been archived. It has been marked resolved."
        await ctx.send(embed=embed)
        await ctx.channel.archive(locked=True)
    

    
def setup(bot):
    bot.add_cog(support(bot))
