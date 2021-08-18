import discord
from discord.ext import commands

from typing import Optional
import unicodedata

from utils.useful import Embed


class info(commands.Cog, description="Information about members, guilds, or roles."):
    def __init__(self, bot):
        self.bot = bot

    async def say_permissions(self, ctx, member, channel):
        permissions = channel.permissions_for(member)
        e = discord.Embed(colour=member.colour)
        avatar = member.avatar.with_static_format('png')
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





def setup(bot):
    bot.add_cog(info(bot))



















