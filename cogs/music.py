from code import InteractiveConsole
import contextlib
from typing import Any, Optional
from urllib.parse import quote_plus
import discord
import pomice
import asyncio
import math
import random

from discord.ext import commands, menus

from bot import MetroBot
from utils.custom_context import MyContext
from utils.json_loader import read_json
from utils.new_pages import RoboPages, SimplePages
from utils.useful import traceback_maker

_info = read_json('info')

password = _info['database_info']['password']
auth = _info['openrobot_api_key']

spotify_id = _info['spotify']['client_id']
spotify_secret = _info['spotify']['client_secret']


def setup(bot: MetroBot):
    bot.add_cog(music(bot))

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
    def __init__(self, ctx: MyContext, *, track: pomice.Track, player: pomice.Player):
        super().__init__(timeout=None)
        self.ctx: MyContext = ctx
        self.track: pomice.Track = track
        self.player: pomice.Player = player
        self.controller: Optional[discord.Message] = None # will be added in start function dw

    async def start(self) -> discord.Message:
        embed = discord.Embed(
            title='Now Playing', 
            description=f"{'🔴 **LIVE**' if self.track.is_stream else ''} [{self.track.title}]({self.track.uri}) [{self.track.requester.mention}]",
            color=self.ctx.color
        )
        self.controller = await self.ctx.send(embed=embed, view=self, reply=False)
        return self.controller

    def is_privileged(self, interaction: discord.Interaction):
        """Check whether the user is an Admin or DJ."""
        player = self.ctx.voice_client

        return player.dj == interaction.user or interaction.user.guild_permissions.mute_members

    def required(self, ctx: commands.Context):
        """Method which returns required votes based on amount of members in a channel."""
        player: Player = ctx.voice_client
        channel = ctx.bot.get_channel(int(player.channel.id))
        required = math.ceil((len(channel.members) - 1) / 2.5)

        return required

    async def interaction_check(self, interaction: discord.Interaction):
        if not interaction.user.voice:
            return await interaction.response.send_message(f"You must be in my voice channel to interact with the player.", ephemeral=True)
        if interaction.user.voice.channel != self.player.channel:
            return await interaction.response.send_message(f"You must be in my voice channel to interact with the player.", ephemeral=True)
        else:
            return True

    @discord.ui.button(label='Lyrics', emoji='\U0001f4da', style=discord.ButtonStyle.blurple)
    async def lyrics(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        button.disabled = True
        button.style = discord.ButtonStyle.gray
        await self.controller.edit(view=self) # disable this shit

        await interaction.response.defer(ephemeral=True) # Might as well defer since the api usually takes longer than 3 seconds

        headers = {'Authorization' : auth}
        async with self.ctx.bot.session.get(
            f"https://api.openrobot.xyz/api/lyrics/{quote_plus(self.track.title)}", headers=headers) as res:

            if res.status != 200:
                return await interaction.followup.send(
                    "Openrobot API returned a bad response."\
                    "\nThis may be due to the API being down or the song is invaild.",
                    ephemeral=True)

            js = await res.json()

        new_view = RoboPages(source=PlayerViewLyrics(js['lyrics'].split("\n"), js, ctx=self.ctx), ctx=self.ctx, interaction=interaction, compact=True)
        await new_view.start()
        
    @discord.ui.button(label='Pause', emoji='\U000023f8', style=discord.ButtonStyle.blurple)
    async def pause(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:

        if self.player.is_paused or not self.player.is_connected:
            return await interaction.response.send_message("The player is already paused or not playing.", ephemeral=True)

        if self.is_privileged(interaction):
            await interaction.response.defer()
            self.player.pause_votes.clear()
            await self.player.set_pause(True)

            button.disabled = True
            button.style = discord.ButtonStyle.gray
            self.play.disabled = False
            self.play.style = discord.ButtonStyle.blurple
            return await self.controller.edit(view=self)

        required = self.required(self.ctx)
        self.player.pause_votes.add(interaction.user) 

        if len(self.player.pause_votes) >= required:
            await interaction.response.send_message(f"⏸️ Vote to pause the player passed. Pausing player...")
            self.player.pause_votes.clear()
            await self.player.set_pause(True)
            button.disabled = True
            button.style = discord.ButtonStyle.gray
            self.play.disabled = False
            self.play.style = discord.ButtonStyle.blurple
            return await self.controller.edit(view=self)
        else:
            await interaction.response.send_message(f"{interaction.user} has voted to pause the player. Votes: {len(self.player.pause_votes)}/{required}")

    @discord.ui.button(label='Play', emoji='\U000023ef', style=discord.ButtonStyle.gray, disabled=True)
    async def play(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:

        if not self.player.is_paused or not self.player.is_connected:
            return await interaction.response.send_message("The player is already playing or not connected.", ephemeral=True)

        if self.is_privileged(interaction):
            await interaction.response.defer()
            self.player.resume_votes.clear()
            await self.player.set_pause(False)

            button.disabled = True
            button.style = discord.ButtonStyle.gray
            self.pause.disabled = False
            self.pause.style = discord.ButtonStyle.blurple
            return await self.controller.edit(view=self)

        required = self.required(self.ctx)
        self.player.resume_votes.add(interaction.user) 

        if len(self.player.resume_votes) >= required:
            await interaction.response.send_message(f"⏯️ Vote to resume the player passed. Resuming player...")
            self.player.resume_votes.clear()
            await self.player.set_pause(False)
            button.disabled = True
            button.style = discord.ButtonStyle.gray
            self.pause.disabled = False
            self.pause.style = discord.ButtonStyle.blurple
            return await self.controller.edit(view=self)
        else:
            await interaction.response.send_message(f"{interaction.user} has voted to resume the player. Votes: {len(self.player.resume_votes)}/{required}")

    @discord.ui.button(label='Skip', emoji='\U000023ed', style=discord.ButtonStyle.blurple)
    async def skip(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:
        if not self.player.is_connected:
            return await interaction.response.send_message("The player is currently not connected.", ephemeral=True)

        if self.is_privileged(interaction) or interaction.user == self.player.current.requester:
            await self.player.stop()
            self.player.skip_votes.clear()
            await self.controller.delete(silent=True)
            await interaction.response.defer()
            return await self.controller.channel.send(f"\U000023ed Skipped the current song.")

        required = self.required(self.ctx)
        self.player.skip_votes.add(interaction.user)

        if len(self.player.skip_votes) >= required:
            await interaction.response.send_message(f"\U000023ed Voted to skip the song.")
            self.player.skip_votes.clear()
            await self.player.stop()
            await self.controller.delete(silent=True)
        else:
            await interaction.response.send(f"{interaction.user} has voted to skip this song. Votes: {len(self.player.skip_votes)}/{required}")

    @discord.ui.button(emoji='\U0001f6d1', style=discord.ButtonStyle.danger)
    async def stop_player(self, button: discord.ui.Button, interaction: discord.Interaction) -> None:

        if not self.player.is_connected:
            return await interaction.response.send_message("The player is currently not connected.", ephemeral=True)

        if self.is_privileged(interaction):
            await interaction.response.send_message("\U0001f6d1 Stopped the player.")
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True
            await self.controller.edit(view=self)
            return await self.player.teardown(view=self)

        required = self.required(self.ctx)
        self.player.stop_votes.add(interaction.user)

        if len(self.player.stop_votes) >= required:
            await interaction.response.send_message("\U0001f6d1 Vote to stop the player passed. Stopping...")
            for item in self.children:
                if isinstance(item, discord.ui.Button):
                    item.disabled = True
            await self.controller.edit(view=self)
            return await self.player.teardown(view=self)
        else:
            await interaction.response.send_message(f"{interaction.user} has voted to stop the player. Votes: {len(self.player.stop_votes)}/{required}")
    

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

       # Queue up the next track, else teardown the player
        try:
            track: pomice.Track = self.queue.get_nowait()
        except asyncio.queues.QueueEmpty:  
            return await self.teardown()

        await self.play(track)
        if self.controller:
            await self.controller.delete(silent=True)
            
        view = PlayerView(self.context, track=track, player=self)
        self.controller = await view.start()

    async def teardown(self, *, view: Optional[PlayerView] = None):
        """Clear internal states, remove player controller and disconnect."""
        with contextlib.suppress((discord.HTTPException), (KeyError)):
            await self.destroy()
            if view:
                for item in view.children:
                    if isinstance(item, discord.ui.Button):
                        item.disabled = True
                await self.controller.edit(view=view)

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
                    spotify_client_id=spotify_id,
                    spotify_client_secret=spotify_secret
            )
        except Exception as e:
            if str(e) == "A node with identifier 'MAIN' already exists.":
                pass
            else:
                print(traceback_maker(e))
            
        print("Music node created.")

    async def required(self, ctx: commands.Context):
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

    @commands.command(name='lyrics')
    async def lyrics(self, ctx: MyContext, *, song: str):
        """Get the lyrics of a song."""
        
        async with ctx.typing():
            headers = {'Authorization' : auth}
            async with self.bot.session.get(
                f"https://api.openrobot.xyz/api/lyrics/{quote_plus(song)}", headers=headers) as res:

                if res.status != 200:
                    raise commands.BadArgument("Openrobot API returned a bad response.")

                js = await res.json()

            menu = SimplePages(source=LyricsSource(js['lyrics'].split("\n"), js), ctx=ctx, compact=True)
            await menu.start()

    @commands.command(name='join', aliases=['summon', 'connect'])
    async def join(self, ctx: MyContext, *, channel: Optional[discord.VoiceChannel]=None):
        """Join a voice channel."""

        if not channel:
            channel = getattr(ctx.author.voice, "channel", None)
            if not channel:
                raise commands.BadArgument(f"{self.bot.emotes['cross']} You are not in a voice channel!")

        await channel.connect(cls=Player)
        player: Player = ctx.voice_client
        await player.set_context(ctx=ctx)
    
        await ctx.guild.change_voice_state(channel=channel, self_deaf=True) 

        await ctx.send(f"Joined the voice channel {channel.mention}", reply=False)


    @commands.command(name='play')
    async def play(self, ctx: MyContext, *, query: str) -> None:
        """Play a song from the query."""
        if not ctx.author.voice:
            raise commands.BadArgument("You aren't connected to a voice channel.")

        if not (player := ctx.voice_client) or ctx.author.voice.channel != ctx.voice_client.channel:
            await ctx.invoke(self.join)  
        
        player = ctx.voice_client

        results = await player.get_tracks(query, ctx=ctx)

        if not results:
            raise commands.BadArgument("No results were found with that search query.")

        if not player.is_playing and not isinstance(results, pomice.Playlist):
            await player.queue.put(results[0])
            return await player.do_next()

        if player.controller and ctx.channel != player.controller.channel:
            return await ctx.send("The player is currently being played in %s head there to use commands." % player.controller.channel.mention)

        if isinstance(results, pomice.Playlist):
            for track in results.tracks:
                await player.queue.put(track)
            await ctx.send(f"📚 Enqueued `{', '.join(map(lambda x: x.title, results.tracks))}`")
            await player.do_next()
        else:
            track = results[0]
            await player.queue.put(track)
            await ctx.send(f"📚 Enqueued `{results[0]}`")

    @commands.command(aliases=['disconnect', 'leave'])
    async def stop(self, ctx: MyContext):
        """Stop the player."""
        if not ctx.author.voice:
            raise commands.BadArgument("You aren't connected to a voice channel.")

        if not (player := ctx.voice_client) or ctx.author.voice.channel != ctx.voice_client.channel:
            return await ctx.send("You must have the bot in a channel in order to use this command", reply=False)

        if not player.is_connected:
            return

        if await self.is_privileged(ctx):
            await ctx.send('An admin or DJ has stopped the player.', reply=False)
            return await player.teardown(view=None)

        required = self.required(ctx)
        player.stop_votes.add(ctx.author)

        if len(player.stop_votes) >= required:
            await ctx.send('Vote to stop passed. Stopping the player.', reply=False)
            await player.teardown(view=None)
        else:
            await ctx.send(f'{ctx.author.mention} has voted to stop the player. Votes: {len(player.stop_votes)}/{required}', reply=False)


    @commands.command()
    async def volume(self, ctx: MyContext, *, volume: int):
        """Change the players volume, between 1 and 100."""

        if not ctx.author.voice:
            raise commands.BadArgument("You aren't connected to a voice channel.")

        if not (player := ctx.voice_client) or ctx.author.voice.channel != ctx.voice_client.channel:
            return await ctx.send("You must have the bot in a channel in order to use this command", reply=False)

        if not player.is_connected:
            return

        if not await self.is_privileged(ctx):
            return await ctx.send('Only the DJ or admins may change the volume.')

        if not 0 < volume < 101:
            return await ctx.send('Please enter a value between 1 and 100.')

        await player.set_volume(volume*5)
        await ctx.send(f'Set the volume to **{volume}**%', reply=False)

    @commands.command()
    async def shuffle(self, ctx: MyContext):
        """Shuffle the queue."""

        if not ctx.author.voice:
            raise commands.BadArgument("You aren't connected to a voice channel.")

        if not (player := ctx.voice_client) or ctx.author.voice.channel != ctx.voice_client.channel:
            return await ctx.send("You must have the bot in a channel in order to use this command", reply=False)

        if not player.is_connected:
            raise commands.BadArgument("The player is not connected.")

        if player.queue.qsize() < 3:
            return await ctx.send('The queue is empty. Add some songs to shuffle the queue.', reply=False)

        if await self.is_privileged(ctx):
            await ctx.send("An admin or DJ has shuffled the queue.", reply=False)
            player.shuffle_votes.clear()
            return random.shuffle(player.queue._queue)

        required = self.required(ctx)
        player.shuffle_votes.add(ctx.author)

        if len(player.shuffle_votes) >= required:
            await ctx.send("Vote to shuffle passed. Shuffling queue.", reply=False)
            player.shuffle_votes.clear()
            return random.shuffle(player.queue._queue)
        else:
            await ctx.send(f"{ctx.author.mention} has shuffled the queue. Votes: {len(self.player.shuffle_votes)}/{required}")


