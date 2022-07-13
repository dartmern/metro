import asyncio
import discord

from utils.constants import SUPPORT_CATEGORY, SUPPORT_ROLE
from utils.embeds import create_embed

class SupportView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='General Support', custom_id='general_support_button')
    async def general_support_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        """General support button."""

        support_role = interaction.guild.get_role(SUPPORT_ROLE)
        
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(
                read_messages=False
            ),
            support_role: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True
            ),
            interaction.user: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True
            )
        }
        category = interaction.guild.get_channel(SUPPORT_CATEGORY)
        channel = await interaction.guild.create_text_channel(
            name='ticket', 
            overwrites=overwrites, 
            topic='General Support Ticket',
            category=category)
        await interaction.response.send_message(f'Created a ticket for you in {channel.mention}', ephemeral=True)

        embed = create_embed('You can ask your question here and close the ticket with `?close`', color=discord.Color.yellow())
        await channel.send(embed=embed)

        try:
            message = await interaction.client.wait_for(
                'message', 
                check=lambda x: x.author == interaction.user and x.channel == channel, 
                timeout=300)
            
            await message.pin()
        except asyncio.TimeoutError:
            pass
        
    @discord.ui.button(label='Bug/Command Error Report', style=discord.ButtonStyle.red, custom_id='report_bug_command_error_button')
    async def report_command_error_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Report command error button."""

        support_role = interaction.guild.get_role(SUPPORT_ROLE)
        
        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(
                read_messages=False
            ),
            support_role: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True
            ),
            interaction.user: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True
            )
        }
        category = interaction.guild.get_channel(SUPPORT_CATEGORY)
        channel = await interaction.guild.create_text_channel(
            name='ticket', 
            overwrites=overwrites, 
            topic='Bug/Command Error Ticket',
            category=category)

        await interaction.response.send_message(f'Created a ticket for you in {channel.mention}', ephemeral=True)

        embed = create_embed('You can state your bug/command error id here and close the ticket with `?close`', color=discord.Color.yellow())
        await channel.send(embed=embed)

        try:
            message = await interaction.client.wait_for(
                'message', 
                check=lambda x: x.author == interaction.user and x.channel == channel, 
                timeout=300)
            
            await message.pin()
        except asyncio.TimeoutError:
            pass
