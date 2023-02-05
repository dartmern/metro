from __future__ import annotations
from typing import List, Optional, TypedDict, TYPE_CHECKING

import discord
from discord import ui

import asyncio

from utils.custom_context import ConfirmationView, MyContext
from discord import Interaction
import json

import secrets
import datetime

import chat_exporter
import io

if TYPE_CHECKING:
    from bot import MetroBot

class TicketObject(TypedDict):
    number: int
    roles: List[int]
    ticket_embed: str
    ticket_message: str
    panel_embed: str
    panel_message: str

class SupportControlsView(ui.View):
    """Persistent View"""

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label='Reopen', emoji='\U0001f513', custom_id='reopen_ticket_button')
    async def reopen_callback(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer()

        members_or_roles = []
        for over in interaction.channel.overwrites:
            if not over.id == interaction.guild_id:
                members_or_roles.append(over)
        
        overwrites = {}
        for member in members_or_roles:
            overwrites[member] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        overwrites[interaction.guild.default_role] = discord.PermissionOverwrite(read_messages=False)

        try:
            await interaction.channel.edit(overwrites=overwrites)
        except discord.HTTPException as e:
            await interaction.followup.send(f'Could not reopen ticket due to permissions isuses. {e}', ephemeral=True)
            return 

        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)
        
        embed = discord.Embed(color=discord.Color.green(), description='Reopened ticket.')
        await interaction.channel.send(embed=embed)

    @ui.button(label='Transcript', emoji='\U0001f4dc', custom_id='transcript_ticket_button')
    async def transcript_callback(self, interaction: Interaction[MetroBot], button: ui.Button):

        await interaction.response.send_message('Gathering data to generate transcript... This may take a while.', ephemeral=True)
        transcript = await chat_exporter.export(interaction.channel)
        if not transcript:
            await interaction.followup.send('Nothing to transcript. Try again later.', ephemeral=True)
            return 

        transcript_file = discord.File(io.BytesIO(transcript.encode()), filename=f"transcript-{interaction.channel.name}.html")
        message: discord.Message = await interaction.channel.send(file=transcript_file)

        embed = discord.Embed(description=f'Transcript Saved.\n[Transcript]({await chat_exporter.link(message)})',
                            color=discord.Color.green())
        embed.set_footer(text=f'Requested by: {interaction.user} (ID: {interaction.user.id})')
        await message.edit(embed=embed, attachments=[transcript_file])
            
    @ui.button(label='Delete', emoji='\U0001f5d1', custom_id='delete_ticket_button')
    async def delete_callback(self, interaction: Interaction, button: ui.Button):
        view = ConfirmationView(timeout=60, author_id=interaction.user.id, ctx=None, delete_after=True)
        await interaction.response.send_message(f"Are you sure you want to delete this ticket?", view=view, ephemeral=True)
        
        await view.wait()

        if not view.value:
            return

        embed = discord.Embed(color=discord.Color.red(), description='Deleting channel in 5 seconds...')
        message = await interaction.channel.send(embed=embed)

        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)

        await asyncio.sleep(5)
        
        try:
            await interaction.channel.delete(reason=f'Delete ticket invoked by: {interaction.user} (ID: {interaction.user.id})')
        except discord.HTTPException:
            await message.edit(content='Could not delete due to permissions issue.', ephemeral=True)

class CloseTicketView(ui.View):
    """Persistent View"""

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label='Close Ticket', emoji='\U0001f512', custom_id='close_ticket_button')
    async def callback(self, interaction: Interaction[MetroBot], button: ui.Button):
        
        channel = interaction.channel
        await interaction.response.send_message('Closing ticket. You can open another one if you need more help!', ephemeral=True)

        over = channel.overwrites_for(interaction.user)
        over.read_messages = False
        try:
            await channel.set_permissions(interaction.user, overwrite=over)
        except discord.HTTPException as e:
            await interaction.followup.send(f'Could not close ticket. \nError: {e}', ephemeral=True)
            return 
        
        embed = discord.Embed(color=discord.Color.red(), description='Ticket has been closed.')
        embed.set_footer(text=f'Ticket closed by: {interaction.user}')
        await channel.send(embed=embed, view=SupportControlsView())

class CreateTicketView(ui.View):
    """Persistent View"""

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label='Create ticket', emoji='\U0001f4e9', custom_id='create_ticket_button')
    async def callback(self, interaction: Interaction[MetroBot], button: ui.Button):

        view = ConfirmationView(timeout=60, author_id=interaction.user.id, ctx=None, delete_after=True)
        await interaction.response.send_message(f"Are you sure you want to create this ticket?", view=view, ephemeral=True)
        
        await view.wait()

        if not view.value:
            return

        bot = interaction.client
        guild = interaction.guild

        query = 'SELECT number, roles, ticket_embed, ticket_message, panel_embed, panel_message FROM tickets WHERE message_id = $1'
        data: TicketObject = await bot.db.fetchrow(query, interaction.message.id)
        if not data:
            await interaction.followup.send('Somehow setup for this guild failed. Report to my support server. `/support`', ephemeral=True)
            return
        
        overwrites = {}
        if data.get('roles'):
            for overwrite in data['roles']:
                obj = guild.get_member(overwrite)
                if not obj:
                    obj = guild.get_role(overwrite)
                    if not obj:
                        continue # not a role or a member
                
                overwrites[obj] = discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                )

        overwrites[guild.default_role] = discord.PermissionOverwrite(read_messages=False) # deny @everyone's read perms
        overwrites[interaction.user] = discord.PermissionOverwrite(read_messages=True) # allow user read perms
        overwrites[interaction.guild.me] = discord.PermissionOverwrite(manage_channels=True, send_messages=True) # give the bot managechannel + send perms
        

        try:
            channel = await guild.create_text_channel(
                name=f'ticket-{str(data["number"]).zfill(4)}', 
                overwrites=overwrites)
        except discord.HTTPException:
            await interaction.followup.send(
                'Could not create a ticket due to permissions issue. Try giving me proper permissions.', ephemeral=True)
            return

        try:
            ticket_embed = json.loads(data.get('ticket_embed'))
            ticket_message = data.get('ticket_message')

            embed = discord.Embed.from_dict(ticket_embed)

        except Exception as e:
            await interaction.followup.send(f'Fetching data failed somehow. Report to support. /support\n{e}', ephemeral=True)
            return

        user_embed = discord.Embed(
            color=interaction.guild.me.color, 
            description=f'Ticket created by: {interaction.user.mention} (ID: {interaction.user.id})')

        query = 'UPDATE tickets SET number = $2 WHERE message_id = $1'
        await bot.db.execute(query, interaction.message.id, int(data["number"]) + 1)

        await interaction.followup.send(f'Created a ticket. {channel.mention}', ephemeral=True)

        content = ticket_message.replace("{user}", interaction.user.mention) if ticket_message else None
        message = await channel.send(
            content=content, 
            embeds=[embed, user_embed], 
            view=CloseTicketView(),
            allowed_mentions=discord.AllowedMentions.all()) # type: discord.Message

        try:
            await message.pin()
        except discord.HTTPException:
            pass

class EditMessageModal(ui.Modal, title='Input Message'):
    def __init__(self, default: str) -> None:
        super().__init__(timeout=300)

        self.message = ui.TextInput(
            label='Input your message.', 
            style=discord.TextStyle.long,
            default=default,
            required=False       
            )

        self.add_item(self.message)

    async def on_submit(self, interaction: Interaction) -> None:
        
        self.interaction = interaction
        self.string = self.message.value
        self.stop()

class EditMessageView(ui.View):
    def __init__(self, interaction: Interaction, default: str, embed: discord.Embed, view):
        super().__init__(timeout=300)

        self.interaction = interaction
        self.default = default
        self.embed = embed
        self.old_view: TicketConfigView = view

    async def on_timeout(self):

        message = await self.interaction.original_response()
        await message.edit(view=None, content='Timed out.', embed=None)

    @ui.button(label='Edit Text', style=discord.ButtonStyle.blurple)
    async def edit_text_callback(self, interaction: Interaction, button: ui.Button):

        modal = EditMessageModal(self.default)
        await interaction.response.send_modal(modal)

        await modal.wait()
        
        embed = self.embed.clear_fields()
        embed.add_field(name='Text', value=modal.string)
        
        if embed.footer:
            self.old_view.ticket_message = modal.string
        else:
            self.old_view.panel_message = modal.string

        await modal.interaction.response.edit_message(embed=embed)

class JsonModal(ui.Modal, title='Input JSON'):
    code = ui.TextInput(label='Input your json code.', style=discord.TextStyle.long)

    async def on_submit(self, interaction: Interaction) -> None:
        
        self.interaction = interaction
        self.code = self.code.value
        self.stop()

class EditEmbedModal(ui.Modal, title='Editing Embed'):
    def __init__(self, part: str, default: str) -> None:
        super().__init__(timeout=300)

        self.item = ui.TextInput(label=part, style=discord.TextStyle.long, default=default, required=False)
        self.add_item(self.item)

    async def on_submit(self, interaction: Interaction) -> None:
        
        self.text = self.item.value
        self.interaction = interaction
        self.stop()

class EditEmbedView(ui.View):
    def __init__(self, interaction: Interaction, embeds: list[discord.Embed], _type: bool, view):
        super().__init__(timeout=300)

        self.interaction: Interaction = interaction
        self.embeds: list[discord.Embed] = embeds
        self.old_view: TicketConfigView = view
        self._type: bool = _type

    async def update_embed(self, interaction: Interaction):
        """Update the embed with it's new state."""

        await interaction.response.edit_message(embeds=self.embeds)
        
    async def on_timeout(self):

        message = await self.interaction.original_response()
        await message.edit(view=None, content='Timed out.', embed=None)

    @ui.button(label='Author Name')
    async def author_name_callback(self, interaction: Interaction, button: ui.Button):
        
        modal = EditEmbedModal('Author Name', self.embeds[1].author.name)
        await interaction.response.send_modal(modal)

        await modal.wait()
        self.embeds[1].set_author(name=modal.text)

        await self.update_embed(modal.interaction)

    @ui.button(label='Description')
    async def description_callback(self, interaction: Interaction, button: ui.Button):

        modal = EditEmbedModal('Description', self.embeds[1].description)
        await interaction.response.send_modal(modal)

        await modal.wait()
        self.embeds[1].description = modal.text

        await self.update_embed(modal.interaction)

    @ui.button(label='Footer Text')
    async def footer_text_callback(self, interaction: Interaction, button: ui.Button):

        modal = EditEmbedModal('Footer Text', self.embeds[1].footer.text)
        await interaction.response.send_modal(modal)

        await modal.wait()
        self.embeds[1].set_footer(text=modal.text)

        await self.update_embed(modal.interaction)

    @ui.button(label='Save', style=discord.ButtonStyle.green)
    async def save_callback(self, interaction: Interaction, button: ui.Button):
        # self._type is True means it's a panel and False is a ticket

        if self._type:
            self.old_view.panel_embed = self.embeds[1]
        else:
            self.old_view.ticket_embed = self.embeds[1]

        await interaction.response.edit_message(content='Saved your changes.', view=None, embeds=[])

    @ui.button(label='Custom JSON', style=discord.ButtonStyle.blurple)
    async def custom_json_callback(self, interaction: Interaction[MetroBot], button: ui.Button):
        
        modal = JsonModal()
        await interaction.response.send_modal(modal)

        await modal.wait()
        
        try:
            data = json.loads(modal.code)
            embed = discord.Embed.from_dict(data)
        except:
            support = interaction.client.support
            await modal.interaction.response.send_message('Had trouble converting that json into an embed.'\
                f'\nDid you follow [this article](<https://discordapp.com/developers/docs/resources/channel#embed-object>)?'\
                f' Try joining my [support server]({support})', 
                ephemeral=True)
        
        self.embeds[1] = embed
        await self.update_embed(modal.interaction)

class CreateChannelModal(ui.Modal, title='Ticket Channel Details'):
    name = ui.TextInput(label='Name', placeholder='Name of the ticketing channel...')

    def __init__(self, view) -> None:
        super().__init__()

        self.old_view: TicketConfigView = view

    async def on_submit(self, interaction: Interaction) -> None:
        if not interaction.guild.me.guild_permissions.manage_channels:
            return await interaction.response.send_message(
                "I do not have Manage Channel permissions to create channels.", ephemeral=True
                )

        try:
            channel = await interaction.guild.create_text_channel(
                name=self.name.value, 
                reason=f'Ticketing channel invoked by: {interaction.user}',
                overwrites={interaction.guild.default_role: discord.PermissionOverwrite(send_messages=False)})
        except discord.HTTPException:
            return await interaction.response.send_message(
                'Could not create channel. Permissions issue?', ephemeral=True
            )

        await interaction.response.edit_message(
            content=f'Created {channel.mention} to be your ticketing panel.', view=None, embed=None)
        
        self.old_view.channel = channel.id
        embed = self.old_view.generate_embed()

        await self.old_view.message.edit(embed=embed)

class ChannelView(ui.View):
    def __init__(self, interaction: Interaction, view):
        super().__init__(timeout=300)

        self.interaction: Interaction = interaction
        self.old_view: TicketConfigView = view

    async def on_timeout(self):

        message = await self.interaction.original_response()
        await message.edit(view=None, content='Timed out.', embed=None)

    @ui.select(cls=ui.ChannelSelect, 
                placeholder='Select a channel or click create...',
                max_values=1,
                channel_types=[discord.ChannelType.text])
    async def select_channels(self, interaction: Interaction, select: ui.ChannelSelect):

        self.old_view.channel = select.values[0].id
        embed = self.old_view.generate_embed()

        await self.old_view.message.edit(embed=embed)

        await interaction.response.edit_message(
            content=f'Selected {select.values[0].mention} to be handling ticketing panel.', 
            view=None, embed=None)

        self.stop()
        
    @ui.button(label='Create',
                style=discord.ButtonStyle.green)
    async def create_callback(self, interaction: Interaction, button: ui.Button):
        
        modal = CreateChannelModal(self.old_view)
        await interaction.response.send_modal(modal)

class RolesView(ui.View):
    def __init__(self, interaction: Interaction, view):
        super().__init__(timeout=300)

        self.interaction: Interaction = interaction
        self.old_view: TicketConfigView = view

    async def on_timeout(self):

        message = await self.interaction.original_response()
        await message.edit(view=None, content='Timed out.', embed=None)

    @ui.select(cls=ui.RoleSelect,
            placeholder='Select roles...',
            max_values=25)
    async def select_roles(self, interaction: Interaction, select: ui.RoleSelect):

        self.old_view.agent_roles = list(map(lambda r: r.id, select.values))
        embed = self.old_view.generate_embed()

        await self.old_view.message.edit(embed=embed)

        roles = ', '.join(list(map(lambda r: r.mention, select.values)))

        await interaction.response.edit_message(
            content=f'Selected {roles} to be ticket agent roles.',
            view=None, embed=None
        )
    
class TicketConfigView(ui.View):
    def __init__(
        self, ctx: MyContext, *, 
        channel: Optional[int] = None, 
        roles: Optional[List[int]] = [],
        panel_embed: Optional[discord.Embed] = None,
        panel_message: Optional[str] = None,
        ticket_embed: Optional[discord.Embed] = None,
        ticket_message: Optional[str] = None):
    
        super().__init__(timeout=60 * 10)

        self.ctx: MyContext = ctx
        self.message: discord.Message

        self.channel: int = channel
        self.agent_roles: List[int] = roles

        self.panel_embed: discord.Embed = panel_embed or self.generate_panel_embed()
        self.panel_message: str = panel_message

        self.ticket_embed: discord.Embed = ticket_embed or self.generate_ticket_embed()
        self.ticket_message: str = ticket_message

    @classmethod
    def from_data(cls, *args, **kwargs):
        """Create from data. Used when a user wants to edit config data."""

        # for now this isn't used but in the future when you can edit existing configs
        return cls(*args, **kwargs)

    async def on_timeout(self):

        await self.message.edit(view=None, content='Timed out.', embed=None)

    async def interaction_check(self, interaction: Interaction) -> bool | None:
        if interaction.user != self.ctx.author:
            return await interaction.response.send_message('This is not your interaction!', ephemeral=True)
        return True

    def generate_embed(self) -> discord.Embed:
        embed = discord.Embed(title='Ticketing Configuration', color=self.ctx.color)
        embed.description = 'Click the different buttons to configure settings to your needs!'

        channel = f'<#{self.channel}>' if self.channel else 'None'
        embed.add_field(name='Ticket Channel', value=channel)

        roles = ', '.join(f'<@&{r}>' for r in self.agent_roles if r) if self.agent_roles else 'None'
        embed.add_field(name='Ticket Agent Roles', value=roles)

        embed.add_field(name='Setup', value=f'Press the green {self.ctx.bot.emotes["check"]} **Setup** button '\
                                        'to finish up everything and send the panel.'\
                                        '\nThis will send the panel to the ticket channel and save all your changes.', 
                        inline=False)

        return embed

    async def edit_buttons(self, value: bool = True):
        for item in self.children:
            item.disabled = value

        await self.message.edit(view=self)

    async def start(self):
        """Start the view."""

        embed = self.generate_embed()
        message = await self.ctx.send(embed=embed, view=self)
        self.message = message

    def generate_panel_embed(self) -> discord.Embed:
        """Default Panel Embed"""

        embed = discord.Embed(color=self.ctx.color)
        embed.set_author(name='Ticketing')

        embed.description = 'To create a ticket click the button below!'
        embed.set_footer(text='Making a ticket will open a private channel for support to help!')

        return embed 

    def generate_ticket_embed(self) -> discord.Embed:
        """Default Ticket Embed"""

        embed = discord.Embed(color=self.ctx.color)
        embed.description = 'Support will be with you shortly.'\
            '\nTo close this ticket press the button below.'

        embed.set_footer(text='Closing your ticket will mark it as solved.')

        return embed        
    
    @ui.button(label='Channel')
    async def channel_callback(self, interaction: Interaction, button: ui.Button):
        
        embed = discord.Embed(color=self.ctx.color)
        embed.description = 'Select the channel you want to send the ticketing panel to.'\
            '\n> You can also click **Create** for me to create one for you.'
        
        await interaction.response.send_message(embed=embed, ephemeral=True, view=ChannelView(interaction, self))

    @ui.button(label='Roles')
    async def roles_callback(self, interaction: Interaction, button: ui.Button):

        embed = discord.Embed(color=self.ctx.color)
        embed.description = 'Select the role(s) you would like to have access and manage tickets.'\
            '\n> Members with the roles can view, send messages, and manage tickets.'
        
        await interaction.response.send_message(embed=embed, ephemeral=True, view=RolesView(interaction, self))

    @ui.button(label='Setup', style=discord.ButtonStyle.green)
    async def setup_callback(self, interaction: Interaction[MetroBot], button: ui.Button):

        confirm = await self.ctx.confirm('Please review all your settings above and press confirm to continue.',
            interaction=interaction, ephemeral=True, timeout=30)
        if not confirm.value:
            return 

        await self.edit_buttons(value=True)
        # disable all the buttons so no further edits can be made

        resp: discord.Message = await interaction.followup.send('Please wait...', ephemeral=True)

        channel: discord.TextChannel = self.ctx.bot.get_channel(self.channel)

        if not self.channel:
            await resp.edit(content='Channel not found. Try inputing a channel by clicking the **Channel** button.')
            await self.edit_buttons(value=False)
            return

        if not self.ctx.guild.me.guild_permissions.manage_channels:
            await resp.edit(content='I don\'t have permission to create channels. (Missing `Manage Channels` permission)'\
                '\nPlease grant me this permission in server settings then press the setup button again.')

            await self.edit_buttons(value=False)
            return

        if self.agent_roles:
            bad_roles = []

            for role_id in self.agent_roles:
                role = self.ctx.guild.get_role(role_id)
                if role >= self.ctx.me.top_role:
                    bad_roles.append(role.id)

            if bad_roles:
                joined = ', '.join([f"<@&{i}>" for i in bad_roles])
                await resp.edit(content=f'The following role(s) are all higher than me therefore I cannot make overwrites for them: \n{joined}'\
                    f'\n\nPlease fix this by moving the position of my top role and clicking the **Setup** button again.')

                await self.edit_buttons(value=False)
                return 

        try:
            message = await channel.send(embed=self.panel_embed, view=CreateTicketView())
        except discord.HTTPException:
            await resp.edit(content='Had trouble sending panel message. Permissions issue?'\
                f'\n> Try giving me Send Messages permission in {channel.mention} then press setup again.')
            await self.edit_buttons(value=False)
            return

        await resp.edit(content=f'Setup and sent the panel to {channel.mention}')

        bot = interaction.client
        guild_id = self.ctx.guild.id

        # this code is a mess to read but it's basically inserting all the data collected from view
        query = "INSERT INTO tickets (guild_id, channel, roles, message_id, ticket_embed, ticket_message, panel_embed, panel_message)"\
                "VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7::jsonb, $8)"

        try:
            ticket_embed = json.dumps(self.ticket_embed.to_dict(), default=str)
            panel_embed = json.dumps(self.panel_embed.to_dict(), default=str)
            await bot.db.execute(
                query,
                guild_id, channel.id, self.agent_roles, message.id, 
                ticket_embed, self.ticket_message,
                panel_embed, self.panel_message)
        except Exception as e:
            await resp.edit(content=f'Something went wrong with saving your data. \n{e}\nReport to support staff. /support')
            return

        await resp.edit(content=f'Setup has finished. Panel was saved and sent to {channel.mention}')

    @ui.button(label='Panel Embed', style=discord.ButtonStyle.blurple, row=1)
    async def panel_embed_callback(self, interaction: Interaction, button: ui.Button):

        link = 'https://discordapp.com/developers/docs/resources/channel#embed-object'

        embed = discord.Embed(title='Edit Panel Embed', description='The embed below will be sent to the panel channel for members '\
                                        'to click for creating tickets.'\
                                        '\n\nUse the buttons below to edit parts of it or use the raw json for more customization.')

        embed.add_field(name='Custom JSON', value=f'You can generate a custom embed and paste in json. It must be in [this format]({link})'\
                                                '\nExample: `{"title": "This is my title", "description": "This is my description"}`'
        )

        embed.set_footer(text='Make sure you click Save when you are done editing your embed.')

        embeds = [embed, self.panel_embed]
        await interaction.response.send_message(
            embeds=embeds, 
            ephemeral=True, 
            view=EditEmbedView(interaction, embeds, True, self))

    @ui.button(label='Panel Message', style=discord.ButtonStyle.blurple, row=1)
    async def panel_message_callback(self, interaction: Interaction, button: ui.Button):

        embed = discord.Embed(color=self.ctx.color, title='Edit Panel Message')
        embed.description = 'This message will be sent along with the embed in the panel channel.'\
            f'\n> By default the bot won\'t send anything in the content and just the embed.'

        embed.add_field(name='Text', value=self.panel_message)

        await interaction.response.send_message(
            embed=embed, 
            view=EditMessageView(interaction, self.ticket_message, embed, self), 
            ephemeral=True)

    @ui.button(label='Ticket Embed', style=discord.ButtonStyle.blurple, row=2)
    async def ticket_embed_callback(self, interaction: Interaction, button: ui.Button):

        link = 'https://discordapp.com/developers/docs/resources/channel#embed-object'

        embed = discord.Embed(title='Edit Ticket Embed', description='The embed below will be sent in the ticket after it\'s been made by members.'\
                                '\n\nUse the buttons below to edit parts of it or use the raw json for more customization.')

        embed.add_field(name='Custom JSON', value=f'You can generate a custom embed and paste in json. It must be in [this format]({link})'\
                                                '\nExample: `{"title": "This is my title", "description": "This is my description"}`'
        )

        embed.set_footer(text='Make sure you click Save when you are done editing your embed.')

        embeds = [embed, self.ticket_embed]
        await interaction.response.send_message(
            embeds=embeds, 
            ephemeral=True, 
            view=EditEmbedView(interaction, embeds, False, self))

    @ui.button(label='Ticket Message', style=discord.ButtonStyle.blurple, row=2)
    async def ticket_message_callback(self, interaction: Interaction, button: ui.Button):

        embed = discord.Embed(color=self.ctx.color, title='Edit Ticket Message')
        embed.description = 'This message will be sent along with the embed in the panel channel.'\
            f'\n> By default the bot won\'t send anything in the content and just the embed.'

        embed.set_footer(text='Tip: You can mention roles and use {user} to mention the ticket opener.')
        embed.add_field(name='Text', value=self.ticket_message)

        await interaction.response.send_message(
            embed=embed, 
            view=EditMessageView(interaction, self.ticket_message, embed, self), 
            ephemeral=True)


        

    