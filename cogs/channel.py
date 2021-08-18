import discord
from discord.channel import _channel_factory
from discord.ext import commands, menus
from discord.ext.menus.views import ViewMenuPages

from bot import MyContext

from typing import Optional, Union

import argparse, shlex


class Arguments(argparse.ArgumentParser):
    def error(self, message):
        raise RuntimeError(message)

class ChannelConfirm(discord.ui.View):
    def __init__(self, author):
        super().__init__(timeout=30)
        self.user = author
        self.value = None


    async def on_timeout(self) -> None:
        self.foo.disabled = True
        self.boo.disabled = True
        await self.message.edit(view=self)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.user == interaction.user:
            return True
        await interaction.response.send_message(f"Only {self.user} can use this menu. Please invoke the command yourself to use this.",
                                                ephemeral=True)
        return False

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def foo(self, _, interaction: discord.Interaction) -> None:
        self.value = True

        for item in self.children:
            item.disabled = True

        await interaction.message.edit(view=self)

        self.stop()


    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.gray)
    async def boo(self, _, interaction: discord.Interaction) -> None:
        
        self.value = False

        for item in self.children:
            item.disabled = True

        await interaction.message.edit(view=self)

        self.stop()


class MySource(menus.ListPageSource):
    def __init__(self, data):
        super().__init__(data, per_page=10)

    async def format_page(self, menu, entries):
        offset = menu.current_page * self.per_page

        return '\n'.join(f'{i.mention} | {i.name} | {i.id}' for i in entries)




class channelstats(commands.Cog, description="Channel information."):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(
        name='channel',
        case_insensitive=True,
        invoke_without_command=True
    )
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_guild_permissions(manage_channels=True)
    async def channel_info(self, ctx : MyContext):
        """
        Information about channels.

        This inculdes text channels, voice channels, and stage channels.
        """

        await ctx.send_help('channel')

    @channel_info.command(name='list')
    async def channel_list(self, ctx, *, flags : str = None):
        """
        List all the channel in the server.

        Apply the `--nomenu` flag to send all the channels without menus.
        """

        if flags is None:
            pages = ViewMenuPages(MySource(tuple(ctx.guild.channels)), clear_reactions_after=True)
            await pages.start(ctx)
            return

        parser = Arguments(add_help=False, allow_abbrev=False)
        parser.add_argument('--nomenu', action='store_true')

        try:
            args = parser.parse_args(shlex.split(flags))
        except Exception as e:
            return await ctx.send(str(e))

        if args.nomenu:
            try:
                await ctx.send("\n".join([f"{c.mention} | {c.name} | {c.id}" for c in ctx.guild.channels]))
            except:
                return await ctx.send('Could not fit all the channels in one message. Try using the command without the `--nomenu` flag.')

        else:
            await ctx.send('Could not parse that into a vaild flag.')

        


    @channel_info.command()
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_guild_permissions(manage_channels=True)
    async def delete(self, ctx : MyContext, channel : Union[discord.TextChannel, discord.VoiceChannel, discord.StageChannel, None]):
        """
        Delete a channel.
        
        Can be a Text Channel, Voice Channel, or a Stage Channel.
        """

        channel = channel or ctx.channel
        
        view = ChannelConfirm(ctx.author)
        message = await ctx.send(f'Are you sure you want to delete {channel.mention}',view=view)

        await view.wait()

        if view.value is None:
            await message.delete()
            return await ctx.send('Timed out. Run the command again to delete the channel.')

        elif view.value:

            if channel == ctx.channel:
                return await channel.delete(reason=f'Channel deleted by {ctx.author} (ID {ctx.author.id})')

            await message.delete()
            await channel.delete(reason=f'Channel deleted by {ctx.author} (ID {ctx.author.id})')
            await ctx.send(f"Deleted #{channel.name}")
            
        else:
            await message.delete()
            return await ctx.send('Command canceled.')

    @channel_info.group(name='create',case_insensitive=True, invoke_without_command=True)
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_guild_permissions(manage_channels=True)
    async def channel_create(self, ctx : MyContext):
        """
        Create a channel.
        """
        await ctx.send_help('channel create')

    @channel_create.command(name='text')
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_guild_permissions(manage_channels=True)
    async def channel_create_text(self, ctx : MyContext, name : str, category : Union[discord.CategoryChannel, None]):
        """
        Create a Text Channel
        """

        view = ChannelConfirm(ctx.author)

        message = await ctx.send(f'Are you sure you want to create a channel named "{name}"?',view=view)
        
        await view.wait()

        if view.value is None:
            await message.delete()
            return await ctx.send('Timed out. Run the command again to create the channel.')

        elif view.value:

            #No need to replace spaces as d.py does it for us
            channel = await ctx.guild.create_text_channel(name=name, category=category)

            return await ctx.send(f"Created {channel.mention}")

        else:

            await message.delete()
            return await ctx.send("Command canceled.")
        





        
    
    
        


def setup(bot):
    bot.add_cog(channelstats(bot))

