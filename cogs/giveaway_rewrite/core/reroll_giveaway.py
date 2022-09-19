import random
from typing import List

import discord
import ast
from bot import MetroBot
from utils.embeds import create_embed

from .get_entries import get_entries
from .validate_entry import validate_entry

async def reroll_giveaway(
    bot: MetroBot,
    message_id: int,
    data: List, # formatted list from database
    message: discord.Message,
    winners: int = 1):
    """Reroll a giveaway."""

    entries = await get_entries(bot, message_id)

    raw_embed = data[0]
    amount_of_winners = winners

    raw = ast.literal_eval(raw_embed.replace('null', 'None'))
    embed = discord.Embed.from_dict(raw)

    if len(entries) == 0:
        alert_message = 'Not enough entrants to determine a winner!'
        embed.color = discord.Color(3553599)

    else:
        requirements = ast.literal_eval(data[5].replace('null', 'None'))
        if all(bool(x) is False for x in requirements.values()):
            # no req
            pass
        else:
            role_req = requirements['role']
            bypass_req = requirements['bypass']
            blacklist_req = requirements['blacklist']
            mee6_req = requirements['mee6']

            for entry in entries:
                if message.guild.get_member(entry['author_id']) not in message.guild.members:
                    entries.remove(entry)
                    continue

                resp = await validate_entry(
                    bot,
                    entry,
                    role_req,
                    bypass_req,
                    blacklist_req, 
                    mee6_req,
                    message.guild)
                if resp is False:
                    entries.remove(entry)

        if len(entries) == 0:
            alert_message = 'Not enough valid entries to determine a winner!'
            embed.color = discord.Color(3553599)
        else:
            try:
                winners = random.sample(entries, amount_of_winners)
            except ValueError:
                winners = entries # when somehow there are more winners than entries everybody that entered wins
            winners_fmt = ", ".join([f"<@{record['author_id']}>" for record in winners])

            alert_message = f'Rerolled Winners: {winners_fmt}'
            embed.color = discord.Color.red()

    old = embed.description 
    old = old.replace('Click the button below to enter!', alert_message) # bad way of doing this but i'm testing
    old = old.replace('Ends', 'Ended')

    embed.description = old
    embed.set_footer(text=message.embeds[0].footer.text)
        
    await message.edit(embed=embed)

    if len(entries) > 0:
        term = 'has' if len(winners) < 2 else 'have'
        new_embed = create_embed(
            alert_message if len(entries) == 0 else f'{winners_fmt} {term} won the reroll for **{message.embeds[0].author.name}**',
            color=discord.Color.orange()
        )
        await message.reply(embed=new_embed)

