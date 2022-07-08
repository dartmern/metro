"""These are all the views associated with the giveaway rewrite."""

import datetime
from typing import Any, Optional

import discord
from bot import MetroBot

from utils.constants import EMOTES
from utils.embeds import create_embed

from .core.get_entry import get_entry
from .core.delete_entry import delete_entry

class GiveawayEntryButton(discord.ui.Button):
    async def callback(self, interaction: discord.Interaction) -> Any:
        return await super().callback(interaction)

class GiveawayEntryView(discord.ui.View):
    def __init__(self, ctx, view_message: discord.Message):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.view_message = view_message

        custom_id = f"{self.ctx.guild.id}|{self.ctx.channel.id}|{self.view_message.id}"

        button = GiveawayEntryButton()
        button.custom_id = custom_id
        button.emoji = '\U0001f389'
        button.style = discord.ButtonStyle.green

        self.add_item(button)
        
class ConfirmationEmojisView(discord.ui.View):
    def __init__(self, *, timeout: float, author_id: int, ctx) -> None:
        super().__init__(timeout=timeout)
        self.value: Optional[bool] = None
        self.author_id: int = author_id
        self.ctx = ctx
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id == self.author_id:
            return True
        else:
            await interaction.response.send_message('This confirmation dialog is not for you.', ephemeral=True)
            return False

    async def on_timeout(self) -> None:
        self.value = None
        
    @discord.ui.button(emoji=EMOTES['check'], style=discord.ButtonStyle.green)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = True
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(emoji=EMOTES['cross'], style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.value = False
        await interaction.response.defer()
        self.stop()

class UnenterGiveawayView(discord.ui.View):
    def __init__(self, bot: MetroBot, message_id, org_message, ending: datetime.datetime):
        super().__init__(timeout=None)
        self.bot = bot
        self.message_id: int = message_id
        self.org_message: discord.Message = org_message # original message
        self.ending = ending

    @discord.ui.button(
        label='Leave this giveaway.', 
        emoji=EMOTES['cross'],
        style=discord.ButtonStyle.red
    )
    async def unenter_giveaway_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Unenter a giveaway."""

        await interaction.response.defer()

        if discord.utils.utcnow().replace(tzinfo=None) > self.ending:
            embed = create_embed('It seems like it\'s too late to leave this giveaway.', color=discord.Color.yellow())
            return await interaction.edit_original_message(embed=embed, view=None)

        data = await get_entry(self.bot, self.message_id, interaction.user.id)
        if not data:
            return await interaction.followup.send(f"It seems like you aren't entered in this giveaway afterall.", ephemeral=True)
    
        await delete_entry(self.bot, self.message_id, interaction.user.id)

        button.style = discord.ButtonStyle.green
        button.disabled = True
        button.label = 'Left this giveaway.'
        button.emoji = EMOTES['check']

        embed = self.org_message.embeds[0]
        footer = self.org_message.embeds[0].footer

        x = footer.text.split("|")[1].rstrip("entries")
        final = footer.text.split("|")[0] + "| " + str(int(x) - 1) + " entries"

        embed.set_footer(text=final)
        await self.org_message.edit(embed=embed)

        embed = create_embed('You have left this giveaway.', color=discord.Color.yellow())
        await interaction.edit_original_message(embed=embed, view=None)
