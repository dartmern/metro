import discord
from discord.ext import commands, menus
from discord import app_commands

import contextlib
import logging
import traceback
from typing import Any, Optional, Union
from urllib.parse import quote_plus
from aiohttp import ClientConnectorError
import pomice
import asyncio
import math
import random
import yarl

from bot import MetroBot
from utils.custom_context import MyContext
from utils.json_loader import read_json
from utils.new_pages import RoboPages, SimplePages

_info = read_json('info')

password = _info['database_info']['password']
auth = _info['openrobot_api_key']

spotify_id = _info['spotify']['client_id']
spotify_secret = _info['spotify']['client_secret']


async def setup(bot: MetroBot):
    await bot.add_cog(music(bot))

class PlayerViewLyrics(menus.ListPageSource):
    def __init__(self, data, js: Any, *, ctx: MyContext):
        super().__init__(data, per_page=18)
        self.js = js
        self.ctx = ctx

    async def format_page(self, menu, entries):
        embed = discord.Embed(color=self.ctx.color)
        embed.title = self.js['title']
        embed.set_thumbnail(url=self.js['images']['background'])

        embed.description = "\n".join(entries)
        return embed

class PlayerView(discord.ui.View):
    def __init__(self, ctx: MyContext, *, track: pomice.Track, player):
        super().__init__(timeout=None)
        self.ctx: MyContext = ctx
        self.track: pomice.Track = track
        self.player: Player = player
        self.controller: Optional[discord.Message] = None # will be added in start function dw
        self.lyrics_dict: dict = None # the lyrics dict that gets added upon request

    async def start(self) -> discord.Message:
        embed = discord.Embed(
            title='Now Playing', 
            description=f"{'🔴 **LIVE**' if self.track.is_stream else ''} [{self.track.title}]({self.track.uri})\n"\
                        f"Requested by: {self.track.requester.mention}",
            color=self.ctx.color if self.ctx else discord.Colour.yellow()
        )
        self.controller = await self.ctx.send(embed=embed, view=self)
        return self.controller

    def is_privileged(self, interaction: discord.Interaction):
        """Check whether the user is an Admin or DJ."""
        player: Player = self.ctx.voice_client

        return player.dj == interaction.user or interaction.user.guild_permissions.mute_members or interaction.user == self.player.current.requester

    def required(self, ctx: commands.Context):
        """Method which returns required votes based on amount of members in a channel."""
        player: Player = ctx.voice_client
        channel: discord.VoiceChannel = ctx.bot.get_channel(int(player.channel.id))
        required = math.ceil((len(channel.members) - 1) / 2.5)

        return required

    async def interaction_check(self, interaction: discord.Interaction):
        if not interaction.user.voice or (interaction.user.voice.channel != self.player.channel):
            return await interaction.response.send_message(f"You must be in my voice channel to interact with the player.", ephemeral=True)
        else:
            return True

    @discord.ui.button(label='Lyrics', emoji='\U0001f4da', style=discord.ButtonStyle.blurple)
    async def lyrics(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:

        await interaction.response.defer(ephemeral=True)

        # this way only 1 request can be made per song and can be viewed by anyone upon request
        if not self.lyrics_dict:
            url = yarl.URL('https://api.yodabot.xyz/api/lyrics/search').with_query({'q': quote_plus(self.track.title)})
            async with self.ctx.bot.session.get(url) as res:

                self.lyrics_dict = await res.json()
                if self.lyrics_dict['title'] is None:
                    return await interaction.followup.send('Could not find song lyrics.', ephemeral=True)

        if self.lyrics_dict['title'] is None:
            return await interaction.followup.send('Could not find song lyrics.', ephemeral=True)

        source = PlayerViewLyrics(self.lyrics_dict['lyrics'].split('\n'), self.lyrics_dict, ctx=self.ctx)
        view = RoboPages(source=source, ctx=self.ctx, interaction=interaction, compact=True, hide=True)
        await view.start()
        
    @discord.ui.button(label='Pause', emoji='\U000023f8', style=discord.ButtonStyle.blurple)
    async def pause(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer()

        if self.is_privileged(interaction):
            embed = self.controller.embeds[0].copy()
            if self.player.is_paused:
                # the user wants to play
                await self.player.set_pause(False)
                button.label, button.emoji = 'Pause', '\U000023f8'
            else:
                # the user wants to pause
                await self.player.set_pause(True)
                button.label, button.emoji = 'Play', '\U000025b6'
                embed.set_footer(text='Player is currently paused.')
            await self.controller.edit(view=self, embed=embed)
            return 

    @discord.ui.button(label='Skip', emoji='\U000023ed', style=discord.ButtonStyle.blurple)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        await interaction.response.defer()

        if self.is_privileged(interaction):
            await self.player.stop()
            return 
            
        required = self.required(self.ctx)
        self.player.skip_votes.add(interaction.user)

        if len(self.player.skip_votes) >= required:
            await interaction.followup.send(f"\U000023ed Voted to skip the song.")
            self.player.skip_votes.clear()
            await self.player.stop()
            
        else:
            await interaction.followup.send(f"{interaction.user} has voted to skip this song. Votes: {len(self.player.skip_votes)}/{required}\n> Click the **Skip** button to vote to skip.")

    @discord.ui.button(emoji='<:disconnect:1040449193753464942>', style=discord.ButtonStyle.danger)
    async def stop_player(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        
        await interaction.response.defer()

        if self.is_privileged(interaction):
            await self.player.teardown()
            return 

        required = self.required(self.ctx)
        self.player.stop_votes.add(interaction.user)

        if len(self.player.stop_votes) >= required:
            await interaction.followup.send("\U0001f6d1 Vote to stop the player passed. Stopping...")
            await self.player.teardown(view=self)
            return 
        else:
            await interaction.followup.send(f"{interaction.user} has voted to stop the player. Votes: {len(self.player.stop_votes)}/{required}\n> Click the {self.ctx.bot.emojis['disconnect']} emoji to vote to stop.")

class Player(pomice.Player):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.queue = asyncio.Queue()
        self.controller: Union[discord.Message, discord.WebhookMessage] = None
        self.context: MyContext = None
        self.dj: discord.Member = None

        self.skip_votes = set()
        self.shuffle_votes = set()
        self.stop_votes = set()

    async def do_next(self) -> None:
        # Clear the votes for a new song

        self.skip_votes.clear()
        self.shuffle_votes.clear()
        self.stop_votes.clear()

       # Queue up the next track, else teardown the player
        try:
            track: pomice.Track = self.queue.get_nowait()
        except asyncio.queues.QueueEmpty:  
            return await self.teardown()

        await self.play(track)
        if self.controller:
            await self.controller.edit(view=None)
            
        view = PlayerView(self.context, track=track, player=self)
        self.controller = await view.start()

    async def teardown(self):
        """Clear internal states, remove player controller and disconnect."""
        with contextlib.suppress((discord.HTTPException), (KeyError)):
            await self.destroy()
            await self.controller.edit(view=None)

    async def set_context(self, ctx: commands.Context):
        """Set context for the player"""
        self.context = ctx 
        self.dj = ctx.author 

class LyricsSource(menus.ListPageSource):
    def __init__(self, data, js: Any):
        super().__init__(data, per_page=18)
        self.js = js

    async def format_page(self, menu: SimplePages, entries):
        menu.embed.title = self.js['title']
        menu.embed.set_thumbnail(url=self.js['images']['background'])

        menu.embed.description = "\n".join(entries)
        return menu.embed

class music(commands.Cog, description='Play high quality music in a voice channel.'):
    def __init__(self, bot: MetroBot):
        self.bot = bot

        self.pomice = pomice.NodePool()
        bot.loop.create_task(self.start_nodes())

    @property
    def emoji(self) -> str:
        return '\U0001f3b5'

    async def start_nodes(self):
        await self.bot.wait_until_ready()
        try:
            await self.pomice.create_node(
                    bot=self.bot,
                    host="127.0.0.1",
                    port="3030",
                    password=password,
                    identifier="MAIN",
                    session=self.bot.session
            )
            logging.info("Music node created.")
        except Exception as e:
            if isinstance(e, ClientConnectorError):
                pass
            elif str(e) == "A node with identifier 'MAIN' already exists.":
                pass
            else:
                traceback.print_exception(e)
                logging.info('The music server cannot be connected at this time.')

    def required(self, ctx: commands.Context):
        """Method which returns required votes based on amount of members in a channel."""
        player: Player = ctx.voice_client
        channel = self.bot.get_channel(int(player.channel.id))
        required = math.ceil((len(channel.members) - 1) / 2.5)

        if ctx.command.name == 'stop':
            if len(channel.members) == 3:
                required = 2

        return required

    async def is_privileged(self, ctx: MyContext):
        """Check whether the user is an Admin or DJ."""
        player: Player = ctx.voice_client

        return player.dj == ctx.author or ctx.author.guild_permissions.mute_members

    @commands.Cog.listener()
    async def on_pomice_track_end(self, player: Player, track, _):
        await player.do_next()

    @commands.Cog.listener()
    async def on_pomice_track_stuck(self, player: Player, track, _):
        await player.do_next()

    @commands.Cog.listener()
    async def on_pomice_track_exception(self, player: Player, track, _):
        await player.do_next()

    @commands.hybrid_command(name='lyrics')
    @app_commands.describe(song='The song you want to search for.')
    async def lyrics(self, ctx: MyContext, *, song: str):
        """Get the lyrics of a song."""
        
        url = yarl.URL('https://api.yodabot.xyz/api/lyrics/search').with_query({'q': quote_plus(song)})
        async with ctx.typing():
            async with self.bot.session.get(url) as res:

                js = await res.json()
                if js['title'] is None:
                    return await ctx.send('Song not found.', hide=True)

            menu = SimplePages(source=LyricsSource(js['lyrics'].split("\n"), js), ctx=ctx, compact=True)
            await menu.start()

    @commands.hybrid_command(name='join', aliases=['summon', 'connect'])
    @app_commands.describe(channel='The voice channel you want me to join.')
    async def join(self, ctx: MyContext, *, channel: Optional[discord.VoiceChannel] = None):
        """Join a voice channel."""

        if not channel:
            channel = getattr(ctx.author.voice, "channel", None)
            if not channel:
                raise commands.BadArgument(f"{self.bot.emotes['cross']} You are not in a voice channel!")

        await channel.connect(cls=Player)
        player: Player = ctx.voice_client
        await player.set_context(ctx=ctx)
    
        await ctx.guild.change_voice_state(channel=channel, self_deaf=True) 
        await ctx.send(f"Joined the voice channel {channel.mention}")

    @commands.hybrid_command(name='play', aliases=['p'])
    @app_commands.describe(query='The song query you want me to play.')
    async def play(self, ctx: MyContext, *, query: str) -> None:
        """Play a song from the query."""
        if not ctx.author.voice:
            return await ctx.send("You aren't connected to a voice channel.", hide=True)

        if not ctx.voice_client or ctx.author.voice.channel != ctx.voice_client.channel:
            await ctx.invoke(self.join)  
        
        player: Player = ctx.voice_client
        results = await player.get_tracks(query, ctx=ctx)

        if not results:
            return await ctx.send("No results were found with that search query.", hide=True)

        if not player.is_playing and not isinstance(results, pomice.Playlist):
            await player.queue.put(results[0])
            return await player.do_next()

        if player.controller and (ctx.channel.id != player.controller.channel.id):           
            channel = f'<#{player.controller.channel.id}>'
            return await ctx.send(f"The player is currently being played in {channel} head there to use commands.", hide=True)

        if isinstance(results, pomice.Playlist):
            for track in results.tracks:
                await player.queue.put(track)
            await ctx.send(f"📚 Enqueued `{', '.join(map(lambda x: x.title, results.tracks))}`", hide=True)
            await player.do_next()
        else:
            track = results[0]
            await player.queue.put(track)
            await ctx.send(f"📚 Enqueued `{results[0]}`", hide=True)

    @commands.hybrid_command(aliases=['disconnect', 'leave'])
    async def stop(self, ctx: MyContext):
        """Stop the player."""

        if not ctx.author.voice:
            raise commands.BadArgument("You aren't connected to a voice channel.")

        if not ctx.voice_client or ctx.author.voice.channel != ctx.voice_client.channel:
            return await ctx.send("You must have the bot in a channel in order to use this command")
        player: Player = ctx.voice_client

        if not player.is_connected:
            return

        if await self.is_privileged(ctx):
            await ctx.send('An admin or DJ has stopped the player.')
            await player.teardown()
            return

        required = self.required(ctx)
        player.stop_votes.add(ctx.author)

        if len(player.stop_votes) >= required:
            await ctx.send('Vote to stop passed. Stopping the player.')
            await player.teardown()
        else:
            await ctx.send(f'{ctx.author.mention} has voted to stop the player. Votes: {len(player.stop_votes)}/{required}')

    @commands.hybrid_command()
    @app_commands.describe(volume='The volume you want to change. Must be 1-100')
    async def volume(self, ctx: MyContext, *, volume: commands.Range[int, 1, 100]):
        """Change the volume of the music being played."""

        if not ctx.author.voice:
            raise commands.BadArgument("You aren't connected to a voice channel.")

        if not ctx.voice_client or ctx.author.voice.channel != ctx.voice_client.channel:
            return await ctx.send("You must have the bot in a channel in order to use this command", reply=False)

        player: Player = ctx.voice_client
        if not player.is_connected:
            return

        if not await self.is_privileged(ctx):
            return await ctx.send('Only the DJ or admins may change the volume.')

        if not 0 < volume < 101:
            return await ctx.send('Volume should be a number in between 1 and 100.')

        await player.set_volume(volume*5)
        await ctx.send(f'Set the volume to **{volume}**%', reply=False)
