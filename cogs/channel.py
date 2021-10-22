import discord
from discord.channel import _channel_factory
from discord.enums import try_enum
from discord.ext import commands, menus
from discord.ext.menus.views import ViewMenuPages

from bot import MyContext

from typing import Optional, Union

import argparse, shlex

from utils.new_pages import SimplePages


class Arguments(argparse.ArgumentParser):
    def error(self, message):
        raise RuntimeError(message)


class ChannelSource(menus.ListPageSource):
    async def format_page(self, menu, entries):
        pages = []
        for index, entry in enumerate(entries, start=menu.current_page * self.per_page):
            pages.append(f'{entry.mention} | {entry.name} | {entry.id}')

        maximum = self.get_max_pages()
        if maximum > 1:
            footer = f'Page {menu.current_page + 1}/{maximum} ({len(self.entries)} entries)'
            menu.embed.set_footer(text=footer)

        menu.embed.description = '\n'.join(pages)
        return menu.embed


class channelstats(commands.Cog, description="Channel information."):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(
        name='channel',
        case_insensitive=True,
        invoke_without_command=True
    )
    @commands.bot_has_permissions(send_messages=True)
    async def channel_info(self, ctx : MyContext):
        """
        Information about channels.

        This inculdes text channels, voice channels, and stage channels.
        """

        await ctx.send_help('channel')

    @channel_info.command(name='list')
    @commands.bot_has_permissions(send_messages=True)
    async def channel_list(self, ctx, *, flags : str = None):
        """
        List all the channel in the server.

        Apply the `--nomenu` flag to send all the channels without menus.
        """

        if flags is None:
            pages = SimplePages(source=ChannelSource(list(ctx.guild.channels),per_page=8),ctx=ctx)
            await pages.start()
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
    @commands.bot_has_guild_permissions(manage_channels=True, send_messages=True)
    async def delete(self, ctx : MyContext, channel : Union[discord.TextChannel, discord.VoiceChannel, discord.StageChannel, None]):
        """
        Delete a channel.
        
        Can be a Text Channel, Voice Channel, or a Stage Channel.
        """

        channel = channel or ctx.channel

        confirm = await ctx.confirm(f'Are you sure you want to delete {channel.mention}',delete_after=True, timeout=30)

        if confirm is None:
            return await ctx.send(f'Timed out.')

        if confirm is False:
            return await ctx.send(f'Canceled.')


        else:

            if channel == ctx.channel:
                return await channel.delete(reason=f'Channel deleted by {ctx.author} (ID {ctx.author.id})')

            await channel.delete(reason=f'Channel deleted by {ctx.author} (ID {ctx.author.id})')
            await ctx.send(f"Deleted #{channel.name}")
            
        

    @channel_info.group(name='create',case_insensitive=True, invoke_without_command=True)
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_guild_permissions(manage_channels=True, send_messages=True)
    async def channel_create(self, ctx : MyContext):
        """
        Create a channel.
        """
        await ctx.send_help('channel create')

    @channel_create.command(name='text')
    @commands.has_guild_permissions(manage_channels=True)
    @commands.bot_has_guild_permissions(manage_channels=True, send_messages=True)
    async def channel_create_text(self, ctx : MyContext, name : str, category : Union[discord.CategoryChannel, None]):
        """
        Create a Text Channel
        """

        confirm = await ctx.confirm(f'Are you sure you want to create a channel named "{name}"?',delete_after=True, timeout=30)

        if confirm is None:
            return await ctx.send(f'Timed out.')

        if confirm is False:
            return await ctx.send(f'Canceled.')

        else:

            #No need to replace spaces as d.py does it for us
            channel = await ctx.guild.create_text_channel(name=name, category=category)

            return await ctx.send(f"Created {channel.mention}")



    
    
        





        
    
    
        


def setup(bot):
    bot.add_cog(channelstats(bot))

