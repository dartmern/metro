from typing import Optional, Union
import discord
from discord.ext import commands

from bot import MetroBot
from utils.custom_context import MyContext
from utils.converters import RoleConverter

async def setup(bot: MetroBot):
    await bot.add_cog(reactionroles(bot))

class reactionroles(commands.Cog, description='Manage the reaction role system.'):
    def __init__(self, bot: MetroBot):
        self.bot = bot

        self.reactionroles = {}

        bot.loop.create_task(self.load_reactionroles())

    @property
    def emoji(self) -> str:
        return self.bot.emotes['role']

    async def load_reactionroles(self):
        await self.bot.wait_until_ready()

        query = """
                SELECT (emoji, message_id, role_id)
                FROM reactionroles
                """
        records = await self.bot.db.fetch(query)
        if records:
            for record in records:
                try:
                    self.reactionroles[record['row'][0]][record['row'][1]] = record['row'][2]
                except KeyError:
                    self.reactionroles[record['row'][0]] = {record['row'][1]: record['row'][2]}

    @commands.Cog.listener('on_raw_reaction_add')
    async def add_reaction_role_handler(self, payload: discord.RawReactionActionEvent):
        if not payload.guild_id:
            return 

        data = self.reactionroles.get(str(payload.emoji))
        if not data:
            return # Not in cache, we aren't gonna try

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return # Somehow this is possible when we check the guild_id but why not be safe

        member = await self.bot.get_or_fetch_member(guild, payload.user_id)
        if not member:
            return # can't find member for some odd reason?

        role = data.get(payload.message_id)
        if not role:
            return # Somehow role isn't found :(

        try:
            await member.add_roles(discord.Object(role), reason='reactionroleadd')
        except discord.HTTPException:
            pass # no perms, can't really do anything...
            
    @commands.Cog.listener('on_raw_reaction_remove') #honestly an inverse of on_raw_reaction_add
    async def remove_reaction_role_handler(self, payload: discord.RawReactionActionEvent):
        if not payload.guild_id:
            return 

        data = self.reactionroles.get(str(payload.emoji))
        if not data:
            return # Not in cache, we aren't gonna try

        guild = self.bot.get_guild(payload.guild_id)
        if not guild:
            return # Somehow this is possible when we check the guild_id but why not be safe

        member = await self.bot.get_or_fetch_member(guild, payload.user_id)
        if not member:
            return # can't find member for some odd reason?

        role = data.get(payload.message_id)
        if not role:
            return # Somehow role isn't found :(

        try:
            await member.remove_roles(discord.Object(role), reason='reactionroleadd')
        except discord.HTTPException:
            pass # no perms, can't really do anything...

    @commands.group(name='reactionrole', aliases=['reactrole', 'rr'], invoke_without_command=True, case_insensitive=True)
    @commands.has_guild_permissions(manage_guild=True)
    async def reactionrole(self, ctx: MyContext):
        """Base command for managing reaction roles."""
        await ctx.help()

    @reactionrole.command(name='add', aliases=['create', '+'])
    @commands.has_guild_permissions(manage_guild=True)
    async def reactionrole_add(
        self, ctx: MyContext, message: Optional[discord.Message], 
        emoji: Union[discord.PartialEmoji, str], *, role: RoleConverter):
        """
        Add a reaction role to a message.
        
        Use this to add one reaction role to one message.
        Consider using `rr make` if you are confused/new to reactionroles.
        """
        if not message:
            if ctx.message.reference:
                message = getattr(ctx.message.reference, 'resolved')
            else:
                message = None
        if not message:
            raise commands.BadArgument("Please supply a message or reply to a message.")

        if len(message.reactions) > 20:
            raise commands.BadArgument('This message has reached the maximum number of reactions (20)')

        query = """
                SELECT * FROM reactionroles
                WHERE emoji = $1
                AND message_id = $2
                """
        data = await self.bot.db.fetchval(query, str(emoji), message.id)
        if data:
            raise commands.BadArgument(f"{self.bot.emotes['cross']} This is emoji already has a role binded to it...")

        query = """
                INSERT INTO reactionroles
                (server_id, channel_id, message_id, role_id, emoji)
                VALUES ($1, $2, $3, $4, $5)
                """
        await self.bot.db.execute(query, ctx.guild.id, message.channel.id, message.id, role.id, str(emoji))
        
        try:
            self.reactionroles[str(emoji)][message.id] = role.id
        except KeyError:
            self.reactionroles[str(emoji)] = {message.id: role.id}

        await message.add_reaction(emoji)
        await ctx.send(f"{self.bot.emotes['check']} Added \"{emoji}\" to hand out **{role.name}**", allowed_mentions=discord.AllowedMentions.none())
        
    @reactionrole.command(name='remove', aliases=['-'])
    @commands.has_guild_permissions(manage_guild=True)
    async def reactionrole_remove(
        self, ctx: MyContext, message: Optional[discord.Message],
        emoji: Union[discord.PartialEmoji, str], *, role: RoleConverter):
        """
        Remove a reaction role from a message.
        """
        if not message:
            if ctx.message.reference:
                message = getattr(ctx.message.reference, 'resolved')
            else:
                message = None
        if not message:
            raise commands.BadArgument("Please supply a message or reply to a message.")

        status = await self.bot.db.execute("DELETE FROM reactionroles WHERE (message_id, role_id, emoji) = ($1, $2, $3)", message.id, role.id, str(emoji))
        if status == "DELETE 0":
            raise commands.BadArgument("Could not find that reaction role in my database.")

        self.reactionroles[str(emoji)].pop(message.id)

        await ctx.send(f"{self.bot.emotes['check']} Removed \"{emoji}\" to hand out **{role.name}**")

    @reactionrole.command(name='list')
    @commands.has_guild_permissions(manage_guild=True)
    async def reactionrole_list(self, ctx: MyContext):
        """
        Display all the reaction roles for this guild.
        """
        data =  await self.bot.db.fetch(
            "SELECT (channel_id, message_id, role_id, emoji) FROM reactionroles WHERE server_id = $1",ctx.guild.id)
        if not data:
            raise commands.BadArgument(f"{self.bot.emotes['cross']} This guild does not have any reaction roles.")

        embed = discord.Embed(color=ctx.color)
        embed.description = "Run `%srr show <id>` for more information on a reaction role." % ctx.clean_prefix
        for record in data:
            channel = self.bot.get_channel(record['row'][0])
            message = channel.get_partial_message(record['row'][1])

            embed.add_field(
                name=record['row'][1], 
                value=f"Emoji: {record['row'][3]} Role: <@&{record['row'][2]}> \n"\
                    f"[Jump url]({message.jump_url})",
                inline=True)
        await ctx.send(embed=embed)

        


