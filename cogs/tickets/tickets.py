import discord
from discord.ext import commands

from bot import MetroBot
from utils.custom_context import MyContext

from .views import TicketConfigView

async def setup(bot: MetroBot):
    await bot.add_cog(tickets(bot))

class tickets(commands.Cog, description='Manage a ticketing system with channels.'):
    def __init__(self, bot: MetroBot):
        self.bot = bot

    @property
    def emoji(self) -> str:
        return '\U0001f39f'

    @commands.hybrid_group(name='tickets')
    async def tickets(self, ctx: MyContext):
        """Manage and create tickets."""

        await ctx.help()

    @tickets.command(name='config', aliases=['setup'])
    async def tickets_config(self, ctx: MyContext):
        """Configure ticketing settings."""
        
        query = 'SELECT channel FROM tickets WHERE guild_id = $1'
        returned: int = await self.bot.db.fetchval(query, ctx.guild.id)
        if returned:
            confirm = await ctx.confirm(
                f'It seems like you already have a ticket panel setup in <#{returned}>, '\
                'Do you want to reset all the data and tickets from that panel to create another one?'
            )
            if not confirm.value:
                return 

            query = 'DELETE FROM tickets WHERE guild_id = $1'
            await self.bot.db.execute(query, ctx.guild.id)

        view = TicketConfigView(ctx)
        await view.start()

    