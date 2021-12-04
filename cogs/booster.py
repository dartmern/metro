import datetime
from typing import Optional
import discord
import bisect
from discord.ext import commands
from discord.member import M

from bot import MetroBot
from utils.custom_context import MyContext
from utils.useful import Embed

class boosts(commands.Cog, description='<:booster:916183319144710154> Get booster stats a members'):
    def __init__(self, bot : MetroBot):
        self.bot = bot
        self.boost_badges = {
            30 : "<:boost1:916198948404858941>",
            60 : "<:boost2:916198948438421554>",
            90 : "<:boost3:916198948480372786>",
            180 : "<:boost4:916198948035760129>",
            270 : "<:boost5:916198948069335091>",
            360 : "<:boost6:916198948333559849>",
            450 : "<:boost7:916198948396466236>",
            540 : "<:boost8:916198948228718613>",
            720 : "<:boost9:916198948383891466>",  
        }

    @commands.Cog.listener()
    async def on_message(self, message : discord.Message):
        
        if message.guild:
            if message.type in ['MessageType.premium_guild_subscription', 'MessageType.premium_guild_tier_1', 'MessageType.premium_guild_tier_2', 'MessageType.premium_guild_tier_3']:
                await self.bot.dispatch('boost', message)

    @commands.command()
    async def boosters(self, ctx : MyContext):
        """
        View all the wonderful boosters the current guild has.
        """

        _boosters = {}
        to_append = []

        for member in ctx.guild.members:
            if member.premium_since:
                _boosters[member] = member.premium_since.timestamp()
        sort = dict(sorted(_boosters.items(), key=lambda x: x[1]))

        for member in sort.keys(): 
            days = datetime.date.today() - datetime.datetime.utcfromtimestamp(sort[member]).date()
            
            p = bisect.bisect(list(self.boost_badges.keys()), days.days)
            emoji = self.boost_badges[(list(self.boost_badges)[p])]

            to_append.append(f"{emoji} {member} - <t:{round(sort[member])}:R>")
            
        if to_append:

            if len(to_append) < 7 and len(to_append) >= 2:
                lvl = '1'
            elif len(to_append) < 14 and len(to_append) >= 7:
                lvl = '2'
            elif len(to_append) >= 14:
                lvl = '3'

            embed = Embed()
            embed.title = f'<:boost_lvl:916489560807051284> Server Boost Level: {lvl}'
            embed.description = '\n'.join(to_append)
            embed.set_footer(text=f'Total Boosters: {len(to_append)}')
            await ctx.send(embed=embed)
        else:
            await ctx.send("This server has no boosters.")

    @commands.command(aliases=['boost_since'])
    async def boosting_since(self, ctx : MyContext, *, member : Optional[discord.Member] = None):
        """
        View when a member started boosting the server.
        Not passing in a member will default to yourself.
        """
        member = member or ctx.author
        if not member.premium_since:
            return await ctx.send(f"`{member}` is not boosting.")

        days = datetime.date.today() - datetime.datetime.utcfromtimestamp(round(member.premium_since.timestamp())).date()
            
        p = bisect.bisect(list(self.boost_badges.keys()), days.days)
        emoji = self.boost_badges[(list(self.boost_badges)[p])]

        return await ctx.send(
            f"{emoji} `{member}` started boosting this server <t:{round(member.premium_since.timestamp())}:R>"
        )

    @commands.command(name='boost_emojis', aliases=['boosting_emojis'])
    async def boost_emojis(self, ctx : MyContext):
        """
        View the boosting emojis and what they mean.
        """

        emojis = []
        for x in self.boost_badges.keys():
            emojis.append(f"{x} days \u2800 \u2800 \u2800 \u2800 {self.boost_badges[x]}")

        embed = Embed()
        embed.add_field(name='Boosting Emojis', value='\n'.join(emojis))
        embed.set_footer(text='Feel free to steal as I just cropped the discord badges.')
        await ctx.send(embed=embed)

def setup(bot : MetroBot):
    bot.add_cog(boosts(bot))