import datetime
import json
from typing import List
from bot import MetroBot

from utils.embeds import create_embed
from .get_entries import get_entries
from .get_giveaway import get_giveaway
from .validate_entry import validate_entry

from ...developer import TabularData

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
    entries = await get_entries(bot, message_id)
    mystbin_button = None

    raw_embed = data[0]
    amount_of_winners = data[1]

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

            alert_message = f'Winners: {winners_fmt}'
            embed.color = discord.Color.red()

            rows = [f'{bot.get_user(entry["author_id"])} ({entry["author_id"]})' for entry in entries]
            entrants = "\n".join(rows)
            content = f'''
                    Giveaway Details

                    Prize: {message.embeds[0].author.name}
                    Winners: {', '.join(f"{bot.get_user(record['author_id'])} ({record['author_id']})" for record in winners)}
                    Giveaway ID: {message_id}

                    
                    Entrants:
                    ---------

                    {entrants}
                    '''
            expires = datetime.datetime.now() + datetime.timedelta(days=7)
            
            paste = await bot.mystbin_client.create_paste(
                filename=f'Giveaway Dump {message_id}.txt', 
                content=content, 
                expires=expires)

            mystbin_button = discord.ui.Button(label='Entries', url=f'https://mystb.in/{paste.id}')

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
    if mystbin_button:
        view.add_item(mystbin_button)
        
    try:
        await message.edit(embed=embed, view=view)
    except (discord.HTTPException, discord.NotFound):
        pass

    if len(entries) > 0:
        term = 'has' if len(winners) < 2 else 'have'
        new_embed = create_embed(
            alert_message if len(entries) == 0 else f'{winners_fmt} {term} won the giveaway for **{message.embeds[0].author.name}**',
            color=discord.Color.yellow()
        )
        await message.reply(embed=new_embed)

    query = """
            UPDATE giveaway
            SET ended = $1
            WHERE message_id = $2
            """
    await bot.db.execute(query, True, message_id)