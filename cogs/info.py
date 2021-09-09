import discord
from discord.enums import T
from discord.ext import commands

from typing import Optional
import unicodedata

from utils.useful import Embed
from discord.ext.commands.cooldowns import BucketType
import time
import json
from pathlib import Path



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
    async def set_prefix(self, ctx, prefix : Optional[str]):
        """
        Set the prefix for this guild.
        (Needs `manage_guild` permission to work)
        """

        if prefix is None:
            prefix = 'm.'


        data = await self.bot.db.fetch('SELECT prefix FROM prefixes WHERE "guild_id" = $1', ctx.guild.id)
        if len(data) == 0:
            print("Prefix is gone.")
            await self.bot.db.execute('INSERT into prefixes ("guild_id", prefix) VALUES ($1, $2)', ctx.guild.id, prefix)

        else:
            print("Prefix is updated.")
            await self.bot.db.execute('UPDATE prefixes SET prefix = $1 WHERE "guild_id" = $2', prefix, ctx.guild.id)
        
        await ctx.send('Set the prefix for **{}** to `{}`'.format(ctx.guild.name, prefix))

        
    @commands.command()
    @commands.max_concurrency(number=1, per=BucketType.user, wait=True)
    async def ping(self, ctx):

        start = time.perf_counter()
        m = await ctx.send('Pinging...')
        end = time.perf_counter()

        typing_ping = (end - start) * 1000

        start = time.perf_counter()
        
        end = time.perf_counter()

        database_ping = (end - start) * 1000

        
        await m.edit(content=f'Typing: `{round(typing_ping, 1)} ms`\nWebsocket: `{round(self.bot.latency*1000)} ms`\nDatabase: `unknown`')


    @commands.command()
    @commands.is_owner()    
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







def setup(bot):
    bot.add_cog(info(bot))



















