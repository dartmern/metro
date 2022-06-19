from typing import List
from bot import MetroBot

from utils.embeds import create_embed
from .get_entries import get_entries
from .delete_giveaway import delete_giveaway
from .delete_entries import delete_entries

import discord
import random
import ast

async def end_giveaway(
    bot: MetroBot,
    message_id: int,
    data: List, # formatted list from database
    message: discord.Message
    
    ):
    """End a giveaway and delete the entries."""
    entires = await get_entries(bot, message_id)

    raw_embed = data[0]
    amount_of_winners = data[1]

    raw = ast.literal_eval(raw_embed)
    embed = discord.Embed.from_dict(raw)

    if len(entires) == 0:
        alert_message = 'Not enough entrants to determine a winner!'
        embed.color = discord.Color(3553599)

    else:
        winners = random.sample(entires, amount_of_winners)
        winners_fmt = ", ".join([f"<@{record['author_id']}>" for record in winners])

        alert_message = f'Winners: {winners_fmt}'
        embed.color = discord.Color.red()

    old = embed.description 
    old = old.replace('Click the button below to enter!', alert_message) # bad way of doing this but i'm testing
    old = old.replace('Ends', 'Ended')

    embed.description = old
    embed.set_footer(text=message.embeds[0].footer.text)

        
    button = discord.ui.Button()
    button.disabled = True
    button.style = discord.ButtonStyle.red
    button.label = 'Giveaway Ended'

    view = discord.ui.View()
    view.add_item(button)
        
    await message.edit(embed=embed, view=view)

    term = 'has' if amount_of_winners < 2 else 'have'
    new_embed = create_embed(
        alert_message if len(entires) == 0 else f'{winners_fmt} {term} won the giveaway for **{message.embeds[0].author.name}**',
        color=discord.Color.yellow()
    )
    await message.reply(embed=new_embed)

    await delete_giveaway(bot, message_id) # delete the giveaway itself
    await delete_entries(bot, message_id) # delete the giveaway's entries