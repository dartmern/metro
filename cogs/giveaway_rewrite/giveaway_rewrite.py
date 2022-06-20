import ast

import discord
from discord.ext import commands
from discord import app_commands

from bot import MetroBot
from cogs.utility import Timer, utility
from utils.custom_context import MyContext
from utils.embeds import create_embed
from utils.remind_utils import FutureTime, human_timedelta
from utils.constants import EMOTES, TESTING_GUILD
from utils.useful import MessageID
from .views import ConfirmationEmojisView, GiveawayEntryView, UnenterGiveawayView

from .core.get_giveaway import get_giveaway
from .core.get_entry import get_entry
from .core.insert_entry import insert_entry
from .core.insert_giveaway import insert_giveaway
from .core.end_giveaway import end_giveaway
from .converters.winners import Winners
from .converters.requirements import Requirements 
from .settings.show_settings import show_settings   

class giveaways2(commands.Cog, description='The giveaways rewrite including buttons.'):
    def __init__(self, bot: MetroBot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):

        if interaction.message:
            message_id = interaction.message.id

            data = await get_giveaway(
                self.bot, message_id)
            
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
                    final = footer.text.split("|")[0] + "| " + str(int(x) + 1) + " entries"

                    embed.set_footer(text=final)
                    await interaction.message.edit(embed=embed)

                else:
                    embed = create_embed(f"{EMOTES['cross']} You have already joined this giveaway.", color=discord.Color.red())

                    view = UnenterGiveawayView(self.bot, interaction.message.id, interaction.message, data[2])
                    return await interaction.response.send_message(embed=embed, ephemeral=True, view=view)

    @commands.Cog.listener()
    async def on_new_giveaway_timer_complete(self, timer: Timer):
        """Fires when a giveaway ends."""
        guild_id, channel_id, message_id = timer.args

        data = await get_giveaway(self.bot, message_id)
        if not data:
            return # rip?

        guild = self.bot.get_guild(guild_id)
        if not guild:
            return 

        channel = guild.get_channel(channel_id)
        if not channel:
            return

        try:
            message = await channel.fetch_message(message_id)
        except discord.HTTPException:
            return 

        await end_giveaway(self.bot, message_id, data, message)
        

    @commands.hybrid_command(name='gend')
    @app_commands.guilds(TESTING_GUILD)
    @app_commands.describe(message_id='The message id of the giveaway.')
    @app_commands.default_permissions(manage_guild=True)
    @commands.has_guild_permissions(manage_guild=True)
    async def gend(
        self, 
        ctx: MyContext,
        *,
        message_id: MessageID):
        """End a giveaway."""
        

        data = await get_giveaway(self.bot, message_id)
        if not data:
            return await ctx.send("That doesn't seem like a giveaway id.")

        channel = self.bot.get_channel(data[3]) # data[3] is the channel id
        if not channel:
            return await ctx.send("It seems liske the giveaway's channel was deleted.")

        try:
            message = await channel.fetch_message(message_id)
        except discord.HTTPException:
            return await ctx.send("It seems like the giveaway's message was deleted.")

        await end_giveaway(self.bot, message_id, data, message)
        await ctx.send(EMOTES['check'], hide=True)

    @commands.hybrid_group(name='giveaway-settings', fallback='info')
    @app_commands.guilds(TESTING_GUILD)
    @app_commands.default_permissions(manage_guild=True)
    @commands.has_guild_permissions(manage_guild=True)
    async def giveaway_settings(
        self, 
        ctx: MyContext):
        """Manage giveaway settings."""

        data = await show_settings(self.bot, ctx.guild.id)
        if not data:
            return await ctx.send('This server has default giveaway settings or has not changed anything yet.')

        embed = discord.Embed()
        embed.set_author(name='Giveaway Settings')
        embed.description = f'Giveaway Manager: <@&{data[0]}>'

        await ctx.send(embed=embed)

    @commands.hybrid_command(name='gstart')
    @app_commands.default_permissions(manage_guild=True)
    @commands.has_guild_permissions(manage_guild=True)
    @app_commands.guilds(TESTING_GUILD)
    @app_commands.describe(duration='Duration of this giveaway.')
    @app_commands.describe(winners='Amount of winners.')
    @app_commands.describe(requirements='Requirements to join this giveaway.')
    @app_commands.describe(prize='Prize you are giving away.')
    async def gstart(
        self, 
        ctx: MyContext, 
        duration: FutureTime, 
        winners: Winners,
        requirements: Requirements,
        *, 
        prize: str):
        """Start a giveaway in the current channel."""

        start = discord.utils.utcnow()

        utility_cog: utility = self.bot.get_cog('utility')
        if not utility_cog:
            return await ctx.send('This feature is currently unavailable.')

        embed = discord.Embed(title='Is this information correct?', color=discord.Colour.yellow())
        embed.description = f"**Prize:** {prize} \n"\
                            f"**Winners:** {winners} \n"\
                            f"**Duration:** {human_timedelta(duration.dt)} \n"

        if not all(x is False for x in requirements.values()):
            role_fmt = ', '.join(r.mention for r in requirements['role'])
            bypass_fmt = ', '.join(r.mention for r in requirements['bypass'])
            blacklist_fmt = ', '.join(r.mention for r in requirements['blacklist'])
            value = f"Role{'s' if len(requirements['role']) > 1 else ''}: {role_fmt if role_fmt != '' else 'No requirements.'}\n"\
                    f"Bypass: {bypass_fmt if bypass_fmt != '' else 'No bypass role'} \n"\
                    f"Blacklist: {blacklist_fmt if blacklist_fmt != '' else 'No blacklist role'}" 
            embed.add_field(name='Requirements', value=value)
                            
        
        view = ConfirmationEmojisView(
            timeout=60, author_id=ctx.author.id, ctx=ctx)
        view.message = await ctx.send(embed=embed, view=view)
        await view.wait()

        difference = discord.utils.utcnow() - start 
        duration.dt = duration.dt + difference

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


