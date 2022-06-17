import ast
from ctypes import util
import json
import random
import discord
from discord.ext import commands, tasks
from discord import app_commands

from bot import MetroBot
from cogs.utility import Timer, utility
from utils.custom_context import MyContext
from utils.embeds import create_embed
from utils.remind_utils import FutureTime, human_timedelta
from utils.constants import EMOTES, TESTING_GUILD
from .views import ConfirmationEmojisView, GiveawayEntryView, UnenterGiveawayView

from .helpers.get_giveaway import get_giveaway
from .helpers.get_entry import get_entry
from .helpers.insert_entry import insert_entry
from .helpers.insert_giveaway import insert_giveaway
from .helpers.get_entries import get_entires

async def setup(bot: MetroBot):
    await bot.add_cog(giveaways2(bot))

class giveaways2(commands.Cog, description='The giveaways rewrite including buttons.'):
    def __init__(self, bot: MetroBot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):

        if interaction.message:
            message_id = interaction.message.id

            data = await get_giveaway(
                self.bot, interaction.guild_id, interaction.channel_id, message_id)
            
            if data:
                entry = await get_entry(self.bot, message_id, interaction.user.id)
                if not entry:

                    await insert_entry(self.bot, message_id, interaction.user.id)
                    
                    embed = create_embed(f"{EMOTES['check']} Your entry has been approved for this giveaway.", color=discord.Color.green())
                    await interaction.response.send_message(embed=embed, ephemeral=True)

                    embed_dict = ast.literal_eval(data[0])
                    embed = discord.Embed.from_dict(embed_dict)

                    footer = interaction.message.embeds[0].footer

                    x = footer.text.split("|")[1].rstrip("entries")
                    final = footer.text.split("|")[0] + "| " + str(int(x) + 1) + " entires"

                    embed.set_footer(text=final)
                    await interaction.message.edit(embed=embed)

                else:
                    embed = create_embed(f"{EMOTES['cross']} You have already joined this giveaway.", color=discord.Color.red())

                    view = UnenterGiveawayView(self.bot, interaction.message.id, interaction.message)
                    return await interaction.response.send_message(embed=embed, ephemeral=True, view=view)

    @commands.Cog.listener()
    async def on_new_giveaway_timer_complete(self, timer: Timer):
        """Fires when a giveaway ends."""
        guild_id, channel_id, message_id = timer.args

        data = await get_giveaway(
            self.bot, 
            guild_id,
            channel_id,
            message_id
        )
        if not data:
            return # rip?

        guild = self.bot.get_guild(guild_id)
        if not guild:
            return 

        channel = guild.get_channel(channel_id)
        if not channel:
            return 

        message = await channel.fetch_message(message_id)
        if not message:
            return 

        entires = await get_entires(self.bot, message_id)
        amount_of_winners = data[1]
        raw_embed = data[0]

        winners = random.sample(entires, amount_of_winners)
        winners_fmt = ", ".join([f"<@{record['author_id']}>" for record in winners])

        raw = ast.literal_eval(raw_embed)
        embed = discord.Embed.from_dict(raw)
        embed.color = discord.Color.red()
        old = embed.description 
        old = old.replace('Click the button below to enter!', f'Winners: {winners_fmt}') # bad way of doing this but i'm testing
        old = old.replace('Ends', 'Ended')

        embed.description = old
        embed.set_footer(text=message.embeds[0].footer.text)

        
        button = discord.ui.Button()
        button.disabled = True
        button.style = discord.ButtonStyle.red
        button.label = 'Giveaway Ended'

        view = discord.ui.View()
        view.add_item(button)
        
        await message.edit(embed=embed, view=view)

        new_embed = create_embed(
            f'{winners_fmt} has won the giveaway for {embed.author.name}!',
            color=discord.Color.yellow()
        )
        await message.reply(embed=new_embed)


        
        

        
        

    @commands.hybrid_command(name='gstart')
    @app_commands.guilds(TESTING_GUILD)
    @app_commands.describe(duration='Duration of this giveaway.')
    @app_commands.describe(winners='Amount of winners.')
    @app_commands.describe(prize='Prize you are giving away.')
    async def gstart(
        self, 
        ctx: MyContext, 
        duration: FutureTime, 
        winners: int , 
        *, 
        prize: str):
        """Testing giveaway command."""

        utility_cog: utility = self.bot.get_cog('utility')
        if not utility_cog:
            return await ctx.send('This feature is currently unavailable.')

        embed = discord.Embed(title='Is this information correct?', color=discord.Colour.yellow())
        embed.description = f"""
                            **Prize:** {prize}
                            **Winners:** {winners}
                            **Duration:** {human_timedelta(duration.dt, brief=True)}
                            """
        
        view = ConfirmationEmojisView(
            timeout=60, author_id=ctx.author.id, ctx=ctx)
        view.message = await ctx.send(embed=embed, view=view)
        await view.wait()

        if view.value is False:
            return await view.message.edit(content='Confirmation canceled.', embeds=[], view=None)
        if view.value is None:
            return await view.message.edit(content='Confirmation timed out.', embeds=[], view=None)
        else:
            await view.message.edit(content=f'Creating giveaway...', embeds=[], view=None)

            giveaway = discord.Embed(
                color=discord.Color.green()
            )
            giveaway.set_author(name=prize)
            giveaway.description = f'Click the button below to enter! \n'\
                    f'Ends {discord.utils.format_dt(duration.dt, "R")} ({discord.utils.format_dt(duration.dt, "f")}) \n'\
                    f'Hosted by: {ctx.author.mention}'           
            giveaway.set_footer(text=f'{winners} winner{"s" if winners > 1 else ""} | 0 entries')

            try:
                await view.message.delete()
            except discord.HTTPException:
                pass

            message = await ctx.channel.send(embed=giveaway, view=GiveawayEntryView(ctx, view.message))

            await insert_giveaway(
                self.bot, 
                ctx.guild.id, 
                ctx.channel.id, 
                message.id, 
                duration.dt.replace(tzinfo=None),
                giveaway.to_dict(),
                winners
                )

            try:
                await utility_cog.create_timer(
                    duration.dt,
                    'new_giveaway',
                    ctx.guild.id,
                    ctx.channel.id,
                    message.id
                )
            except Exception:
                pass # for now idk what to do at the moment

            








    @property
    def emoji(self) -> str:
        return '\U0001f973'


