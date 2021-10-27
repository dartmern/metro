import discord
from discord.ext import commands


from bot import MyContext
from utils.useful import Embed

from typing import Optional, Union
import datetime
import asyncio

def is_tester():
    def predicate(ctx):
        try:
            role = ctx.guild.get_role(861141649265262592)
        except:
            raise commands.BadArgument(f"You must have the tester role to use this command.\nJoin my support server (run `{ctx.prefix}support`) and type !tester for this to work.")
        if role in ctx.author.roles:
            return True
        else:
            raise commands.BadArgument(f'You must have the tester role to use this command.\nType `!tester` to get the role.')

    return commands.check(predicate)
        

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


class Verify(discord.ui.View):
    def __init__(self, bot) -> None:
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label='Verify', style=discord.ButtonStyle.green, custom_id='verify_button')
    async def verify_button(self, button : discord.ui.Button, interaction : discord.Interaction):
        

        await interaction.response.send_message(f'{self.bot.check} Verifying...',ephemeral=True)
        await asyncio.sleep(1.5)
        if interaction.user.created_at > (discord.utils.utcnow() - datetime.timedelta(days=3)):
            
            await interaction.user.send(f'You were kicked for being too new! (Account was created in the last 3 days)')
            await interaction.user.kick(reason='Kicked for being too new! (Account was created in the last 3 days)')

        else:
            
            role = discord.Object(id=902693712688197642)
            await interaction.user.remove_roles(role)

            await interaction.user.send(f'{self.bot.check} You were verified in Metro Support Server!')
            


        


class support(commands.Cog, description='Support only commands.'):
    def __init__(self, bot):
        self.bot = bot


    @commands.Cog.listener()
    async def on_command_completion(self, ctx):

        try:
            ctx.bot.usage[ctx.command.qualified_name] += 1
        except:
            ctx.bot.usage[ctx.command.qualified_name] = 1


    @commands.command(hidden=True)
    async def support_roles(self, ctx : MyContext):

        if ctx.author.id != self.bot.owner_id:
            return 

        await ctx.message.delete()

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

        verify_channel = self.bot.get_channel(902694707161870376)

        verify_em = Embed()
        verify_em.title = 'Welcome to Metro Support Server!'
        verify_em.description = "Please click the **Verify** button below to gain access to the server. This checks your account creation date to detect spam. If you have any issues/questions please contact a support member."
        await verify_channel.send(embed=verify_em, view=Verify(ctx.bot))



    @commands.command(hidden=True)
    @is_tester()
    async def tester(self, ctx):
        """Get the commands ready to be tested!
        
        Must be a tester to use.
        """
        await ctx.send('There are no tasks to test as of now! \nIf you want, keep an eye out on the pins and pings in this channel. You will get notified when commands are available to test.')

        


        




    
def setup(bot):
    bot.add_cog(support(bot))
