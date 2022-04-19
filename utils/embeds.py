from typing import Optional, Union
import discord

def create_embed(
    text: str, 
    *, 
    color: Optional[discord.Color] = None,
    title: Optional[str] = None
):
    color = color or discord.Color.blurple()
    embed = discord.Embed(color=color, description=text, title=title)
    return embed