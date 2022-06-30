import discord
from discord import app_commands
from discord.ext import commands

from utils.custom_context import MyContext

@app_commands.context_menu(name='Reroll Giveaway')
async def reroll_giveaway_context_menu(interaction: discord.Interaction, message: discord.Message):
    command: commands.Command = interaction.client.get_command('giveaway reroll')
    context: MyContext = await interaction.client.get_context(interaction)
    try:
        await context.invoke(command, message_id=message.id)
    except Exception as e:
        return await interaction.response.send_message(str(e), ephemeral=True)
