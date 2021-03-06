import ast
from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands

from bot import MetroBot
from cogs.giveaway_rewrite.modals.giveaway_create import GiveawayCreate
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
from .core.reroll_giveaway import reroll_giveaway
from .converters.winners import Winners
from .converters.requirements import Requirements 

from .settings.show_settings import show_settings   
from .settings.add_setting import add_setting

class giveaways(commands.Cog, description='The giveaways rewrite including buttons.'):
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
                    requirements = ast.literal_eval(data[5])

                    role_req = [ele for ele in requirements['role'] if ele not in map(lambda x: x.id, interaction.user.roles)]
                    blacklist_req = [ele for ele in requirements['blacklist'] if ele in map(lambda x: x.id, interaction.user.roles)]
                    bypass_req = [ele for ele in requirements['bypass'] if ele in map(lambda x: x.id, interaction.user.roles)]
                    
                    if blacklist_req:

                        roles = [f"<@&{role}>" for role in blacklist_req]
                        if len(roles) > 1:
                            roles[-1] = f"and {roles[-1]}"
                        
                        embed = create_embed(
                            f'{EMOTES["cross"]} You cannot join this giveaway because you the following blacklisted roles: \n{", ".join(roles)}',
                            color=discord.Color.red()
                        )
                        
                        return await interaction.response.send_message(embed=embed, ephemeral=True)

                    if role_req:
                        if bypass_req:
                            pass
                        else:
                            roles = [f"<@&{role}>" for role in role_req]
                            if len(roles) > 1:
                                roles[-1] = f"and {roles[-1]}"

                            embed = create_embed(
                                f'{EMOTES["cross"]} You are missing the following roles to join this giveaway:\n {", ".join(roles)}',
                                color=discord.Color.red())

                            if requirements['bypass']:
                                roles = [f"<@&{role}>" for role in requirements['bypass']]
                                if len(roles) > 1:
                                    roles[-1] = f"and {roles[-1]}"

                                embed.description += f'\n Bypass Roles: {", ".join(roles)}'
                                
                            return await interaction.response.send_message(embed=embed, ephemeral=True)
                    

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

        if data[4] is True:
            return # already ended

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

    @commands.hybrid_group(name='giveaway-settings', fallback='info', aliases=['gset'])
    @commands.has_guild_permissions(manage_guild=True)
    async def giveaway_settings(
        self, 
        ctx: MyContext):
        """Manage giveaway settings."""

        data = await show_settings(self.bot, ctx.guild.id)
        if not data:
            # this will be changed but for now it's like this
            return await ctx.send('This server has default giveaway settings or has not changed anything yet.')

        manager = f'<@&{data[0]}>' if data[0] else None
        ping_role = f'<@&{data[1]}>' if data[1] else None

        embed = discord.Embed(color=ctx.color)
        embed.set_author(name='Giveaway Settings')
        embed.description = f'Giveaway Manager: {manager} \n'\
                            f'Ping Role: {ping_role}'

        await ctx.send(embed=embed)

    @giveaway_settings.command(name='manager')
    @commands.has_guild_permissions(manage_guild=True)
    @app_commands.describe(role='Role you want to set as manager.')
    async def giveaway_settings_manager(
        self,
        ctx: MyContext, *, role: Optional[discord.Role] = None):
        """Set a giveaway manager role. Leave blank to reset the role."""

        await add_setting(self.bot, 'manager', role.id if role else None, ctx.guild.id)
        await ctx.send(EMOTES['check'], hide=True)
        
    @giveaway_settings.command(name='ping')
    @app_commands.describe(role='Role you want to ping for giveaways.')
    async def giveaway_settings_ping(
        self,
        ctx: MyContext, *, role: Optional[discord.Role] = None):
        """Set the giveaway ping role. Leave blank to reset the role."""

        await add_setting(self.bot, 'ping', role.id if role else None, ctx.guild.id)
        await ctx.send(EMOTES['check'], hide=True)
    
    @commands.hybrid_group(name='giveaway', fallback='help', aliases=['g'])
    @commands.has_guild_permissions(manage_guild=True)
    @app_commands.default_permissions(manage_guild=True)
    async def giveaway(
        self, 
        ctx: MyContext
        ):
        """Base command for creating giveaways.
        
        See `[p]giveaway-settings` for giveaway customization."""
        await ctx.help()

    @giveaway.command(name='end')
    @app_commands.describe(message_id='The message id of the giveaway.')
    @app_commands.default_permissions(manage_guild=True)
    @commands.has_guild_permissions(manage_guild=True)
    async def giveaway_end(
        self, 
        ctx: MyContext,
        *,
        message_id: MessageID):
        """End a giveaway."""
    
        data = await get_giveaway(self.bot, message_id)
        if not data:
            return await ctx.send("That doesn't seem like a giveaway id.", hide=True)

        channel = self.bot.get_channel(data[3]) # data[3] is the channel id
        if not channel:
            return await ctx.send("It seems liske the giveaway's channel was deleted.", hide=True)

        try:
            message = await channel.fetch_message(message_id)
        except discord.HTTPException:
            return await ctx.send("It seems like the giveaway's message was deleted.", hide=True)

        await end_giveaway(self.bot, message_id, data, message)
        await ctx.send(EMOTES['check'], hide=True)

    @giveaway.command(name='reroll')
    @commands.has_guild_permissions(manage_guild=True)
    @app_commands.describe(message_id='The message id of the giveaway.')
    @app_commands.describe(winners='The amount of winners to reroll. Defaults to 1.')
    async def giveaway_reroll(
        self,
        ctx: MyContext,
        message_id: MessageID,
        winners: int = 1):
        """Reroll a giveaway."""

        data = await get_giveaway(self.bot, message_id)
        if not data:
            return await ctx.send("That doesn't seem like a giveaway id.", hide=True)

        if data[4] is False:
            return await ctx.send("This giveaway has not ended yet therefore you cannot reroll it.", hide=True)
        
        channel = self.bot.get_channel(data[3]) # data[3] is the channel id
        if not channel:
            return await ctx.send("It seems liske the giveaway's channel was deleted.", hide=True)

        try:
            message = await channel.fetch_message(message_id)
        except discord.HTTPException:
            return await ctx.send("It seems like the giveaway's message was deleted.", hide=True)

        await reroll_giveaway(self.bot, message_id, data, message)
        await ctx.send(EMOTES['check'], hide=True)
        

    @giveaway.command(name='start')
    @commands.has_guild_permissions(manage_guild=True)
    @app_commands.describe(duration='Duration of this giveaway.')
    @app_commands.describe(winners='Amount of winners.')
    @app_commands.describe(requirements='Requirements to join this giveaway.')
    @app_commands.describe(prize='Prize you are giving away.')
    async def giveaway_start(
        self, 
        ctx: MyContext, 
        duration: FutureTime, 
        winners: Winners,
        requirements: Requirements,
        *, 
        prize: str):
        """Start a giveaway in the current channel."""
        
        message = await ctx.send('Creating giveaway...')

        utility_cog: utility = self.bot.get_cog('utility')
        if not utility_cog:
            return await message.edit(content='This feature is currently unavailable.')
        else:
            requirement = ""
            if requirements['role']:
                roles = [f"<@&{role}>" for role in requirements['role']]
                if len(roles) > 1:
                    roles[-1] = f"and {roles[-1]}"
                requirement += f'Required Role{"s" if len(requirements["role"]) > 1 else ""}: {", ".join(roles)} \n'

            if requirements['bypass']:
                roles = [f"<@&{role}>" for role in requirements['bypass']]
                if len(roles) > 1:
                    roles[-1] = f"and {roles[-1]}"
                requirement += f'Bypass Role{"s" if len(requirements["bypass"]) > 1 else ""}: {", ".join(roles)} \n'
            
            if requirements['blacklist']:
                roles = [f"<@&{role}>" for role in requirements['blacklist']]
                if len(roles) > 1:
                    roles[-1] = f"and {roles[-1]}"
                requirement += f'Blacklisted Role{"s" if len(requirements["blacklist"]) > 1 else ""}: {", ".join(roles)} \n'

            giveaway = discord.Embed(
                color=discord.Color.green()
            )
            giveaway.set_author(name=prize)
            giveaway.description = f'Click the button below to enter! \n'\
                    f'Ends {discord.utils.format_dt(duration.dt, "R")} ({discord.utils.format_dt(duration.dt, "f")}) \n'\
                    f'{requirement}'\
                    f'Hosted by: {ctx.author.mention}'  
            giveaway.set_footer(text=f'{winners} winner{"s" if winners > 1 else ""} | 0 entries')

            try:
                await message.delete()
            except discord.HTTPException:
                pass

            message = await ctx.channel.send(embed=giveaway, view=GiveawayEntryView(ctx, message))
            await insert_giveaway(
                self.bot, 
                ctx.guild.id, 
                ctx.channel.id, 
                message.id, 
                duration.dt.replace(tzinfo=None),
                giveaway.to_dict(),
                winners,
                requirements
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
    
    @giveaway.command(name='create', with_app_command=True)
    @commands.has_guild_permissions(manage_guild=True)
    async def giveaway_create(self, ctx: MyContext):
        """Interactively create a giveaway."""

        if ctx.interaction:
            await ctx.interaction.response.send_modal(GiveawayCreate(interaction=ctx.interaction))
    

    @property
    def emoji(self) -> str:
        return '\U0001f973'


