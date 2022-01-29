import datetime
import json
import random
import traceback
from typing import Dict, List, Optional
import discord
from discord.ext import commands
import argparse

import pytz
import re

from bot import MetroBot
from utils.converters import RoleConverter
from utils.custom_context import MyContext
from utils.remind_utils import FutureTime, plural
from utils.useful import Cooldown, Embed, ts_now


def setup(bot: MetroBot):
    bot.add_cog(basic_cog(bot))

class WinnerConverter(commands.Converter):
    async def convert(self, ctx : MyContext, argument : str):
        if argument is None:
            return 1
        try:
            if int(argument) > 30:
                raise commands.BadArgument("\U00002753 You cannot have more than 30 winners.")
            if int(argument) <= 0:
                raise commands.BadArgument("\U00002753 You cannot have less than 0 winners.")
            return int(argument)
        except ValueError:
            argument = argument.replace("w", "")
            try:
                if int(argument) > 30:
                    raise commands.BadArgument("\U00002753 You cannot have more than 30 winners.")
                if int(argument) <= 0:
                    raise commands.BadArgument("\U00002753 You cannot have less than 0 winners.")
                return int(argument)
            except ValueError:
                raise commands.BadArgument("\U00002753 There was an issue converting your winners argument.")

class NoExitParser(argparse.ArgumentParser):
    def error(self, message):
        raise commands.BadArgument(message)            

class RequirementConverter(commands.Converter):
    async def convert(self, ctx: MyContext, argument: str):
        if argument.lower() == "none":
            return None
        
        to_return = []

        pattern = re.compile(r"\||;;")
        argument = pattern.split(argument)

        for arg in argument:
            if arg is None:
                continue
            try:
                role = await RoleConverter().convert(ctx, arg)
            except Exception:
                raise commands.BadArgument(f"I could not convert \"{arg}\" into a vaild role.\nPass in `none` to ignore requirements for giveaways.")
            to_return.append(role.id)
        
        return to_return 

class basic_cog(commands.Cog, description='Create and manage giveaways.'):
    def __init__(self, bot: MetroBot):
        self.bot = bot

    @property
    def emoji(self) -> str:
        return '\U0001f389'
    
    async def end_giveaway(
        self, 
        *, 
        guild_id: int, 
        host_id: int, 
        channel_id: int, 
        message_id: int, 
        winners: int, 
        prize: str,
        message: str,
        role: int) -> bool:
        """Helper function to end a giveaway by it's giveaway id."""

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            return False

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            return False

        _message = discord.utils.get(self.bot.cached_messages, id=message_id)
        if _message is None:
            try:
                _message = await channel.fetch_message(message_id)
            except discord.NotFound:
                return False

        reactions = await _message.reactions[0].users().flatten()
        reactions.remove(guild.me)
        if len(reactions) < 1:
            embed = discord.Embed(color=discord.Colour(3553599))
            embed.set_author(name=prize)
            embed.description = f"\nNot enough entrants to determine a winner!"\
                                f"\nEnded {discord.utils.format_dt(discord.utils.utcnow(), 'R')}"\
                                f"\nHosted by: <@{host_id}>" # No API call needed
            embed.set_footer(text=f'{winners} winner{"s" if winners > 1 else ""}')
            
            embeds = [embed] if not message else [embed, discord.Embed(color=discord.Colour.blue(), description=message)]

            view = discord.ui.View()
            view.add_item(discord.ui.Button(label='Jump to giveaway', url=_message.jump_url))

            await _message.edit(embeds=embeds, content=f"\U0001f389\U0001f389 **GIVEAWAY ENDED** \U0001f389\U0001f389\n{'<@&%s>' % role if role else ''}", allowed_mentions=discord.AllowedMentions.all())
            await _message.channel.send(f"There were no vaild entries for the **{prize}** giveaway.", view=view)
            return True
        else:
            winners_string = []
            winners_list = reactions

            for _ in range(winners):
                winner = random.choice(winners_list)
                winners_list.pop(winners_list.index(winner))

                member = guild.get_member(winner.id)

                embed = discord.Embed(
                    color=discord.Colour.green(), description=f"You won the giveaway for [{prize}]({_message.jump_url} \"Jump to message\") in **{guild.name}**")

                try:
                    await member.send(embed=embed)
                except discord.HTTPException:
                    pass

                winners_string.append(winner.id)
            
            embed = discord.Embed(color=discord.Color(3553599))
            embed.set_author(name=prize)
            embed.description = f"\nWinner{'s: ' if len(winners_string) > 1 else ':'} {', '.join(f'<@{users}>' for i, users in enumerate(winners_string))}"\
                                f"\nEnded {ts_now('R')}"\
                                f"\nHosted by: <@{host_id}>" # No API call needed
            embed.set_footer(text=f'{winners} winner{"s" if winners > 1 else ""}')

            embeds = [embed] if not message else [embed, discord.Embed(color=discord.Color.blue(), description=message)]

            view = discord.ui.View()
            view.add_item(discord.ui.Button(label='Jump to giveaway', url=_message.jump_url))

            await _message.edit(embeds=embeds, content=f"\U0001f389\U0001f389 **GIVEAWAY ENDED** \U0001f389\U0001f389\n{'<@&%s>' % role if role else ''}", allowed_mentions=discord.AllowedMentions.all())
            await _message.channel.send(
                f'{", ".join(f"<@{users}>" for i, users in enumerate(winners_string))} {"have" if len(winners_string) > 1 else "has"} won the giveaway for **{prize}**',
                view=view)
            return True

    @commands.group(name='giveaway', aliases=['gaw', 'g'], invoke_without_command=True, case_insensitive=True)
    @commands.bot_has_permissions(send_messages=True, add_reactions=True)
    @commands.has_guild_permissions(manage_guild=True)
    async def giveaway(self, ctx : MyContext):
        """Manage and create giveaways for your server."""
        await ctx.help()

    @giveaway.command(name='make')
    @commands.bot_has_permissions(send_messages=True, add_reactions=True)
    @commands.has_guild_permissions(manage_guild=True)
    async def giveaway_make(self, ctx: MyContext):
        """Make a giveaway interactively."""

        await ctx.send("work in progress stop running this command")
    

    @giveaway.command(
        name='start',
        extras={
            'examples' : "[p]g start 10m 1w Free Nitro"\
                        "\n[p]g start 50days 10w NFT"\
                        "\n[p]g start 1week Free Bot Premium"
        })
    @commands.check(Cooldown(2, 8, 3, 8, commands.BucketType.member))
    @commands.bot_has_permissions(send_messages=True, add_reactions=True)
    @commands.has_guild_permissions(manage_guild=True)
    async def giveaway_start(
        self, ctx : MyContext, duration : FutureTime, 
        winners : Optional[WinnerConverter] = 1, *, prize : str):
        """
        Start a giveaway!
        
        Vaild Flags:
        `--ping`: A mention or name of a role to ping
        `--message`: A string to include as the giveaway message
        `--pin`: Pin the giveaway after creating it
        `--require`: A mention, name or id of a role that's required to join

        For additional help join my [support server](https://discord.gg/2ceTMZ9qJh)
        """
        await ctx.defer()

        prize = prize.split('--')[0]
        flags = ctx.message.content


        parser = NoExitParser()
        parser.add_argument('--ping', nargs='*', type=str, default=None)
        parser.add_argument('--message', nargs='*', type=str, default=None)
        parser.add_argument('--pin', action='store_true', default=False)
        
        role, message, pin = None, None, False
        try:
            flags = vars(parser.parse_known_args(flags.split())[0])
            
            if flags['ping']:
                try:
                    role = await RoleConverter().convert(ctx, str(flags['ping']))
                except Exception as e:
                    return await ctx.send(str(e))
            if flags['message']:
                message = ' '.join(list(flags['message']))
            if flags['pin']:
                pin = True

        except Exception as e:
            return await ctx.send(str(e))

        if duration.dt < (ctx.message.created_at + datetime.timedelta(seconds=5)):
            return await ctx.send("Duration is too short. Must be at least 5 seconds.")

        #if requirements:
            #requirement = f"\nRequired Role{'s:' if len(requirements) > 1 else ':'} {', '.join(f'<@&{users}>' for i, users in enumerate(requirements))}"
        #else:
            #requirement = ""

        e = Embed()
        e.colour = 0xe91e63
        e.set_author(name=prize[0:40])
        e.description = f"\nReact with \U0001f389 to enter!"\
                        f"\nEnds {discord.utils.format_dt(duration.dt, 'R')} ({discord.utils.format_dt(duration.dt, 'f')})"\
                        f"\nHosted by: {ctx.author.mention}"
        e.set_footer(text=f'{winners} winner{"s" if winners > 1 else ""}')

        embeds = [e] if not message else [e, discord.Embed(description=message[0:1500], color=discord.Colour.blue())]

        giveaway_message = await ctx.send(f":tada: **GIVEAWAY!** :tada: \n{role.mention if role else ''}",embeds=embeds, allowed_mentions=discord.AllowedMentions.all(), reply=None)
        await giveaway_message.add_reaction('\U0001f389')
        if pin is True and ctx.channel.permissions_for(ctx.guild.me).manage_messages:
            await giveaway_message.pin()

        reminder_cog = self.bot.get_cog("utility")
        if reminder_cog is None:
            raise commands.BadArgument("This feature is currently unavailable.")

        try:
            timer = await reminder_cog.create_timer(
                duration.dt,
                "giveaway",
                ctx.guild.id,
                ctx.author.id,
                ctx.channel.id,
                giveaway_message.id,
                winners=winners,
                prize=prize,
                message=message,
                role=None if role == None else role.id,
                #requirements=requirements,
                connection=self.bot.db
            )
        except Exception as e:
            traceback_string = "".join(traceback.format_exception(
                    etype=None, value=e, tb=e.__traceback__)
            )
            await ctx.send(str(traceback_string))
            return
        e.set_footer(text=f'{winners} winner{"s" if winners > 1 else ""} | Giveaway ID: {timer.id}')

        return await giveaway_message.edit(f":tada: **GIVEAWAY!** :tada:\n{role.mention if role else ''}",embeds=embeds, allowed_mentions=discord.AllowedMentions.all())
        

    @giveaway.command(name='list')
    @commands.check(Cooldown(4, 8, 6, 8, commands.BucketType.member))
    @commands.bot_has_permissions(send_messages=True, add_reactions=True)
    @commands.has_guild_permissions(manage_guild=True)
    async def giveaway_list(self, ctx: MyContext):
        """List all the active giveaways."""

        cog = self.bot.get_cog("utility")
        if not cog:
            raise commands.BadArgument("This feature is currectly unavailable. Please try again later.")

        embed = Embed()
        embed.colour = discord.Colour.yellow()

        query = """
                SELECT (id, expires, extra, created)
                FROM reminders
                WHERE event = 'giveaway'
                AND extra #>> '{args,0}' = $1
                ORDER BY expires;
                """
        records = await self.bot.db.fetch(query, str(ctx.guild.id))
        if not records:
            return await ctx.send("There are no active giveaways in this guild.")

        to_append = []
        for record in records:
            _id : int = record['row'][0]
            expires : datetime.datetime = pytz.utc.localize(record['row'][1])
            extra : Dict = json.loads(record['row'][2])
            created = pytz.utc.localize(record['row'][3])
            args = extra['args']
            kwargs = extra['kwargs']

            guild_id, host_id, channel_id, giveaway_id = args
            winners = kwargs['winners']
            prize = kwargs['prize']

            to_append.append(
                f"\n\n**{prize}** - {winners} winner{'s' if winners > 1 else ''} - [jump url](https://discord.com/channels/{guild_id}/{channel_id}/{giveaway_id}) - ID: {_id}" # save an api call
                f"\n Created: {discord.utils.format_dt(created, 'R')}"
                f"\n Ends: {discord.utils.format_dt(expires, 'R')}"
                f"\n Host: <@{host_id}>"
            )

        await ctx.paginate(to_append)
            
    @giveaway.command(name='end')
    @commands.check(Cooldown(4, 8, 6, 8, commands.BucketType.member))
    @commands.bot_has_permissions(send_messages=True, add_reactions=True)
    @commands.has_guild_permissions(manage_guild=True)
    async def giveaway_end(self, ctx : MyContext, id : int):
        """
        End a giveaway early.
        
        This is different from canceling it as I will roll the winners.
        
        You can find the giveaway's id in the footer of the giveaway's embed.
        
        You cannot end giveaways that have `None` as their id.
        This is due to them being too short.
        """
        
        query = """
                SELECT extra FROM reminders
                WHERE id = $1
                AND event = 'giveaway'
                AND extra #>> '{args,0}' = $2
                """
        data = await self.bot.db.fetchrow(query, id, str(ctx.guild.id)) # Kinda have to do 2 queries to get the jump_url and proper data
        if not data:
            return await ctx.send(f"Could not delete any giveaways with that ID.\nUse `{ctx.prefix}g list` to list all the running giveaways.")

        extra = json.loads(data['extra'])

        guild_id = extra['args'][0]
        host_id = extra['args'][1]
        channel_id = extra['args'][2]
        message_id = extra['args'][3]
        winners = extra['kwargs']['winners']
        prize = extra['kwargs']['prize']

        _message = extra['kwargs'].get("message")
        role = extra['kwargs'].get("role")

        query = """
                DELETE FROM reminders
                WHERE id=$1
                AND event = 'giveaway'
                AND extra #>> '{args,1}' = $2;
                """
        await self.bot.db.execute(query, id, str(ctx.author.id))

        reminder_cog = self.bot.get_cog("utility")
        if reminder_cog is None:
            raise commands.BadArgument("This feature is currently unavailable.")

        if reminder_cog._current_timer and reminder_cog._current_timer.id == id:
            reminder_cog._task.cancel()
            reminder_cog._task = self.bot.loop.create_task(reminder_cog.dispatch_timers())

        status = await self.end_giveaway(
                        guild_id=guild_id,
                        host_id=host_id,
                        channel_id=channel_id,
                        message_id=message_id,
                        winners=winners,
                        prize=prize,
                        message=_message,
                        role=role
                    )
        if status is False:
            return await ctx.send("Failed to end that giveaway. The giveaway has been deleted from my database.")
        else:
            await ctx.check()
        
    @commands.Cog.listener('on_giveaway_timer_complete')
    async def giveaway_end_event(self, timer):
        guild_id, host_id, channel_id, giveaway_id = timer.args
        winners = timer.kwargs.get("winners")
        prize = timer.kwargs.get("prize")

        _message = timer.kwargs.get('message')
        role = timer.kwargs.get('role')

        await self.bot.wait_until_ready()

        await self.end_giveaway(
            guild_id=guild_id,
            host_id=host_id,
            channel_id=channel_id,
            message_id=giveaway_id,
            winners=winners,
            prize=prize,
            message=_message,
            role=role
        )