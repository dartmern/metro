import asyncio
import datetime
import re
from typing import List, Optional
import discord
from discord import app_commands
from discord.ext import commands
import pytz
from requests import head
from bot import MetroBot
from utils.embeds import create_embed
from ..utility import Timer, utility
from .views.view import PollView
from utils.constants import TESTING_GUILD

from .time_helpers import HumanTime
from ..developer import TabularData

async def setup(bot: MetroBot):
    await bot.add_cog(AdvancedPoll(bot))

class AdvancedPoll(commands.Cog, description="Create more advanced and engaging polls."):
    def __init__(self, bot: MetroBot) -> None:
        self.bot = bot

    @app_commands.command(name='poll')
    @app_commands.guilds(TESTING_GUILD)
    @app_commands.describe(duration='The duration this poll will last for.')
    @app_commands.describe(question='The question you would like to poll.')
    @app_commands.describe(channel='The channel to post this poll. Defaults to the current channel.')
    @app_commands.describe(public='Whether to make the results of this poll public. Defaults to False.')
    @app_commands.describe(anonymous='Whether poll participants are anonymous. Defaults to False.')
    async def poll_command(
        self, 
        interaction: discord.Interaction, 
        duration: str,
        question: str,
        channel: Optional[discord.TextChannel],
        public: Optional[bool] = False,
        anonymous: Optional[bool] = False,
    ):
        """Start a modal based poll."""
        channel = channel or interaction.channel

        if not interaction.permissions.manage_guild:
            # most likely will be changed
            # when this was written permissions v2 
            # has not yet been released
            return await interaction.response.send_message("You don't have the Manage Guild permission to use this command.", ephemeral=True)
        
        created_at = discord.utils.utcnow()
        try:
            duration = await HumanTime(duration).convert(created_at, duration)
        except Exception as e:
            return await interaction.response.send_message(str(e), ephemeral=True)

        if duration.dt > (created_at + datetime.timedelta(days=7)):
            return await interaction.response.send_message('Polls may not be longer than 7 days.', ephemeral=True)

        if duration.dt < (created_at + datetime.timedelta(seconds=4)):
            return await interaction.response.send_message('Polls may not be shorter than 1 minute.', ephemeral=True)
        
        embed = create_embed(f'Creating poll in {channel.mention}...', color=discord.Color.green())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        # start the poll creation process
        # includes creating then sending
        # the embed and starting a timer

        title = f"{interaction.user} is asking a question."

        embed = discord.Embed(color=discord.Color.green())
        embed.description = f'*{question}*\n\nThis poll closes {discord.utils.format_dt(duration.dt, "R")}.'
        embed.set_author(name=title, icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text="Your response may be viewed by the poll's author.")

        view = PollView(question=question, title=title, close_time=duration.dt)
        view.message = await channel.send(embed=embed, view=view)

        # create a timer for the poll
        # the timer's created time is  
        # when the command was invoked

        reminder_cog: utility = interaction.client.get_cog('utility')
        if not reminder_cog:
            # if the reminder cog is unloaded timers don't work
            embed = create_embed('This feature is currently unavailable. Sorry.', color=discord.Color.orange())
            return await interaction.edit_original_message(embed=embed)
        
        try:
            await reminder_cog.create_timer(
                duration.dt,
                'poll',
                interaction.guild_id,
                channel.id,
                view.message.id,
                host=interaction.user.id,
                question=question,
                created_at=created_at,
                connection=interaction.client.db
            )
        except Exception as e:
            return await interaction.edit_original_message(content=f"An unknown error occurred: {e}")

        embed = create_embed(f'Created poll in {channel.mention}\n- Make sure to have your DMs open for results.')
        await interaction.edit_original_message(embed=embed)


    @commands.Cog.listener()
    async def on_poll_timer_complete(self, timer: Timer):
        guild_id, channel_id, message_id = timer.args
        
        host_id = timer.kwargs.get('host')
        question = timer.kwargs.get('question')

        await self.bot.wait_until_ready()

        guild = self.bot.get_guild(guild_id)
        if not guild:
            # rip guild
            return 

        channel = self.bot.get_channel(channel_id)
        if not channel:
            # rip channel
            return 

        try:
            message = await channel.fetch_message(message_id)
        except (discord.HTTPException, discord.NotFound):
            # rip message
            return

        host = guild.get_member(host_id)
        if not host:
            try:
                host = await self.bot.fetch_user(host_id)
                icon_url = host.display_avatar.url
            except:
                host = "Host ID: %s" % host_id
                icon_url = None
        else:
            icon_url = host.display_avatar.url

        button = discord.ui.Button(label='Answer')
        button.disabled = True

        view = discord.ui.View()
        view.add_item(button)

        title = f"{host} asked a question."
        time_fmt = discord.utils.format_dt(pytz.utc.localize(timer.created_at), 'R')

        embed = discord.Embed(color=discord.Color.light_gray())
        embed.set_author(name=title, icon_url=icon_url)
        embed.description = f"*{question}*\n\nThis poll closed {time_fmt}."
        await message.edit(view=view, embed=embed)

        data = await self.bot.db.fetch('SELECT author_id, response FROM poll_entries WHERE poll_id = $1', message.id)

        if isinstance(host, str):
            additional_message = f'There was an error fetching the host of this poll. Maybe they left?'
        else:
            additional_message = ''

        if not data:
            msg = 'It also does not seem like anyone answered this poll.'
        else:
            headers = list(data[0].keys())
            table = TabularData()
            table.set_columns(headers)
            table.add_rows(list(r.values()) for r in data)
            render = table.render()

            async with self.bot.session.post(f"https://mystb.in/documents", data=render) as s:
                res = await s.json()
                url_key = res['key']

            poll_results = f"https://mystb.in/{url_key}"

            msg = f'The results of this poll can be viewed [here]({poll_results} \"Click for a dumped mystbin of the results\").' 

        embed = create_embed(
            f'{additional_message}\n{msg}', 
            color=discord.Color.light_gray()
        )
        return await message.reply(embed=embed)
