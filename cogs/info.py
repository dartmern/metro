import discord
from discord import utils
from discord.ext import commands, menus
from discord.ext.menus.views import ViewMenuPages

from typing import Optional
import unicodedata

from utils.useful import Embed
from discord.ext.commands.cooldowns import BucketType

import time
import json
from pathlib import Path
import inspect
import os


from utils.useful import Embed, get_bot_uptime
from utils.pages import ExtraPages



def get_path():
    """
    A function to get the current path to bot.py
    Returns:
     - cwd (string) : Path to bot.py directory
    """
    cwd = Path(__file__).parents[1]
    cwd = str(cwd)
    return cwd


def chunkIt(seq, num):
    avg = len(seq) / float(num)
    out = []
    last = 0.0

    while last < len(seq):
        out.append(seq[int(last):int(last + avg)])
        last += avg

    return out


class Source(menus.ListPageSource):
    def __init__(self, entries):
        super().__init__(entries=entries, per_page=4)

    async def format_page(self, menu, entries):
        
        maximum = self.get_max_pages()
        embed=discord.Embed()
        embed.description='\n'.join(f"{i}\n**ID:** {i.id}\n**GUILD:** {i.guild}" for i in entries)

        embed.set_footer(text=f'[{menu.current_page + 1}/{maximum}]')
        return embed
        

class info(commands.Cog, description="Information about members, guilds, or roles."):
    def __init__(self, bot):
        self.bot = bot

    async def say_permissions(self, ctx, member, channel):
        permissions = channel.permissions_for(member)
        e = discord.Embed(colour=member.colour)
        avatar = member.avatar.url

        if avatar is None:
            e.set_author(name=str(member))
        else:
            e.set_author(name=str(member), url=avatar)
        allowed, denied = [], []
        for name, value in permissions:
            name = name.replace('_', ' ').replace('guild', 'server').title()
            if value:
                allowed.append(name)
            else:
                denied.append(name)

        e.add_field(name='Allowed', value='\n'.join(allowed))
        e.add_field(name='Denied', value='\n'.join(denied))
        await ctx.send(embed=e)

    @commands.command(name='permissions',brief="Shows a member's permissions in a specific channel.")
    @commands.guild_only()
    @commands.bot_has_permissions(send_messages=True)
    async def member_perms(self, ctx, member : Optional[discord.Member], channel : Optional[discord.TextChannel]):
        """Shows a member's permissions in a specific channel.

        If no channel is given then it uses the current one.

        You cannot use this in private messages. If no member is given then
        the info returned will be yours.
        """

        channel = channel or ctx.channel
        if member is None:
            member = ctx.author

        await self.say_permissions(ctx, member, channel)

    @commands.command()
    @commands.bot_has_permissions(send_messages=True)
    async def charinfo(self, ctx, *, characters: str):
        """Shows you information about a number of characters.
        Only up to 25 characters at a time.
        """

        def to_string(c):
            digit = f'{ord(c):x}'
            name = unicodedata.name(c, 'Name not found.')
            return f'`\\U{digit:>08}`: {name} - {c} \N{EM DASH} <http://www.fileformat.info/info/unicode/char/{digit}>'

        msg = '\n'.join(map(to_string, characters))
        if len(msg) > 2000:
            return await ctx.send('Output too long to display.')
        await ctx.send(msg)


    @commands.command(aliases=['ui','whois'])
    @commands.bot_has_permissions(send_messages=True)
    async def userinfo(self, ctx, member : Optional[discord.Member]):
        """
        Shows all the information about the specified user.
        If user isn't specified, it defaults to the author.
        """

        member = member or ctx.author

        embed = discord.Embed(
            description=member.mention,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(
            name="Joined at",
            value=f"{discord.utils.format_dt(member.joined_at)}\n({discord.utils.format_dt(member.joined_at, 'R')})",
            inline=True
        )
        embed.add_field(
            name="Created at",
            value=f"{discord.utils.format_dt(member.created_at)}\n({discord.utils.format_dt(member.created_at, 'R')})",
            inline=True

        )
        embed.set_thumbnail(url=member.avatar.url)
        embed.set_author(name=member, icon_url=member.avatar.url)
        embed.set_footer(text=f'User ID: {member.id}')

        roles = member.roles[1:30]

        if roles:
            embed.add_field(
                name=f"Roles [{len(member.roles) - 1}]",
                value=" ".join(f"{role.mention}" for role in roles),
                inline=False,
            )
        else:
            embed.add_field(
                name=f"Roles [{len(member.roles) - 1}]",
                value="This member has no roles",
                inline=False,
            )

        await ctx.send(embed=embed)


    @commands.command()
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_permissions(send_messages=True)
    async def roles(self, ctx):
        """
        View all the roles in the guild.
        Ordered from top to bottom.
        """

        if not ctx.guild.roles:
            return await ctx.reply(f"This guild does not have any roles.")

        embed = Embed(
            description="".join(f"\n{role.mention} - {role.id}" for role in ctx.guild.roles)
        )
        await ctx.send(embed=embed)


    @commands.command(name='prefix')
    @commands.bot_has_permissions(send_messages=True)
    async def set_prefix(self, ctx, prefix : Optional[str]):
        """
        Set the prefix for this guild.
        (Needs `manage_guild` permission to work)
        """

        if prefix is None:
            prefix = 'm.'


        data = await self.bot.db.fetch('SELECT prefix FROM prefixes WHERE "guild_id" = $1', ctx.guild.id)
        if len(data) == 0: 
            await self.bot.db.execute('INSERT into prefixes ("guild_id", prefix) VALUES ($1, $2)', ctx.guild.id, prefix)

        else:
            await self.bot.db.execute('UPDATE prefixes SET prefix = $1 WHERE "guild_id" = $2', prefix, ctx.guild.id)
        
        await ctx.send('Set the prefix for **{}** to `{}`'.format(ctx.guild.name, prefix))

        
    

    @commands.command(hidden=True)
    @commands.is_owner()  
    @commands.bot_has_permissions(send_messages=True)  
    async def tags(self, ctx):
        await ctx.send('Loading up tags... This could take up to 2 minutes in ideal conditions. All other commands have paused.',delete_after=3)

        DPY_GUILD = ctx.bot.get_guild(336642139381301249)

        tags = []

        cwd = get_path()
        with open(cwd+'/config/'+'tags.txt', 'r', encoding='utf8') as file:
            for line in file.read().split("\n"):
                id = line[-51:]
                id = id[:18]

                try:
                    id = DPY_GUILD.get_member(int(id))
                except:
                    continue

                if id not in DPY_GUILD.members:
                    tag = line[10:112]
                    tag = tag.strip()
                    tags.append(f'{tag}')

        
        
        m = chunkIt(tags, 5)
        


        for i in m:
            await ctx.author.send(str(i))
        await ctx.send('{} Finished! Check your DMs!.'.format(ctx.author.mention),delete_after=.1)


    @commands.command(aliases=['sourcecode', 'code'],
                      )
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def source(self, ctx, *, command: str = None):
        """
        Links to the bot's source code, or a specific command's
        """
        source_url = 'https://github.com/dartmern/metro'
        branch = 'master'

        if command is None:
            embed = Embed(description=f"take the [entire repo]({source_url})")
            return await ctx.send(embed=embed)

        if command == 'help':
            src = type(self.bot.help_command)
            module = src.__module__
            filename = inspect.getsourcefile(src)
        else:
            obj = self.bot.get_command(command.replace('.', ' '))
            if obj is None:
                embed = Embed(description=f"take the [**entire repo**]({source_url})")
                return await ctx.send(embed=embed)

            src = obj.callback.__code__
            module = obj.callback.__module__
            filename = src.co_filename

        lines, firstlineno = inspect.getsourcelines(src)
        if not module.startswith('discord'):
            # not a built-in command
            location = os.path.relpath(filename).replace('\\', '/')
        else:
            location = module.replace('.', '/') + '.py'
            source_url = 'https://github.com/Rapptz/discord.py'
            branch = 'master'

        final_url = f'<{source_url}/blob/{branch}/{location}#L{firstlineno}-L{firstlineno + len(lines) - 1}>'
        embed = Embed(color=ctx.me.color,
                              description=f"source code for [`{command}`]({final_url})")
        await ctx.send(embed=embed)


    @commands.command()
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def convert(self, ctx, id : int):

        try:
            member = self.bot.get_member(id)

            return await ctx.send(f'{member.mention} `{member}` (ID: {member.id})',allowed_mentions=discord.AllowedMentions.none())

        except:
            try:
                user = self.bot.get_user(id)

                return await ctx.send(f'{user.mention} `{user}` (ID: {user.id})',allowed_mentions=discord.AllowedMentions.none())

            except:
                try:
                    channel = self.bot.get_channel(id)

                    return await ctx.send(f'{channel.mention} (ID: {member.id})')

                except:

                    try:
                        role = ctx.guild.get_role(id)

                        return await ctx.send(f"{role.mention} (ID: {role.id})",allowed_mentions=discord.AllowedMentions.none())
                    
                    except:
                        try:
                            guild = self.bot.get_guild(id)

                            return await ctx.send(f"{guild.name} (ID: {guild.id})",allowed_mentions=discord.AllowedMentions.none())

                        except:
                            return await ctx.send(f"This id either is a message or I cannot convert it into anything.")


    @commands.command()
    @commands.bot_has_permissions(send_messages=True)
    async def uptime(self, ctx):

        await ctx.send(f'I have an uptime of: **{get_bot_uptime(self.bot, brief=True)}**')


    @commands.command()
    @commands.bot_has_permissions(send_messages=True, embed_links=True)
    async def emojis(self, ctx):

        menu = ViewMenuPages(source=Source(self.bot.emojis), clear_reactions_after=True)
        await menu.start(ctx)
















def setup(bot):
    bot.add_cog(info(bot))



















