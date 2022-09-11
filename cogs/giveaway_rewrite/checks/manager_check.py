from utils.custom_context import MyContext
from ..settings.get_setting import get_setting
from ..errors import NotManager, NoGiveawayPermissions
from bot import MetroBot

import discord
from discord.ext import commands


def giveaway_manager_check():
    async def predicate(ctx: MyContext):

        manager = await get_setting(ctx.bot, 'manager', ctx.guild.id)

        role = ctx.guild.get_role(manager) # manager can be none and this will still work
        if not role:
            if not ctx.author.guild_permissions.manage_guild:
                raise NoGiveawayPermissions(f'You need `Manage Guild` permissions to use this.')
        else:
            if not role in ctx.author.roles and not ctx.author.guild_permissions.manage_guild:
                raise NotManager(f'You need to be a giveaway manager (<@&{manager}>) to use this.')
        return True
    return commands.check(predicate)

async def giveaway_manager_check_interaction(bot: MetroBot, interaction: discord.Interaction,):
    """Check if `Interaction.user` is a giveaway manager."""
    manager = await get_setting(bot, 'manager', interaction.guild_id)

    role = interaction.guild.get_role(manager) # manager can be none and this will still work
    if not role:
        if not interaction.user.guild_permissions.manage_guild:
            await interaction.followup.send(f'You need `Manage Guild` permissions to use this.', ephemeral=True)
            return False
    else:
        if not role in interaction.user.roles and not interaction.user.guild_permissions.manage_guild:
            await interaction.followup.send(f'You need to be a giveaway manager (<@&{manager}>) to use this.', ephemeral=True)
            return False
    return True
    
