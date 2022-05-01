import asyncio
import copy
from typing import List
import discord
import re
import time

import TagScriptEngine as tse

from utils.custom_context import MyContext
from .blocks import blocks
from .context import SilentContext


async def process(ctx: MyContext, message: str):
    adapters = {
        "member": tse.MemberAdapter(ctx.author), 
        "guild": tse.GuildAdapter(ctx.guild), 
        "server": tse.GuildAdapter(ctx.guild), # same thing
    }
    engine = tse.Interpreter(blocks)
    output = engine.process(message, dot_parameter=False, seed_variables=adapters)

    actions = output.actions
    content = output.body[0:1999] if output.body else None

    await send_output(ctx, actions, content)


async def send_output(ctx: MyContext, actions: dict, content: str = None):

    command_messages = []
    to_gather = []

    if delete := actions.get("delete", False):
        to_gather.append(delete_quietly(ctx))
    
    if actions.get("commands"):
        for command in actions["commands"]:
            if command == "tag invoke":
                await ctx.send("Tag looping isn't allowed.")
                return
            
            new = copy.copy(ctx.message)
            new.content = ctx.prefix + command
            command_messages.append(new)

    if command_messages:
        silent = actions.get("silent", False)
        overrides = actions.get("overrides")
        to_gather.append(process_commands(command_messages, silent, overrides, ctx))

    if to_gather:
        await asyncio.gather(*to_gather)

    try:
        await ctx.channel.send(content)
    except discord.HTTPException:
        pass

async def process_commands(messages: List[discord.Message], silent: bool, overrides: dict, context: MyContext):
    command_tasks = []
    for message in messages:
        command_task = asyncio.create_task(process_command(message, silent, overrides, context))
        command_tasks.append(command_task)
        await asyncio.sleep(0.1)
    await asyncio.gather(*command_tasks)

async def process_command(message: discord.Message, silent: bool, overrides: dict, context: MyContext):
    command_cls = SilentContext if silent else MyContext
    ctx = await context.bot.get_context(message, cls=command_cls)
    if not ctx.valid:
        return
    if overrides:
        # ctx.command = handle_overrides(ctx.command, overrides)
        pass
    await context.bot.invoke(ctx)

async def delete_quietly(ctx: MyContext):
    if ctx.channel.permissions_for(ctx.me).manage_messages:
        try:
            await ctx.message.delete()
        except discord.HTTPException:
            pass
