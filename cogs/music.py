import contextlib
from typing import Optional
import discord
import pomice
import asyncio
import math
import random

from discord.ext import commands

from bot import MetroBot
from utils.custom_context import MyContext
from utils.json_loader import read_json

password = read_json('info')['database_info']['password']

def setup(bot: MetroBot):
    bot.add_cog(music(bot))

class Player(pomice.Player):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.queue = asyncio.Queue()
        self.controller: discord.Message = None
        self.context: MyContext = None
        self.dj: discord.Member = None

        self.pause_votes = set()
        self.resume_votes = set()
        self.skip_votes = set()
        self.shuffle_votes = set()
        self.stop_votes = set()

    async def do_next(self) -> None:
        # Clear the votes for a new song
        self.pause_votes.clear()
        self.resume_votes.clear()
        self.skip_votes.clear()
        self.shuffle_votes.clear()
        self.stop_votes.clear()

        # Check if theres a controller still active and deletes it
        if self.controller:
            await self.controller.delete(silent=True)        

       # Queue up the next track, else teardown the player
        try:
            track: pomice.Track = self.queue.get_nowait()
        except asyncio.queues.QueueEmpty:  
            return await self.teardown()

        await self.play(track)

        # Call the controller (a.k.a: The "Now Playing" embed) and check if one exists

        if track.is_stream:
            embed = discord.Embed(title="Now playing", description=f":red_circle: **LIVE** [{track.title}]({track.uri}) [{track.requester.mention}]")
            self.controller = await self.context.send(embed=embed)
        else:
            embed = discord.Embed(title=f"Now playing", description=f"[{track.title}]({track.uri}) [{track.requester.mention}]")
            self.controller = await self.context.send(embed=embed)


    async def teardown(self):
        """Clear internal states, remove player controller and disconnect."""
        with contextlib.suppress((discord.HTTPException), (KeyError)):
            await self.destroy()
            if self.controller:
                await self.controller.delete() 

    async def set_context(self, ctx: commands.Context):
        """Set context for the player"""
        self.context = ctx 
        self.dj = ctx.author 


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

        await self.pomice.create_node(
            bot=self.bot,
            host="0.0.0.0",
            port="2333",
            password=password,
            identifier="MAIN",
            spotify_client_id="d31d8bdbe41d4ca5937bd503e1f098b2",
            spotify_client_secret="e209c01ae7b646379ca21d08b7262ca8"
        )
        print("Music node created.")

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

    @commands.command(name='join', aliases=['summon', 'connect'])
    async def join(self, ctx: MyContext, *, channel: Optional[discord.VoiceChannel]=None):
        """Join a voice channel."""

        if not channel:
            channel = getattr(ctx.author.voice, "channel", None)
            if not channel:
                raise commands.BadArgument(f"{self.bot.emotes['cross']} You are not in a voice channel!")

        await ctx.author.voice.channel.connect(cls=Player)
        player: Player = ctx.voice_client
        player.set_context(ctx=ctx)

        await ctx.send(f"Joined the voice channel {channel.mention}")

    @commands.command(name='disconnect', aliases=['leave'])
    async def disconnect(self, ctx: MyContext):
        """Disconnect from the voice channel."""

        if not (player := ctx.voice_client):
            raise commands.BadArgument(f"{self.bot.emotes['cross']} The bot must be in your voice channel to use this.")

        await player.destroy()
        await ctx.send("Left the voice channel.")

    
    @commands.command(name='play')
    async def play(self, ctx: MyContext, *, query: str) -> None:
        """Play a song from the query."""

        if not (player := ctx.voice_client):
            await ctx.invoke(self.join)  

        results = await player.get_trackers(query, ctx=ctx)

        if not results:
            raise commands.BadArgument("No results were found with that search query.")

        if isinstance(results, pomice.Playlist):
            for track in results.tracks:
                await player.queue.put(track)
        else:
            track = results[0]
            await player.queue.put(track)

        if not player.is_playing:
            await player.do_next()

    


