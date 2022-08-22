import discord
from discord.ext import commands

from mee6_py_api import API
import mee6_py_api

from utils.constants import MEE6_ID
from utils.embeds import create_embed
from utils.errors import ConverterError

class MEE6_Converter(commands.Converter):
    
    async def convert(self, ctx, argument: str):
        mee6 = ctx.guild.get_member(MEE6_ID)
        if not mee6 in ctx.guild.members:
            raise ConverterError('I cannot do MEE6 requirements without MEE6 in the server.')

        try:
            level = int(argument)
        except ValueError:
            raise ConverterError('MEE6 requirement must be a integer. Example: `mee6:10`')

        mee6api = API(ctx.guild.id)
        try:
            await mee6api.levels.get_leaderboard_page(0)
        except mee6_py_api.exceptions.UnauthorizedError:

            embed = create_embed(
                'MEE6 leaderboard must be public to use MEE6 requirements.\n\n'\
                f'`1)` Go to your [MEE6 dashboard](https://mee6.xyz/dashboard) and click on the **Leaderboard** tab on the left. \n'\
                f'`2)` Enable **Make my server\'s leaderboard public** \n'\
                f'`3)` Make sure you save your changes by clicking **Save** in the bottom right.'
                )
            embed.set_footer(text='Manage Server permissions are required to make this change.')
            
            raise ConverterError(embed=embed)

        return level

        


        

        

            




