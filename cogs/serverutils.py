import datetime
import io
import json
from typing import Optional, Union
import discord
import re
import pytz
import unicodedata
import asyncpg
import unidecode
import stringcase
import humanize

from discord.ext import commands
from discord import app_commands

from bot import MetroBot
from utils.checks import can_bot_execute_role_action, can_execute_action, can_execute_role_action, can_execute_role_edit
from utils.constants import DISBOARD_ID, EMOTES
from utils.converters import ActionReason, RoleConverter
from utils.custom_context import MyContext
from utils.new_pages import SimplePageSource, SimplePages
from utils.remind_utils import FutureTime, UserFriendlyTime, human_timedelta
from utils.useful import Embed, dynamic_cooldown
from utils.parsing import RoleParser
from cogs.utility import Timer, utility

EMOJI_RE = re.compile(r"(<(a)?:[a-zA-Z0-9_]+:([0-9]+)>)") 

# Parts of lockdown/unlockdown I took from Hecate thx
# https://github.com/Hecate946/Neutra/blob/main/cogs/mod.py#L365-L477

# **old** role command (before rewrite) was from phencogs and adapted for d.py 2.0
# https://github.com/phenom4n4n/phen-cogs/blob/master/roleutils/roles.py
# for redbot btw so you might need to make adjustments

# user-info & server-info have great insparation from leo tyty
# https://github.com/LeoCx1000/discord-bots/blob/master/DuckBot/cogs/utility.py#L575-L682
# https://github.com/LeoCx1000/discord-bots/blob/master/DuckBot/cogs/utility.py#L707-L716

def role_check():
    def predicate(ctx: MyContext):
        if not ctx.author.guild_permissions.manage_roles:
            raise commands.MissingPermissions(['manage_roles'])
        if not ctx.me.guild_permissions.manage_roles:
            raise commands.BotMissingPermissions(['manage_roles'])
        return True
    return commands.check(predicate)

def role_check_interaction():
    def predicate(interaction: discord.Interaction):
        if not interaction.user.guild_permissions.manage_roles:
            raise app_commands.MissingPermissions(['manage_roles'])
        if not interaction.guild.me.guild_permissions.manage_roles:
            raise commands.BotMissingPermissions
        return True

    return app_commands.check(predicate)

class RoleInfoView(discord.ui.View):
    def __init__(self, *, ctx: MyContext, role: discord.Role):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.role = role
        self.message: discord.Message

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        
        await self.message.edit(view=self)

    async def start(self):
        """Start the view by sending a message."""

        desc = [
            self.role.mention,
            f"• __**Members:**__ {len(self.role.members)}",
            f"• __**Position:**__ {self.role.position}"
            f" • __**Color:**__ {self.role.colour}",
            f"• __**Hoisted:**__ {await self.ctx.emojify(self.role.hoist)}",
            f"• __**Mentionable:**__ {await self.ctx.emojify(self.role.mentionable)}"
            f"• __**Created:**__ {discord.utils.format_dt(self.role.created_at, 'R')}"
        ]
        if self.role.managed:
            desc.append(f"• __**Managed:**__ {await self.ctx.emojify(self.role.managed)}")
        embed = discord.Embed(color=self.role.color, title=self.role.name)
        embed.description = '\n'.join(desc)
        embed.set_footer(text=f'ID: {self.role.id}')

        self.message = await self.ctx.send(embed=embed, view=self)

    @discord.ui.button(label='Permissions')
    async def permissions_button(self, inter: discord.Interaction, button: discord.ui.Button):

        allowed, denied = [], []
        for name, value in self.role.permissions:
            name = name.replace("_", " ").replace('guild', 'server').title()
            if value:
                allowed.append(name)
            else:
                denied.append(name)
        
        await inter.response.send_message(
            f'**Allowed:** {", ".join(allowed) if allowed else "No allowed permissions."}'\
            f'\n\n**Denied:** {", ".join(denied) if denied else "No denied permissions."}', ephemeral=True
        )

    @discord.ui.button(label='Members')
    async def member_button(self, inter: discord.Interaction, button: discord.ui.Button):
        await inter.response.defer()

        fmt = [f"{member} (ID: {member.id})" for member in self.role.members]
        to_send = '\n'.join(fmt)
        if len(fmt) > 12:
            await inter.followup.send(f'Members of {self.role.mention}', file=discord.File(io.StringIO(to_send), filename='members.txt'), ephemeral=True)
        else:
            await inter.followup.send(f"Members of {self.role.mention}\n\n{to_send}", ephemeral=True)
        

class EditColorModal(discord.ui.Modal, title='Edit Role Color'):
    def __init__(self, *, default: str, view: discord.ui.View, ctx: MyContext) -> None:
        super().__init__(timeout=300)
        self._children = [
            discord.ui.TextInput(
                label='Color', 
                placeholder='Ender a hex color code or color name.', 
                default=default,
                max_length=16)
        ]
        self.view: CreateRoleView = view
        self.ctx = ctx

    async def on_submit(self, interaction: discord.Interaction):

        answer = self.children[0].value
        
        try:
            color = await commands.ColorConverter().convert(self.ctx, answer)
        except commands.BadArgument:
            await interaction.response.send_message(f'Could not convert "{answer}" to a valid color.\n> Try a hex color code or a color name.', ephemeral=True)
        
        self.view.color = color

        embed = self.view.generate_embed()
        await interaction.message.edit(embed=embed)
        await interaction.response.send_message(f'Role color set to: **{color}**', ephemeral=True)

class EditNameModal(discord.ui.Modal, title='Edit Role Name'):
    def __init__(self, *, default: str, view: discord.ui.View) -> None:
        super().__init__(timeout=300)
        self.view: CreateRoleView = view

        self._children = [
            discord.ui.TextInput(
                label='Name', 
                placeholder='Enter a role name...', 
                default=default,
                max_length=32)
        ]
        
    async def on_submit(self, interaction: discord.Interaction):
        self.view.name = self.children[0].value

        embed = self.view.generate_embed()
        await interaction.message.edit(embed=embed)
        await interaction.response.send_message(f'Role name set to: **{self.view.name}**', ephemeral=True)

class ChooseRolePermissionsSelect1(discord.ui.Select):
    async def callback(self, interaction: discord.Interaction):
        self.view: CreateRoleView

        self.view.changes_made_1 = True
        await interaction.response.defer()

class ChooseRolePermissionsSelect2(discord.ui.Select):
    async def callback(self, interaction: discord.Interaction):
        self.view: CreateRoleView

        self.view.changes_made_2 = True
        await interaction.response.defer()

class ChooseRolePermissionsView(discord.ui.View):
    def __init__(self, permissions: discord.Permissions, *, interaction: discord.Interaction, view: discord.ui.View):
        super().__init__(timeout=300)
        
        self.permissions = permissions
        self.old_interaction = interaction
        self.old_view: CreateRoleView = view

        self.changes_made_1 = False
        self.changes_made_2 = False

        perms = []
        for name, value in permissions:
            perms.append((name, value))
        

        select_1 = ChooseRolePermissionsSelect1(min_values=0, max_values=24)
        select_1.options = [discord.SelectOption(label=perm[0].replace('_', ' ').title(), value=perm[0], default=True if perm[1] else False) for perm in perms[0:24]]
            
        self.add_item(select_1)

        select_2 = ChooseRolePermissionsSelect2(min_values=0, max_values=17)
        select_2.options = [discord.SelectOption(label=perm[0].replace('_', ' ').title(), value=perm[0], default=True if perm[1] else False) for perm in perms[24:]]
        self.add_item(select_2)

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green)
    async def confirm_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Called when the user confirms the permissions they want."""

        perms = []
        for name, value in self.permissions:
            perms.append((name, value))

        first_values = [perm for perm, value in perms[0:24] if value] if not self.changes_made_1 else self.children[2].values
        second_values = [perm for perm, value in perms[24:] if value] if not self.changes_made_2 else self.children[3].values

        selected = first_values + second_values
        permissions = discord.Permissions()

        print(selected)

        for perm in selected:
            setattr(permissions, perm, True)

        self.old_view.permissions = permissions
        perms = []
        for name, value in permissions:
            if value:
                perms.append(name.replace("_", " ").replace('guild', 'server').title())

        embed = self.old_view.generate_embed()
        await self.old_interaction.message.edit(embed=embed)
        await self.old_interaction.edit_original_response(content=f'Permissions set to: {", ".join(perms)}', view=None)

    @discord.ui.button(label='Reset', style=discord.ButtonStyle.red)
    async def reset_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Called when the user wants to reset the select menu's options."""
        
        await interaction.response.defer()
        self.__init__(discord.Permissions(), interaction=self.old_interaction, view=self.old_view) # re does init to reset perms
        await self.old_interaction.edit_original_response(view=self) 

        
class CreateRoleView(discord.ui.View):
    def __init__(self, *, ctx: MyContext, role: Optional[discord.Role] = None):
        super().__init__(timeout=300)
        
        self.ctx = ctx
        self.role = role

        # default options
        self.name = 'new role' if not self.role else self.role.name
        self.color = discord.Color.default() if not self.role else self.role.color
        self.permissions = discord.Permissions() if not self.role else self.role.permissions
        self.hoist = False if not self.role else self.role.hoist
        self.mentionable = False if not self.role else self.role.mentionable

    def generate_embed(self) -> discord.Embed:
        """Generate the embed to edit along with the view."""

        embed = discord.Embed(color=self.color)
        embed.add_field(name='Name', value=self.name)
        embed.add_field(name='Color', value=str(self.color))
        embed.add_field(name='Hoisted', value=str(self.hoist), inline=True)
        embed.add_field(name='Mentionable', value=str(self.mentionable), inline=True)

        permissions = []
        for name, value in self.permissions:
            name = name.replace("_", " ").replace('guild', 'server').title()
            if value:
                permissions.append(name)

        embed.add_field(
            name='Permissions', 
            value=f'{", ".join(permissions) if permissions else "No permissions set."}',
            inline=False)
        embed.set_footer(text='Click the Confirm button to save your changes.')

        return embed

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        
        await self.message.edit(view=self)

    async def start(self):
        """Start the embed/view."""

        self.message = await self.ctx.send(embed=self.generate_embed(), view=self)

    @discord.ui.button(label='Edit name', emoji='\U0001f6e0', row=0)
    async def edit_name_button(self, inter: discord.Interaction, button: discord.ui.Button):
        
        modal = EditNameModal(default=self.name, view=self)
        await inter.response.send_modal(modal)


    @discord.ui.button(label='Edit color', emoji='\U0001f6e0', row=0)
    async def edit_color_button(self, inter: discord.Interaction, button: discord.ui.Button):

        modal = EditColorModal(default=str(self.color), view=self, ctx=self.ctx)
        await inter.response.send_modal(modal)

    @discord.ui.button(label='Edit permissions', emoji='\U0001f6e0', row=0)
    async def edit_permissions_button(self, inter: discord.Interaction, button: discord.ui.Button):
        
        view = ChooseRolePermissionsView(self.permissions, interaction=inter, view=self)
        await inter.response.send_message('Select the role permissions you want:', ephemeral=True, view=view)

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green, row=1)
    async def confirm_button(self, inter: discord.Interaction, button: discord.ui.Button):
        
        if self.role:
            strategy = self.role.edit
        else:
            strategy = self.ctx.guild.create_role

        try:
            role = await strategy(
                name=self.name, 
                permissions=self.permissions, 
                color=self.color,
                mentionable=self.mentionable,
                hoist=self.hoist)
        except (discord.HTTPException, discord.Forbidden) as e:
            await inter.response.send_message(content=f'Had an issue with this role: {e}', ephemeral=True)
            await inter.message.edit(view=None)
            return

        word = 'Edited' if self.role else 'Created'
        embed = self.generate_embed()
        embed.set_footer(text=f'ID: {role.id}')
        await inter.message.edit(embed=embed, content=f'{word} the role {role.mention}.', view=None)

    @discord.ui.button(label='Toggle Hoist', emoji='\U0001f199', row=1)
    async def toggle_hoist(self, inter: discord.Interaction, button: discord.ui.Button):

        if self.hoist:
            self.hoist = False
        else:
            self.hoist = True

        embed = self.generate_embed()
        await inter.message.edit(embed=embed)
        await inter.response.defer()

    @discord.ui.button(label='Toggle Mentionable', emoji='<:mention:1025615653798952992>', row=1)
    async def toggle_mentionable(self, inter: discord.Interaction, button: discord.ui.Button):

        if self.mentionable:
            self.mentionable = False
        else:
            self.mentionable = True

        embed = self.generate_embed()
        await inter.message.edit(embed=embed)
        await inter.response.defer()


class AddRoleView(discord.ui.View):
    def __init__(self, member: discord.Member, role: discord.Role, *, author: discord.Member):
        super().__init__(timeout=180)

        self.member = member
        self.role = role
        self.message: discord.Message
        self.author = author

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True

        await self.message.edit(view=self)

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id == self.author.id:
            return True
        await interaction.response.send_message('This button cannot be used by you, sorry!', ephemeral=True)
        return False
        
    @discord.ui.button(label='Add role', emoji='<:mplus:904450883633426553>', style=discord.ButtonStyle.green)
    async def add_role_button(self, inter: discord.Interaction, button: discord.ui.Button):
        
        await inter.response.defer() # not responding with a resp but with a message edit

        try:
            await self.member.add_roles(self.role, reason=f'Role command invoked by: {inter.user} (ID: {inter.user.id})')
        except discord.HTTPException as e:
            return await inter.followup.send(f"Had trouble adding this role: {e}", ephemeral=True)

        view = RemoveRoleView(self.member, self.role, author=self.author)
        view.message = inter.message
        await inter.message.edit(content=f'Added **{self.role.name}** to **{self.member}**', view=view)


class RemoveRoleView(discord.ui.View):
    def __init__(self, member: discord.Member, role: discord.Role, *, author: discord.Member):
        super().__init__(timeout=180)

        self.member = member
        self.role = role
        self.message: discord.Message
        self.author = author

    async def on_timeout(self) -> None:
        for item in self.children:
            item.disabled = True

        await self.message.edit(view=self)

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id == self.author.id:
            return True
        await interaction.response.send_message('This button cannot be used by you, sorry!', ephemeral=True)
        return False
        
    @discord.ui.button(label='Remove role', emoji='<:mminus:904450883587276870>', style=discord.ButtonStyle.red)
    async def remove_role_button(self, inter: discord.Interaction, button: discord.ui.Button):
        
        await inter.response.defer() # not responding with a resp but with a message edit

        try:
            await self.member.remove_roles(self.role, reason=f'Role command invoked by: {inter.user} (ID: {inter.user.id})')
        except discord.HTTPException as e:
            return await inter.followup.send(f"Had trouble removing this role: {e}", ephemeral=True)

        view = AddRoleView(self.member, self.role, author=self.author)
        view.message = inter.message
        await inter.message.edit(content=f'Removed **{self.role.name}** from **{self.member}**', view=view)

class CancelBulkRoleOperationView(discord.ui.View):
    def __init__(
        self, *, view: discord.ui.View, 
        message: discord.InteractionMessage, ctx: MyContext):
        super().__init__(timeout=300)
        
        self.view: BulkRoleView = view
        self.message = message
        self.ctx = ctx

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id == self.ctx.author.id:
            return True
        await interaction.response.send_message('This button cannot be used by you, sorry!', ephemeral=True)
        return False

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.red)
    async def cancel_button_(self, inter: discord.Interaction, button: discord.ui.Button):
        """Called when a user wants to cancel bulk role operation."""

        self.view.operation_running = False
        await inter.response.defer()

class BulkRoleView(discord.ui.View):
    def __init__(self, *, ctx: MyContext, role: discord.Role):
        super().__init__(timeout=300)

        self.ctx = ctx
        self.bot: MetroBot = ctx.bot
        self.role = role
        self.message: discord.Message

        # if roles are being assigned at the moment
        # this *can* be changed in CancelBulkRoleOptionView
        self.operation_running: bool = False

        # amount of roles added
        # this is used in CancelBulkRoleOptionView
        self.added_amount: int = 0

        self.failed: int = 0
        self.already_has: int = 0

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.id == self.ctx.author.id:
            return True
        await interaction.response.send_message('This button cannot be used by you, sorry!', ephemeral=True)
        return False

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

        await self.message.edit(view=self) 

    async def enable_buttons(self):
        for item in self.children:
            if item._provided_custom_id:
                continue
            item.disabled = False
        
        await self.message.edit(view=self)

    async def start(self):
        """Start the embed/view."""   

        embed = self.generate_embed()
        self.message = await self.ctx.send(embed=embed, view=self)

    def generate_embed(self) -> discord.Embed:
        """Generate the embed to edit along with the view."""

        embed = discord.Embed(color=discord.Color.og_blurple())
        embed.description = f'Choose **who** you want to bulk add/remove {self.role.mention}.'
        embed.add_field(
            name='All (Humans + Bots)', 
            value=f'{self.bot.emotes["members"]}: Add to all\n{self.bot.emotes["members_r"]}: Remove from all')
        embed.add_field(
            name='Humans',
            value=f'\U0001f465: Add to humans\n{self.bot.emotes["humans_r"]}: Remove from humans')
        embed.add_field(
            name='Bots',
            value=f'{self.bot.emotes["bot"]}: Add to bots\n{self.bot.emotes["bot_r"]}: Remove from bots')
        
        return embed

    async def apply_bulk_action(self, who: str, removal: bool, *, inter: discord.Interaction):
        """Apply the bulk role action.""" 

        if who == 'bots':
            group = [member for member in self.ctx.guild.members if member.bot]
        if who == 'humans':
            group = [member for member in self.ctx.guild.members if not member.bot]
        if who == 'members':
            group = self.ctx.guild.members

        removal_term = 'remove' if removal else 'add'
        grammer_term = 'from' if removal else 'to'

        message = None
        if len(group) > 5:
            member_dt = discord.utils.utcnow() + datetime.timedelta(seconds=len(group) * 0.75)
            duration = human_timedelta(member_dt)
            message = f'\n*\U00002139 This should take {duration} in ideal conditions.*'
        
        confirm = await self.ctx.confirm(
            message=f'Are you sure you want to {removal_term} {self.role.mention} {grammer_term} {len(group):,} {who}?{message if message else ""}',
            delete_after=False,
            interaction=inter, ephemeral=False)
        if not confirm.value:
            await confirm.message.delete()
            return

        await self.on_timeout() # disables all the buttons

        view = CancelBulkRoleOperationView(view=self, message=confirm.message, ctx=self.ctx)
        await confirm.message.edit(content=f'{removal_term.capitalize().rstrip("e")}ing {self.role.mention} {grammer_term} {len(group):,} {who}', view=view)

        self.operation_running = True # start the operation
        for member in group:
            if self.operation_running is False:
                break

            if removal:
                action = member.remove_roles
            else:
                action = member.add_roles

            if not can_execute_action(self.ctx, self.ctx.author, member):
                self.failed += 1
                continue
            
            if removal:
                if self.role not in member.roles:
                    self.already_has += 1
                    continue
            else:
                if self.role in member.roles:
                    self.already_has += 1
                    continue
            
            try:
                await action(self.role, reason=f'Role {removal_term} all {who} command issued by: {inter.user} (ID: {inter.user.id})')
                self.added_amount += 1
            except discord.HTTPException:
                self.failed += 1
        self.operation_running = False

        embed = discord.Embed(color=discord.Color.og_blurple())
        if self.added_amount > 0:
            embed.add_field(name='Success', value=f'{removal_term.capitalize().rstrip("e")}ed {self.role.mention} {grammer_term} {self.added_amount:,}/{len(group):,} {who}.')
        
        already_had_term = 'already had' if not removal else 'didn\'t have'

        if self.already_has > 0:
            embed.add_field(name=already_had_term.capitalize(), value=f'{self.already_has:,} {who} {already_had_term} the role {self.role.mention}')
        if self.failed > 0:
            embed.add_field(name='Failed', value=f'Failed to {removal_term} {self.role.mention} {grammer_term} {self.failed:,} {who} due to role hierarchy or permission errors.')
        if not embed.fields:
            embed.description = f'Did not {removal_term} any roles {grammer_term} members due to a canceled operation or an internal error.'

        self.__init__(ctx=self.ctx, role=self.role) # basically resets all the counters

        await confirm.message.edit(embed=embed, view=None, content=None)
        await self.enable_buttons()


    @discord.ui.button(disabled=True, label='\u2800', custom_id='placeholderbutton_1')
    async def placeholder_one(self, inter, button):
        pass # this should never get called

    @discord.ui.button(emoji='<:members:908483589157576714>')
    async def members_callback(self, inter: discord.Interaction, button: discord.ui.Button):
        await self.apply_bulk_action('members', False, inter=inter)

    @discord.ui.button(emoji='<:members_r:1025995724254629959>')
    async def memebrs_r_callback(self, inter: discord.Interaction, button: discord.ui.Button):
        await self.apply_bulk_action('members', True, inter=inter)

    @discord.ui.button(disabled=True, label='\u2800', custom_id='placeholderbutton_2')
    async def placeholder_two(self, inter, button):
        pass # this should never get called

    @discord.ui.button(emoji='\U0001f465', row=1)
    async def humans_callback(self, inter: discord.Interaction, button: discord.ui.Button):
        await self.apply_bulk_action('humans', False, inter=inter)

    @discord.ui.button(emoji='<:humans_r:1025996848252588083>', row=1)
    async def humans_r_callback(self, inter: discord.Interaction, button: discord.ui.Button):
        await self.apply_bulk_action('humans', True, inter=inter)

    @discord.ui.button(emoji='<:bot:965850583766536232>', row=1)
    async def bot_callback(self, inter: discord.Interaction, button: discord.ui.Button):
        await self.apply_bulk_action('bots', False, inter=inter)

    @discord.ui.button(emoji='<:bot_r:1025997934237597707>', row=1)
    async def bot_r_callback(self, inter: discord.Interaction, button: discord.ui.Button):
        await self.apply_bulk_action('bots', True, inter=inter)

async def setup(bot: MetroBot):
    await bot.add_cog(serverutils(bot))

class serverutils(commands.Cog, description='Server utilities like role, lockdown, nicknames.'):
    def __init__(self, bot: MetroBot):
        self.bot = bot
        self.default_message = "It's been 2 hours since the last successful bump, may someone run `!d bump`?"
        self.default_thankyou = "Thank you for bumping the server! Come back in 2 hours to bump again."

        self.afk_users: dict[int, bool] = {}

    role_group = app_commands.Group(name='role', description='Base command for managing role related things.')

    @property
    def emoji(self) -> str:
        return '📓'

    @commands.Cog.listener()
    async def on_serverlockdown_timer_complete(self, timer):
        await self.bot.wait_until_ready()
        guild_id, author_id = timer.args

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return # fuck

        author = guild.get_member(author_id)
        if not author:
            try:
                author = await self.bot.fetch_user(author_id)
            except discord.HTTPException:
                author = None
            if not author:
                author = "Mod ID: %s" % author_id
            else:
                author = f"{author} (ID: {author.id})"
        else:
            author = f"{author} (ID: {author.id})"

        perms = guild.default_role.permissions
        perms.update(send_messages=True)

        try:
            await guild.default_role.edit(permissions=perms, reason=f'Automatic unlockdown by {author}') 
        except:
            pass

    @commands.Cog.listener()
    async def on_lockdown_timer_complete(self, timer):
        await self.bot.wait_until_ready()
        guild_id, mod_id, channel_id = timer.args
        perms = timer.kwargs["perms"]

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            # RIP
            return

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            # RIP
            return

        moderator = guild.get_member(mod_id)
        if moderator is None:
            try:
                moderator = await self.bot.fetch_user(mod_id)
            except:
                # request failed somehow
                moderator = f"Mod ID {mod_id}"
            else:
                moderator = f"{moderator} (ID: {mod_id})"
        else:
            moderator = f"{moderator} (ID: {mod_id})"

        reason = (
            f"Automatic unlock from timer made on {timer.created_at} by {moderator}."
        )
        overwrites = channel.overwrites_for(guild.default_role)
        overwrites.send_messages = perms
        await channel.set_permissions(
            guild.default_role,
            overwrite=overwrites,
            reason=reason,
        )

    @commands.group(name="lockdown", brief="Lockdown a channel.", aliases=["lock"], invoke_without_command=True, case_insensitive=True)
    @commands.has_permissions(send_messages=True, manage_channels=True)
    @commands.bot_has_permissions(send_messages=True, manage_channels=True)
    async def lockdown_cmd(
            self, ctx : MyContext,
            channel : Optional[discord.TextChannel] = None, *,
            duration : UserFriendlyTime(commands.clean_content, default='\u2026') = None):
        """
        Locks down a channel by changing permissions for the default role.
        This will not work if your server is set up improperly.
        """
        channel = channel or ctx.channel
        await ctx.typing()

        if not channel.permissions_for(ctx.guild.me).read_messages:
            raise commands.BadArgument(
                f"I need to be able to read messages in {channel.mention}"
            )
        if not channel.permissions_for(ctx.guild.me).send_messages:
            raise commands.BadArgument(
                f"I need to be able to send messages in {channel.mention}"
            )

        query = """
                SELECT (id)
                FROM reminders
                WHERE event = 'lockdown'
                AND EXTRA->'kwargs'->>'channel_id' = $1; 
                """
        data = await self.bot.db.fetchval(query, str(channel.id))
        if data:
            raise commands.BadArgument(f"{self.bot.cross} Channel {channel.mention} is already locked.")
        
        overwrites = channel.overwrites_for(ctx.guild.default_role)
        perms = overwrites.send_messages
        if perms is False:
            raise commands.BadArgument(f"{self.bot.cross} Channel {channel.mention} is already locked.")

        reminder_cog = self.bot.get_cog('utility')
        if not reminder_cog:
            raise commands.BadArgument(f'This feature is currently unavailable.')

        message = await ctx.send(f'Locking {channel.mention} ...')
        bot_perms = channel.overwrites_for(ctx.guild.me)
        if not bot_perms.send_messages:
            bot_perms.send_messages = True
            await channel.set_permissions(
                ctx.guild.me, overwrite=bot_perms, reason="For channel lockdown."
            )

        endtime = duration.dt.replace(tzinfo=None) if duration and duration.dt else None

        if endtime:
            await reminder_cog.create_timer(
                endtime,
                "lockdown",
                ctx.guild.id,
                ctx.author.id,
                ctx.channel.id,
                perms=perms,
                channel_id=channel.id,
                connection=self.bot.db,
                created=ctx.message.created_at.replace(tzinfo=None)
            )
        overwrites.send_messages = False
        reason = "Channel locked by command."
        await channel.set_permissions(
            ctx.guild.default_role,
            overwrite=overwrites,
            reason=await ActionReason().convert(ctx, reason),
        )

        if duration and duration.dt:
            timefmt = human_timedelta(endtime)
        else:
            timefmt = None
        
        ft = f" for {timefmt}" if timefmt else ""
        await message.edit(content=f'{self.bot._check} Channel {channel.mention} locked{ft}')

    @lockdown_cmd.command(name='server', aliases=['guild'])
    @commands.has_permissions(manage_guild=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def lockdown_server(self, ctx: MyContext, *, 
                        duration: UserFriendlyTime(commands.clean_content, default='\u2026') = None):
        """Lockdown the entire guild."""
        
        async with ctx.typing():
            query = """
                    SELECT (id, extra)
                    FROM reminders
                    WHERE event = 'serverlockdown'
                    AND extra->'kwargs'->>'guild_id' = $1;
                    """
            data = await self.bot.db.fetchval(query, str(ctx.guild.id))
            if data:
                raise commands.BadArgument("The server is already locked.")

            overwrites = ctx.guild.default_role.permissions.send_messages
            if overwrites is False:
                raise commands.BadArgument("This server is already locked.")

            reminder_cog: utility = self.bot.get_cog("utility")
            if not reminder_cog:
                raise commands.BadArgument("This feature is currently unavailable.")

            message = await ctx.send("Locking the server...")

            perms = ctx.guild.default_role.permissions
            perms.update(send_messages=False)

            await ctx.guild.default_role.edit(permissions=perms, reason=f'Server lockdown by {ctx.author} (ID: {ctx.author.id})') 

            endtime = duration.dt.replace(tzinfo=None) if duration and duration.dt else None
            if endtime:
                await reminder_cog.create_timer(
                    endtime,
                    "serverlockdown",
                    ctx.guild.id,
                    ctx.author.id,
                    guild_id=ctx.guild.id,
                    connection=self.bot.db,
                    created=discord.utils.utcnow().replace(tzinfo=None)
                )      
            
            if duration and duration.dt:
                timefmt = human_timedelta(endtime)
            else:
                timefmt = None

            ft = f" for {timefmt}" if timefmt else ""
            await message.edit(content=f"{self.bot.emotes['check']} Server locked{ft}")
        
    @commands.group(name="unlockdown", brief="Unlock a channel.", aliases=["unlock"], invoke_without_command=True, case_insensitive=True)
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(send_messages=True, manage_channels=True)
    async def unlockdown_cmd(self,
                           ctx : MyContext, *,
                           channel: discord.TextChannel = None):
        """
        Unlocks down a channel by changing permissions for the default role.
        This will not work if your server is set up improperly
        """

        channel = channel or ctx.channel

        await ctx.typing()
        if not channel.permissions_for(ctx.guild.me).read_messages:
            raise commands.BadArgument(
                f"I need to be able to read messages in {channel.mention}"
            )
        if not channel.permissions_for(ctx.guild.me).send_messages:
            raise commands.BadArgument(
                f"I need to be able to send messages in {channel.mention}"
            )

        query = """
                SELECT (id, extra)
                FROM reminders
                WHERE event = 'lockdown'
                AND extra->'kwargs'->>'channel_id' = $1;
                """
        s = await self.bot.db.fetchval(query, str(channel.id))
        if not s:
            overwrites = channel.overwrites_for(ctx.guild.default_role)
            perms = overwrites.send_messages
            if perms is None:
                return await ctx.send(f"Channel {channel.mention} is already unlocked.")
            else:
                pass   
        else:
            pass
           
        message = await ctx.send(f"Unlocking {channel.mention} ...")
        if s:
            task_id = s[0]
            args_and_kwargs = json.loads(s[1])
            perms = args_and_kwargs["kwargs"]["perms"]
            

            query = """
                    DELETE FROM reminders
                    WHERE id = $1
                    """
            await self.bot.db.execute(query, task_id)
        reason = "Channel unlocked by command execution."

        overwrites = channel.overwrites_for(ctx.guild.default_role)
        overwrites.send_messages = None
        await channel.set_permissions(
            ctx.guild.default_role,
            overwrite=overwrites,
            reason=await ActionReason().convert(ctx, reason),
        )
        await message.edit(
            content=f"{self.bot._check} Channel {channel.mention} unlocked."
        )

    @unlockdown_cmd.command(name='server', aliases=['guild'])
    @commands.has_permissions(manage_guild=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def unlockdown_server(self, ctx: MyContext):
        """Unlocked the entire guild."""

        query = """
                SELECT (id, extra)
                FROM reminders
                WHERE event = 'serverlockdown'
                AND extra->'kwargs'->>'guild_id' = $1;
                """
        s = await self.bot.db.fetchval(query, str(ctx.guild.id))
        if not s:
            if ctx.guild.default_role.permissions.send_messages:
                raise commands.BadArgument("This server is already unlocked.")
            else:
                pass
    
        message = await ctx.send("Unlocking...")
        if s:
            task_id = s[0]
            args_and_kwargs = json.loads(s[1])
            
            query = """
                    DELETE FROM reminders
                    WHERE id = $1
                    """
            await self.bot.db.execute(query, task_id)

        perms = ctx.guild.default_role.permissions
        perms.update(send_messages=True)

        await ctx.guild.default_role.edit(permissions=perms, reason=f'Server unlockdown by {ctx.author} (ID: {ctx.author.id})') 
        await message.edit(content=f'{self.bot.emotes["check"]} Unlocked the server.')

    async def cleanup_code(self, content):
        """Automatically removes code blocks from the code."""
        # remove ```py\n```
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])

        # remove `foo`
        return content.strip('` \n')

    async def show_roleinfo(self, ctx: MyContext, role: discord.Role):
        if role.guild.chunked is False:
            await role.guild.chunk()

        desc = [
            role.mention,
            f"• __**Members:**__ {len(role.members)}",
            f"• __**Position:**__ {role.position}"
            f"• __**Color:**__ {role.colour}",
            f"• __**Hoisted:**__ {await ctx.emojify(role.hoist)}",
            f"• __**Mentionable:**__ {await ctx.emojify(role.mentionable)}"
            f"• __**Created:**__ {discord.utils.format_dt(role.created_at, 'R')}"
        ]
        if role.managed:
            desc.append(f"• __**Managed:**__ {role.managed}")
        
        embed = Embed()
        embed.colour = role.colour
        embed.title = role.name
        embed.description = "\n".join(desc)
        embed.set_footer(text=f"ID: {role.id}")

        return embed

    async def role_toggle(self, ctx: MyContext, member: discord.Member, role: discord.Role):
        
        if not (await can_execute_role_action(ctx, ctx.author, member, role)):
            return

        if role in member.roles:
            await ctx.invoke(self._role_remove, member=member, role=role)
            return
        elif role not in member.roles:
            await ctx.invoke(self._role_add, member=member, role=role)
            return
        else:
            await ctx.help()

    async def _role_add(self, ctx: MyContext, member: discord.Member, role: discord.Role):

        if not (await can_execute_role_action(ctx, ctx.author, member, role)):
            return 

        if role in member.roles:
            view = RemoveRoleView(member, role, author=ctx.author)
            view.message = await ctx.send(f"**{member}** already has that role. Try removing it instead.", view=view)
            return

        try:
            await member.add_roles(role, reason=f'Role command invoked by: {ctx.author} (ID: {ctx.author.id})')
        except discord.HTTPException as e:
            return await ctx.send(f"Had trouble adding this role: {e}")

        view = RemoveRoleView(member, role, author=ctx.author)
        view.message = await ctx.send(f"Added **{role.name}** to **{member}**", view=view)

    async def _role_remove(self, ctx: MyContext, member: discord.Member, role: discord.Role):

        if not (await can_execute_role_action(ctx, ctx.author, member, role)):
            return 

        if not role in member.roles:
            view = AddRoleView(member, role, author=ctx.author)
            view.message = await ctx.send(f"**{member}** doesn't have that role. Try adding it instead.", view=view)
            return

        try:
            await member.remove_roles(role, reason=f'Role command invoked by: {ctx.author} (ID: {ctx.author.id})')
        except discord.HTTPException as e:
            return await ctx.send(f"Had trouble removing this role: {e}")

        view = AddRoleView(member, role, author=ctx.author)
        view.message = await ctx.send(f"Removed **{role.name}** from **{member}**", view=view)

    async def _role_list(self, ctx: MyContext):

        fmt = [
            f"`{role.position}` - {role.id} - `{role.color}` - {role.mention}" 
            for role in list(ctx.guild.roles)[::-1]]

        source = SimplePageSource(entries=list(fmt), per_page=9)
        menu = SimplePages(source=source, ctx=ctx, compact=True)
        
        await menu.start()

    async def _role_delete(self, ctx: MyContext, role: discord.Role) -> None:
        if not (await can_execute_role_edit(ctx, role)):
            return 
        if not (await can_bot_execute_role_action(ctx, role)):
            return 

        confirm = await ctx.confirm(
            f'Are you sure you want to delete {role.mention}?',
            delete_after=False,
            interaction=ctx.interaction if ctx.interaction else None)
        if not confirm.value:
            await confirm.message.edit(content='Canceled.', view=None)
            return 

        try:
            await role.delete(reason=f'Role delete command invoked by: {ctx.author.id} (ID: {ctx.author.id})')
        except discord.HTTPException as e:
            await confirm.message.edit(content=f'Error deleting role: {e}')
            return 

        await confirm.message.edit(content=f'{self.bot._check} Deleted the role **{role.name}**', view=None)

    @commands.group(invoke_without_command=True, name='role')
    @role_check()
    async def _role(self, ctx: MyContext, member: discord.Member, *, role: RoleConverter):
        """Toggle a role for a member."""

        await self.role_toggle(ctx, member, role) 

    @_role.command(name='add')
    @role_check()
    async def _role_add_command(self, ctx: MyContext, member: discord.Member, *, role: RoleConverter):
        """Add a role to a member."""

        await self._role_add(ctx, member, role)

    @_role.command(name='remove')
    @role_check()
    async def _role_remove_command(self, ctx: MyContext, member: discord.Member, *, role: RoleConverter):
        """Remove a role from a member."""

        await self._role_remove(ctx, member, role)

    @_role.command(name='create')
    @role_check()
    async def _role_create_command(self, ctx: MyContext):
        """Create a new role."""

        view = CreateRoleView(ctx=ctx)
        await view.start()

    @_role.command(name='edit')
    @role_check()
    async def _role_edit_command(self, ctx: MyContext, *, role: RoleConverter):
        """Edit an existing role."""

        if not (await can_execute_role_edit(ctx, role)):
            return 
        if not (await can_bot_execute_role_action(ctx, role)):
            return 

        view = CreateRoleView(ctx=ctx, role=role)
        await view.start()

    @_role.command(name='bulk')
    @role_check()
    async def _role_bulk_command(self, ctx: MyContext, *, role: RoleConverter):
        """Bulk add/remove roles to guild members/bots."""

        if not (await can_bot_execute_role_action(ctx, role)):
            return 

        view = BulkRoleView(ctx=ctx, role=role)
        await view.start()

    @_role.command(name='info')
    async def _role_info_command(self, ctx: MyContext, *, role: RoleConverter):
        """Display information on a role."""

        view = RoleInfoView(ctx=ctx, role=role)
        await view.start()

    @_role.command(name='list')
    async def _role_list_command(self, ctx: MyContext):
        """Displays the server's roles."""

        await self._role_list(ctx)

    @_role.command(name='delete')
    async def _role_delete_command(self, ctx: MyContext, *, role: RoleConverter):
        """Delete a role."""

        await self._role_delete(ctx, role)

    @role_group.command(name='toggle')
    @role_check_interaction()
    @app_commands.describe(member='The member you want to toggle the role.')
    @app_commands.describe(role='The role you want to toggle.')
    async def role_slash(self, inter: discord.Interaction, member: discord.Member, role: discord.Role):
        """Toggle a role for a member."""

        ctx = await self.bot.get_context(inter)
        await self.role_toggle(ctx, member, role)

    @role_group.command(name='add')
    @role_check_interaction()
    @app_commands.describe(member='The member you want to add the role to.')
    @app_commands.describe(role='The role you want to add.')
    async def role_add_slash(self, inter: discord.Interaction, member: discord.Member, role: discord.Role):
        """Add a role to a member."""

        ctx = await self.bot.get_context(inter)
        await self._role_add(ctx, member, role)

    @role_group.command(name='remove')
    @role_check_interaction()
    @app_commands.describe(member='The member you want to remove the role from.')
    @app_commands.describe(role='The role you want to remove.')
    async def role_remove_slash(self, inter: discord.Interaction, member: discord.Member, role: discord.Role):
        """Remove a role from a member."""

        ctx = await self.bot.get_context(inter)
        await self._role_remove(ctx, member, role)

    @role_group.command(name='create')
    @role_check_interaction()
    async def role_create_slash(self, inter: discord.Interaction):
        """Create a new role."""

        ctx = await self.bot.get_context(inter)

        view = CreateRoleView(ctx=ctx)
        await view.start()

    @role_group.command(name='edit')
    @role_check_interaction()
    @app_commands.describe(role='The role you want to edit.')
    async def role_edit_slash(self, inter: discord.Interaction, role: discord.Role):
        """Edit an existing role."""

        ctx = await self.bot.get_context(inter)
        if not (await can_execute_role_edit(ctx, role)):
            return 

        view = CreateRoleView(ctx=ctx, role=role)
        await view.start()

    @role_group.command(name='bulk')
    @role_check_interaction()
    @app_commands.describe(role='The role you want to bulk add/remove.')
    async def role_bulk_slash(self, inter: discord.Interaction, role: discord.Role):
        """Bulk add or remove roles to guild members/bots."""

        ctx = await self.bot.get_context(inter)
        if not (await can_bot_execute_role_action(ctx, role)):
            return 

        view = BulkRoleView(ctx=ctx, role=role)
        await view.start()

    @role_group.command(name='info')
    @app_commands.describe(role='The role you want to view information on.')
    async def role_info_slash(self, inter: discord.Interaction, role: discord.Role):
        """Display information on a role."""

        ctx = await self.bot.get_context(inter)

        view = RoleInfoView(ctx=ctx, role=role)
        await view.start()

    @role_group.command(name='list')
    async def role_list_slash(self, inter: discord.Interaction):
        """Displays the server's roles."""

        ctx = await self.bot.get_context(inter)
        await self._role_list(ctx)

    @role_group.command(name='delete')
    @role_check_interaction()
    @app_commands.describe(role='The role you want to delete.')
    async def role_delete_slash(self, inter: discord.Interaction, role: discord.Role):
        """Delete a role."""

        ctx = await self.bot.get_context(inter)
        await self._role_delete(ctx, role)

    @commands.Cog.listener()
    async def on_temprole_timer_complete(self, timer: Timer):
        guild_id, author_id, role_id, member_id = timer.args

        await self.bot.wait_until_ready()
        
        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return # If we can't even find the guild we can't proceed

        role = guild.get_role(role_id)
        if role is None:
            return # there's nothing to add if the role is None

        member = await self.bot.get_or_fetch_member(guild, member_id)
        if member is None:
            return # member doesn't even exist

        moderator = await self.bot.get_or_fetch_member(guild, author_id)
        if moderator is None:
            try:
                moderator = await self.bot.fetch_user(author_id)
            except:
                # moderator request failed (somehow)
                moderator = f"Mod ID: {author_id}"
            else:
                moderator = f"{moderator} (ID: {author_id})"
        else:
            moderator = f'{moderator} (ID: {author_id})'

        try:
            await member.remove_roles(role, reason=f'Automatic temprole timer made on {timer.created_at} by {moderator}')
        except (discord.Forbidden, discord.HTTPException):
            pass # Either I don't have permissions at this time or removing the roles failed

    @commands.command(name='temprole', usage='<member> <duration> <role>')
    @commands.dynamic_cooldown(dynamic_cooldown, type=commands.BucketType.user)
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_guild_permissions(manage_roles=True)
    async def temprole(
        self, 
        ctx: MyContext, 
        member: discord.Member, 
        duration: FutureTime,
        *,
        role: RoleConverter
    ):
        """Adds a role to a member and removes it after the specified duration"""

        if role in member.roles:
            return await ctx.send("This member already has that role. \nIf you want to extend the temprole duration remove the role first.")

        if role.position >= ctx.guild.me.top_role.position:
            to_send = ""
            to_send += (
                f"\🔴 I am unable to remove roles due to discord hierarchy rules."
                f"\nMy top role's position ({ctx.guild.me.top_role.mention}) is lower than `@{role.name}`"
                f"\n\nMy top role position: {ctx.guild.me.top_role.position} • `@{role.name}` position: {role.position}"
                f"\n\nPlease move my top role higher to make this command work!"
            )
            raise commands.BadArgument(to_send)

        if not can_execute_action(ctx, ctx.author, member):
            return await ctx.send('You are not high enough in role hierarchy to give roles to this member.')

        reminder_cog = ctx.bot.get_cog('utility')
        if reminder_cog is None:
            return await ctx.send('This function is not available at this time. Try again later.')

        try:
            timer = await reminder_cog.create_timer(
                duration.dt,
                "temprole",
                ctx.guild.id,
                ctx.author.id,
                role.id,
                member.id,
                connection=ctx.bot.db,
                created_at=ctx.message.created_at
            )
        except Exception as e:
            return await ctx.send(str(e))

        await member.add_roles(role, reason=f'Temprole command invoked by: {ctx.author} (ID: {ctx.author.id})')

        embed = Embed()
        embed.colour = discord.Colour.blue()
        embed.description = "__**Temporary role added**__"\
            f"\n{member.mention} was granted the {role.mention} role for {human_timedelta(duration.dt+datetime.timedelta(seconds=.4), accuracy=50)}"
        await ctx.send(embed=embed)

    @staticmethod
    def is_cancerous(text: str) -> bool:
        for segment in text.split():
            for char in segment:
                if not (char.isascii() and char.isalnum()):
                    return True
        return False

    @staticmethod
    def strip_accs(text):
        try:
            text = unicodedata.normalize("NFKC", text)
            text = unicodedata.normalize("NFD", text)
            text = unidecode.unidecode(text)
            text = text.encode("ascii", "ignore")
            text = text.decode("utf-8")
        except Exception as e:
            print(e)
        return str(text)

    async def nick_maker(self, old_shit_nick: str):
        old_shit_nick = self.strip_accs(old_shit_nick)
        new_cool_nick = re.sub("[^a-zA-Z0-9 \n.]", "", old_shit_nick)
        new_cool_nick = " ".join(new_cool_nick.split())
        new_cool_nick = stringcase.lowercase(new_cool_nick)
        new_cool_nick = stringcase.titlecase(new_cool_nick)
        if len(new_cool_nick.replace(" ", "")) <= 1 or len(new_cool_nick) > 32:
            new_cool_nick = "simp name"
        return new_cool_nick

    @commands.command(aliases=['dehoist', 'dc'])
    @commands.has_guild_permissions(manage_nicknames=True)
    @commands.bot_has_guild_permissions(manage_nicknames=True)
    async def decancer(self, ctx: MyContext, *, member: discord.Member):
        """Remove special/cancerous characters from a user's nickname."""

        old_nick = member.display_name
        if not self.is_cancerous(old_nick):
            embed = Embed(color=discord.Colour.red())
            embed.description = "**%s**'s nickname is already decancered." % member
            return await ctx.send(embed=embed)

        new_nick = await self.nick_maker(old_nick)
        if old_nick.lower() != new_nick.lower():
            try:
                await member.edit(nick=new_nick, reason=f'Decancer command invoked by: {ctx.author} (ID: {ctx.author.id})')
            except discord.Forbidden:
                raise commands.BotMissingPermissions(['manage_nicknames'])
            else:
                em = Embed(title='Decancer command', color=discord.Colour.green())
                em.set_author(name=member, icon_url=member.display_avatar.url)
                em.add_field(name='Old nick', value=old_nick, inline=False)
                em.add_field(name='New nick', value=new_nick, inline=False)
                return await ctx.send(embed=em)
        else:
            embed = Embed(color=discord.Colour.red())
            embed.description = "**%s**'s nickname is already decancered." % member
            return await ctx.send(embed=embed)

    @commands.command(aliases=['nick'])
    @commands.bot_has_guild_permissions(manage_nicknames=True)
    @commands.has_guild_permissions(manage_nicknames=True)
    async def nickname(self, ctx: MyContext, member: Optional[discord.Member], *, nickname: Optional[str]):
        """Change a member's nickname. 
        
        Passing in no member will change my nickname.
        Passing in no nickname will remove a nickname if applicable.
        """
        member = member or ctx.guild.me
        await member.edit(nick=nickname, reason=f'Nickname command invoked by: {ctx.author} (ID: {ctx.author.id})')

        term = "my" if member == ctx.guild.me else f"{member.mention}'s"
        first_term = "Changed" if nickname else "Reset"
        new_nick = "." if nickname is None else " to **%s**." % nickname 

        em = Embed()
        em.set_author(name=member, icon_url=member.display_avatar.url)
        em.description = f"{first_term} {term} nickname{new_nick}"
        return await ctx.send(embed=em)

    @commands.command(name='nuke-channel', aliases=['nuke'])
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_guild_permissions(manage_channels=True)
    async def nuke_channel(self, ctx: MyContext, *, channel: Optional[discord.TextChannel]):
        """Nuke a text channel.
        
        This deletes the channel and creates the same channel again.
        """
        channel = channel or ctx.channel
        if isinstance(channel, discord.Thread):
            raise commands.BadArgument("You cannot nuke threads.")

        confirm = await ctx.confirm(f'Are you sure you want to nuke {channel.mention}', timeout=30.0, delete_after=False)
        if not confirm.value:
            await confirm.message.edit(content='Canceled/Timed out.', view=None)
            return

        new_channel = await channel.clone(name=channel.name)
        await ctx.ghost_ping(ctx.author, channel=new_channel)

        try:
            await channel.delete(reason=f'Nuke command invoked by: {ctx.author} (ID: {ctx.author.id})')
        except (discord.HTTPException, discord.Forbidden) as e:
            return await ctx.send(f"Had an issue with deleting this channel. {e}")

        await new_channel.send(f"Nuke-command ran by: {ctx.author}")

    @commands.command(name='grant', aliases=['grant-permissions'])
    @commands.has_guild_permissions(administrator=True)
    @commands.bot_has_guild_permissions(administrator=True)
    async def grant_permissions(self, ctx: MyContext, entity: Union[discord.Member, discord.Role], *perms: str):
        """
        Grant an entity certain permissions.
        
        Entity may be a member or a role.
        Make sure my top role is above that target role if entity is a role.

        If an entity is a role it edits the permissions on that role.
        If an entity is a member it edits the current channel's permissions.
        """
        
        if isinstance(entity, discord.Member):
            if not can_execute_action(ctx, ctx.author, entity):
                raise commands.BadArgument("You are not high enough in role hierarchy to grant permissions to this member.")

            overwrites = discord.PermissionOverwrite()
            perms_cleaned = []
            for perm in perms:
                if perm.lower().replace("server", "guild").replace(" ", "_") not in dict(discord.Permissions()):
                    raise commands.BadArgument(f"Invaild permission: {perm}")
                overwrites.update(**(dict(perm=True)))
                perms_cleaned.append(perm.title())
                
            overwrites = {entity: overwrites}
            
            to_send = ", ".join(["`%s`" % perm for perm in perms_cleaned])

            await ctx.channel.edit(overwrites=overwrites)
            return await ctx.send(f"Granted {to_send} to {entity}")

        elif isinstance(entity, discord.Role):
            permissions = discord.Permissions()
            if entity.position >= ctx.author.top_role.position:
                if ctx.author == ctx.guild.owner:
                    pass
                else:
                    raise commands.BadArgument("You are not high enough in role hierarchy to grant permissions to this role.")
            
            to_append = []

            for perm in perms:
                if perm not in dict(discord.Permissions()):
                    raise commands.BadArgument("Invaild permission: %s" % perm)

                setattr(permissions, perm, True)
                to_append.append(perm.title().replace("_", " "))

            to_send = ", ".join(["`%s`" % x for x in to_append])
            
            await entity.edit(permissions=permissions)
            return await ctx.send(f"Granted {to_send} to {entity}")

    async def userinfo_embed(self, ctx: MyContext, member: discord.Member):
        """This function returns a embed for a discord.Member instance."""

        embed = discord.Embed(color=member.color if member.color not in (None, discord.Color.default()) else discord.Colour.green())
        embed.set_author(name="%s's User Info" % member, icon_url=member.display_avatar.url)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text="ID: %s" % member.id)

        embed.add_field(name="\U00002139 General", value=f'__**ID:**__ {member.id} \n__**Username:**__ {member}\n__**Nickname:**__ {await ctx.emojify(member.nick)} {member.nick if member.nick else ""} \n__**Owner:**__ {self.bot._check if member.id == member.guild.owner_id else self.bot.cross} • __**Bot:**__ {await ctx.emojify(member.bot)} \n__**Join Position:**__ {sorted(ctx.guild.members, key=lambda m: m.joined_at or discord.utils.utcnow()).index(member) + 1}')

        embed.add_field(name=f'{EMOTES["inviteme"]} Created at', value=f'╰ {discord.utils.format_dt(member.created_at, "F")} ({discord.utils.format_dt(member.created_at, "R")})', inline=False)
        embed.add_field(name=f'{EMOTES["joined_at"]} Joined at', value=f'╰ {discord.utils.format_dt(member.joined_at, "F")} ({discord.utils.format_dt(member.joined_at, "R")})', inline=True)

        roles = [role.mention for role in member.roles if not role.is_default()]
        roles.reverse()
        
        if roles:
            roles = ', '.join(roles)
        else:
            roles = "This member has no roles."

        embed.add_field(name=f'{EMOTES["role"]} Roles [{len(member.roles) - 1}]', value=roles, inline=False)

        return embed
        
    async def serverinfo_embed(self, ctx: MyContext, guild: discord.Guild):
        """This function returns a embed for a discord.Guild instance."""

        if not guild.chunked:
            await ctx.typing()
            await guild.chunk()

        embed = discord.Embed(color=ctx.color)
        embed.set_author(name=guild.name, icon_url=guild.icon.url if guild.icon else None)

        embed.add_field(name='\U00002139 General', value=f"__**ID:**__ {guild.id} \n__**Owner:**__ {guild.owner if guild.owner else 'Not Found'}\n__**Verification Level:**__ {str(guild.verification_level).title()}\n__**Filesize Limit:**__ {humanize.naturalsize(guild.filesize_limit)}\n__**Role count:**__ {len(guild.roles)}")

        embed.add_field(name=f'{EMOTES["channels"]} Channels', value=f'{EMOTES["text"]} Text: {len([x for x in guild.channels if isinstance(x, discord.TextChannel)])}\n{EMOTES["voice"]} Voice: {len([x for x in guild.channels if isinstance(x, discord.VoiceChannel)])}\n{EMOTES["category"]} Category: {len([x for x in guild.channels if isinstance(x, discord.CategoryChannel)])} \n{EMOTES["stage"]} Stage: {len([x for x in guild.channels if isinstance(x, discord.StageChannel)])}')
        embed.add_field(name=f'{EMOTES["members"]} Members', value=f"\U0001f465 Humans: {len([x for x in guild.members if not x.bot])}\n{EMOTES['bot']} Bots: {len([x for x in guild.members if x.bot])}\n\U0000267e Total: {len(guild.members)}\n\U0001f4c1 Limit: {guild.max_members}", inline=True)

        embed.add_field(name=f'{EMOTES["joined_at"]} Created at', value=f"{discord.utils.format_dt(guild.created_at, 'F')} ({discord.utils.format_dt(guild.created_at, 'R')})")

        return embed

    async def channelinfo_embed(
        self, ctx: MyContext, 
        channel: Union[discord.TextChannel, discord.VoiceChannel, discord.StageChannel]):
        """This function returns a embed for a Text/Voice/Stage channel instance."""

        embed = discord.Embed(color=discord.Colour.light_gray(), title=f'#{channel.name}')
        embed.add_field(name='\U00002139 General', value=f"__**Mention:**__ {channel.mention} \n__**Name:**__ {channel.name} \n__**ID:**__ {channel.id}\n__**Type:**__ {str(channel.type).title()}\n__**Created on:**__ {discord.utils.format_dt(channel.created_at, 'F')} ({discord.utils.format_dt(channel.created_at, 'R')})")

        return embed

    @commands.command(name='user-info', aliases=['userinfo', 'ui','whois'])
    @commands.bot_has_permissions(send_messages=True)
    async def user_info(self, ctx, *, member: Optional[discord.Member]):
        """Shows all the information about the specified user/member."""
        member = member or ctx.author
        await ctx.send(embed=await self.userinfo_embed(ctx, member))

    @commands.command(name='role-info', aliases=['roleinfo', 'ri'])
    async def role_info(self, ctx: MyContext, *, role: RoleConverter):
        """Show all the information about a role."""
        await ctx.send(embed=await self.show_roleinfo(ctx, role))

    @commands.command(name='server-info', aliases=['serverinfo', 'guildinfo', 'si'])
    async def server_info(self, ctx: MyContext):
        """Show all the information about the current guild."""
        await ctx.send(embed=await self.serverinfo_embed(ctx, ctx.guild))

    @commands.command(name='channel-info', aliases=['channelinfo', 'ci'])
    async def channel_info(
        self, ctx: MyContext, *, 
        channel: Union[discord.TextChannel, discord.VoiceChannel, discord.StageChannel, None]):
        """Show all the information about a channel.
        
        This channel can be a voice or text channel."""
        channel = channel or ctx.channel
        await ctx.send(embed=await self.channelinfo_embed(ctx, channel))
        
    @commands.group(name='emoji', invoke_without_command=True, case_insensitive=True)
    async def _emoji(self, ctx: MyContext):
        """Base command for managing emojis."""
        await ctx.help()

    @_emoji.command(name='list', aliases=['show'], usage="[--ids]")
    async def emoji_list(self, ctx: MyContext, *, flags: Optional[str]):
        """List all the emojis in the guild.
        
        Apply the `--ids` flags if you want emoji ids"""

        to_paginate = []
        if flags and "--ids" in flags:
            for emoji in ctx.guild.emojis:
                to_paginate.append(f"{emoji} `:{emoji.name}:` `<{'a' if emoji.animated else ''}:{emoji.name}:{emoji.id}>`")
        else:
            for emoji in ctx.guild.emojis:
                to_paginate.append(f"{emoji} `:{emoji.name}:`")

        await ctx.paginate(to_paginate, per_page=16)


    @_emoji.command(name='add', aliases=['create', '+'])
    @commands.has_guild_permissions(manage_emojis=True)
    @commands.bot_has_guild_permissions(manage_emojis=True)
    async def emoji_add(self, ctx: MyContext, name: str, *, url: Optional[str]):
        """Add a custom emoji."""
        if ctx.message.attachments:        
            image = await ctx.message.attachments[0].read()
            try:
                discord.utils._get_mime_type_for_image(image)
            except discord.errors.InvalidArgument:
                raise commands.BadArgument("Not a vaild image or had trouble reading it.")
        else:
            if not url:
                raise commands.BadArgument("Please attach a image or a url...")
            try:
                async with self.bot.session.get(url) as resp:
                    image = await resp.read()
            except Exception as e:
                return await ctx.send(f"Had an issue reading this url: {e}")

        try:
            await ctx.guild.create_custom_emoji(
                name=name,
                image=image,
                reason=f'Emoji add command invoked by: {ctx.author} (ID: {ctx.author.id})'
            )
        except discord.HTTPException:
            raise commands.BadArgument("I have having trouble creating this emoji. Permissions error?")
        else:
            await ctx.check()

    @_emoji.command(name='remove', aliases=['delete', '-'])
    @commands.has_guild_permissions(manage_emojis=True)
    @commands.bot_has_guild_permissions(manage_emojis=True)
    async def emoji_remove(self, ctx: MyContext, *, emoji: discord.Emoji):
        """Delete a emoji."""
        if emoji.guild != ctx.guild:
            raise commands.BadArgument("The emoji needs to be in this guild.")
        try:
            await emoji.delete(reason=f'Emoji delete command invoked by: {ctx.author} (ID: {ctx.author.id})')
        except discord.HTTPException:
            raise commands.BadArgument("I have having trouble deleting this emoji. Permissions error?")
        else:
            await ctx.check()

    @_emoji.command(name='rename')
    @commands.has_guild_permissions(manage_emojis=True)
    @commands.bot_has_guild_permissions(manage_emojis=True)
    async def emoji_rename(self, ctx: MyContext, emoji: discord.Emoji, *, name: str):
        """Rename an emoji."""
        if emoji.guild != ctx.guild:
            raise commands.BadArgument("The emoji needs to be in this guild.")  
        try:
            await emoji.edit(name=name, reason=f"Emoji edit command invoked by: {ctx.author} (ID: {ctx.author.id})")
        except discord.HTTPException:
            raise commands.BadArgument("I have having trouble creating this emoji. Permissions error?")
        else:
            await ctx.check()

    @_emoji.command(name='steal')
    @commands.has_guild_permissions(manage_emojis=True)
    @commands.bot_has_guild_permissions(manage_emojis=True)
    async def emoji_steal(self, ctx: MyContext, name: str, *, message: Optional[discord.Message]):
        """Add an emoji from a specified messages."""

        if not message:
            message = getattr(ctx.message.reference, 'resolved', None)
        if not message:
            raise commands.BadArgument("Please provide a message or reply to one...")

        emoji = EMOJI_RE.search(message.content)
        if not emoji:
            raise commands.BadArgument("No emojis were founds in this message.")
        url = (
            "https://cdn.discordapp.com/emojis/"
            f"{emoji.group(3)}.{'gif' if emoji.group(2) else 'png'}?v=1"
        )
        async with self.bot.session.get(url) as r:
            data = await r.read()
        try:
            await ctx.guild.create_custom_emoji(name=name, image=data, reason=f'Emoji steal command invoked by: {ctx.author.id} (ID: {ctx.author.id})')
            await ctx.check()
        except discord.InvalidArgument:
            raise commands.BadArgument("Discord returned invaild data.")
        except discord.HTTPException:
            raise commands.BadArgument("I have having trouble creating this emoji. Permissions error?")

    @commands.group(name='bumpreminder', aliases=['bprm'])
    @commands.has_guild_permissions(manage_guild=True)
    @commands.bot_has_guild_permissions(manage_messages=True, manage_channels=True)
    async def bumpreminder(self, ctx: MyContext):
        """Set reminders to bump on Disboard."""
        if not ctx.guild.chunked:
            await ctx.guild.chunk()
        member = ctx.guild.get_member(DISBOARD_ID)
        if member not in ctx.guild.members:
            raise commands.BadArgument("Disboard doesn't seem to be in this server...")
        if not ctx.invoked_subcommand:
            await ctx.help()

    @bumpreminder.command(name='channel')
    @commands.has_guild_permissions(manage_guild=True)
    @commands.bot_has_guild_permissions(manage_messages=True, manage_channels=True)
    async def bumpreminder_channel(self, ctx: MyContext, *, channel: Optional[discord.TextChannel]):
        """Set the channel to send bump reminders to."""
        if not channel:
            await self.bot.db.execute('UPDATE bumpreminder SET channel = $1 WHERE guild_id = $2', None, ctx.guild.id)
            return await ctx.send(f"{self.bot.emotes['minus']} Toggled off bump reminders for this guild.")

        if not channel.permissions_for(ctx.guild.me).send_messages:
            await ctx.send(f'I cannot send messages in that channel')

        try:
            await self.bot.db.execute('INSERT INTO bumpreminder (guild_id, channel) VALUES ($1, $2)', ctx.guild.id, channel.id)
        except asyncpg.exceptions.UniqueViolationError:
            await self.bot.db.execute('UPDATE bumpreminder SET channel = $1 WHERE guild_id = $2', channel.id, ctx.guild.id)
        await ctx.send(f"{self.bot.emotes['plus']} Successfully set {channel.mention} as the bump reminder channel. \nI will not send my first reminders until a successful bump as registered.")

    @bumpreminder.command(name='message', aliases=['msg'])
    @commands.has_guild_permissions(manage_guild=True)
    @commands.bot_has_guild_permissions(manage_messages=True, manage_channels=True)
    async def bumpreminder_message(self, ctx: MyContext, *, message: Optional[commands.clean_content] = None):
        """Change the message used for bump reminders.
        
        Provide no message to reset back to the default message:
        > It's been 2 hours since the last successful bump, may someone run `!d bump`?
        """
        message = message or self.default_message
        try:
            await self.bot.db.execute('INSERT INTO bumpreminder (guild_id, message) VALUES ($1, $2)', ctx.guild.id, message)
        except asyncpg.exceptions.UniqueViolationError:
            await self.bot.db.execute('UPDATE bumpreminder SET message = $1 WHERE guild_id = $2', message, ctx.guild.id)

        await ctx.send(f"{self.bot.emotes['plus']} Updated the bump reminder message.")

    @bumpreminder.command(name='thankyou', aliases=['ty'])
    @commands.has_guild_permissions(manage_guild=True)
    @commands.bot_has_guild_permissions(manage_messages=True, manage_channels=True)
    async def bumpreminder_thankyou(self, ctx: MyContext, *, message: Optional[commands.clean_content] = None):
        """Change the thankyou message used for bump reminders.
        
        Provide no message to reset back to the default message:
        > Thank you for bumping the server! Come back in 2 hours to bump again.
        """
        message = message or self.default_thankyou
        try:
            await self.bot.db.execute('INSERT INTO bumpreminder (guild_id, thankyou) VALUES ($1, $2)', ctx.guild.id, message)
        except asyncpg.exceptions.UniqueViolationError:
            await self.bot.db.execute('UPDATE bumpreminder SET thankyou = $1 WHERE guild_id = $2', message, ctx.guild.id)

        await ctx.send(f"{self.bot.emotes['plus']} Updated the bump reminder thankyou message.")

    @bumpreminder.command(name='pingrole', aliases=['ping'])
    @commands.has_guild_permissions(manage_guild=True)
    @commands.bot_has_guild_permissions(manage_messages=True, manage_channels=True)
    async def bumpreminder_pingrole(self, ctx: MyContext, *, role: RoleConverter):
        """Set a role to ping for bump reminders."""
        try:
            await self.bot.db.execute('INSERT INTO bumpreminder (guild_id, pingrole) VALUES ($1, $2)', ctx.guild.id, role.id)
        except asyncpg.exceptions.UniqueViolationError:
            await self.bot.db.execute('UPDATE bumpreminder SET pingrole = $1 WHERE guild_id = $2', role.id, ctx.guild.id)

        await ctx.send(f"{self.bot.emotes['plus']} Updated the pinged role for bump reminders.")

    @bumpreminder.command(name='settings', aliases=['show'])
    @commands.has_guild_permissions(manage_guild=True)
    @commands.bot_has_guild_permissions(manage_messages=True, manage_channels=True)
    async def bumpreminder_settings(self, ctx: MyContext):
        """Show your Bump Reminder settings."""
        
        js = await self.bot.db.fetchval(
            'SELECT (channel, message, thankyou, lock, pingrole) '
            'FROM bumpreminder WHERE guild_id = $1', ctx.guild.id
        )
        if not js:
            raise commands.BadArgument("This server does not have bump reminder set up yet.")

        em = discord.Embed(color=ctx.color, title='Bump Reminder Settings')
        em.set_author(name=ctx.guild.name, icon_url=ctx.guild.icon if ctx.guild.icon else None)
        em.description = f"**Channel:** {f'<#{js[0]}>' if js[0] else 'No bump reminder channel set...'}"\
                        f"\n**Ping role:** {f'<@&{js[4]}>' if js[4] else 'No ping role set...'}"\
                        f"\n**Auto-lock channel:** {await ctx.emojify(js[3])}"
        em.add_field(name='Message', value=f"```\n{js[1] if js[1] else self.default_message}\n```", inline=False)
        em.add_field(name='Thank you message', value=f"```\n{js[2] if js[2] else self.default_thankyou}\n```", inline=False)
        await ctx.send(embed=em)

    @commands.Cog.listener('on_message')
    async def bumpreminder_handler(self, message: discord.Message):
        """Handle the bump reminders."""
        
        if message.author.id != DISBOARD_ID:
            return 

        if "Bump done!" in message.embeds[0].description: # really need daddy regex but just need to push an update out asap
            thankyou = await self.bot.db.fetchval('SELECT (channel, thankyou, message) FROM bumpreminder WHERE guild_id = $1', message.guild.id)
            if not thankyou[0]:
                return
            if thankyou[0] != message.channel.id:
                return 
            await message.channel.send(thankyou[1] if thankyou[1] else self.default_thankyou)

            utility_cog: utility = self.bot.get_cog("utility")
            if not utility_cog:
                return # im a dumbass!!!

            await utility_cog.create_timer(
                discord.utils.utcnow() + datetime.timedelta(hours=2),
                'bumpreminder',
                message.guild.id,
                message.channel.id
            )

    @commands.Cog.listener()
    async def on_bumpreminder_timer_complete(self, timer):
        guild_id, channel_id = timer.args

        guild = self.bot.get_guild(guild_id)
        if not guild:
            return 

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        message = await self.bot.db.fetchval("SELECT (message, pingrole) FROM bumpreminder WHERE guild_id = $1", guild_id)
        await channel.send(f"{f'<@&{message[1]}>:' if message[1] else ''} {message[0]}", allowed_mentions=discord.AllowedMentions(roles=True))

    @commands.command(name='afk')
    async def _afk(self, ctx: MyContext, *, message: Optional[commands.clean_content] = None):
        """Set an AFK status when users mention you."""
        message = message or 'No reason provided...'

        query = """
                INSERT INTO afk (_user, is_afk, added_time, message) VALUES ($1, $2, $3, $4)
                """
        try:
            await self.bot.db.execute(query, ctx.author.id, True, discord.utils.utcnow().replace(tzinfo=None), message)
        except asyncpg.exceptions.UniqueViolationError:
            return

        self.afk_users[ctx.author.id] = True
        await ctx.send(f"{self.bot.emotes['dnd']} Your AFK has been set for: \n> {message}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if self.afk_users.get(message.author.id):
            query = """
                    SELECT added_time FROM afk WHERE _user = $1
                    """
            data = await self.bot.db.fetchval(query, message.author.id)
            await self.bot.db.execute("DELETE FROM afk WHERE _user = $1", message.author.id)
            self.afk_users[message.author.id] = False
            return await message.reply(f"👋 Welcome back **{message.author}**, you've been afk since {discord.utils.format_dt(pytz.utc.localize(data), 'R')}")
        if not message.mentions:
            return 
        for mention in message.mentions:
            if not self.afk_users.get(mention.id):
                return 

            query = """
                    SELECT (message, added_time) FROM afk WHERE _user = $1
                    """
            data = await self.bot.db.fetchval(query, mention.id)
            if data:
                await message.reply(f"Seems like **{mention}** is currently afk since {discord.utils.format_dt(pytz.utc.localize(data[1]), 'R')}\n> {data[0]}")

    @commands.command(name='scan')
    @commands.has_guild_permissions(manage_guild=True)
    @commands.bot_has_guild_permissions(manage_guild=True)
    async def scan(self, ctx: MyContext, *, text: str):
        """
        Scan the presences of the guild members and searches for a substring.
        
        You can use this tool to check for invite links, certain words or more.
        """
        if not ctx.guild.chunked:
            await ctx.guild.chunk()

        to_paginate = []
        for member in ctx.guild.members:
            if not member.activities:
                continue
            if isinstance(member.activities[0], (discord.CustomActivity, discord.Game, discord.Activity, discord.Streaming)):
                if text in str(member.activities[0].name):
                    to_paginate.append(member)
                continue
            try:
                if text in member.activities[0]:
                    to_paginate.append(f"{member}: {member.activity}")
            except:
                continue
        if to_paginate:
            await ctx.paginate(to_paginate, compact=True)
        else:
            await ctx.send("No members in this guild have the string in their status.")
                





