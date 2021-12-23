import discord
from discord.ext import commands
from discord.ui.button import B

from bot import MetroBot
from utils.checks import can_execute_action
from utils.custom_context import MyContext
from utils.converters import RoleConverter
from utils.useful import Cooldown, Embed

# This cog has parts of code from phencogs
# https://github.com/phenom4n4n/phen-cogs/blob/master/roleutils/roles.py

def setup(bot : MetroBot):
    bot.add_cog(roleutils(MetroBot))

class roleutils(commands.Cog, description='<:role:923611835066908712> Manage anything role related.'):
    def __init__(self, bot : MetroBot) -> None:
        self.bot = bot

    async def show_roleinfo(self, role: discord.Role):
        if role.guild.chunked is False:
            await role.guild.chunk()

        desc = [
            role.mention,
            f"Member: {len(role.members)} | Position: {role.position}",
            f"Colour: {role.colour}",
            f"Hoisted: {role.hoist}",
            f"Mentionable: {role.mentionable}"
        ]
        if role.managed:
            desc.append(f"Managed: {role.managed}")
        
        embed = Embed()
        embed.colour = role.colour
        embed.title = role.name
        embed.description = "\n".join(desc)
        embed.timestamp = role.created_at
        embed.set_footer(text=f"ID: {role.id}")

        return embed
        
    @commands.group(invoke_without_command=True)
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_guild_permissions(manage_roles=True)
    async def role(self, ctx: MyContext, member : discord.Member, *, role : RoleConverter):
        """
        Base command for modifying roles.
        
        Invoking this command without subcommands will add or remove the given role from the member, 
        depending on whether they already had it.
        """
        if not can_execute_action(ctx, ctx.author, member):
            return await ctx.send('You are not high enough in role hierarchy to edit roles from this member.')

        if role in member.roles:
            await ctx.invoke(self.role_remove, member=member, role=role)
            return
        elif role not in member.roles:
            await ctx.invoke(self.role_add, member=member, role=role)
            return
        else:
            await ctx.help() 

    @role.error
    async def role_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            return await ctx.send_help("role")


    @role.command(name='add')
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_guild_permissions(manage_roles=True)
    async def role_add(self, ctx : MyContext, member : discord.Member, *, role : RoleConverter):
        """Add a role to a member."""

        if role in member.roles:
            return await ctx.send(f"**{member}** already has that role. Try removing it instead.")

        if not can_execute_action(ctx, ctx.author, member):
            return await ctx.send('You are not high enough in role hierarchy to give roles to this member.')

        if role.position > ctx.guild.me.top_role.position:
            to_send = ""
            to_send += (
                f"\🔴 I am unable to add this role due to discord hierarchy rules."
                f"\nMy top role's position ({ctx.guild.me.top_role.mention}) is lower than the configured mute role."
                f"\n\nMy top role position: {ctx.guild.me.top_role.position} • `@{role.name}` position: {role.position}"
                f"\n\nPlease move my top role higher to make this command work!"
            )
            return await ctx.send(to_send)

        try:
            await member.add_roles(role, reason=f'Role command invoked by: {ctx.author} (ID: {ctx.author.id})')
        except discord.HTTPException as e:
            return await ctx.send(f"Had trouble adding this role: {e}")
        await ctx.send(f"Added **{role.name}** to **{member}**")

        
    @role.command(name='remove')
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_guild_permissions(manage_roles=True)
    async def role_remove(self, ctx : MyContext, member : discord.Member, *, role : RoleConverter):
        """Remove a role from a member."""

        if not role in member.roles:
            return await ctx.send(f"**{member}** doesn't have that role. Try adding it instead.")

        if not can_execute_action(ctx, ctx.author, member):
            return await ctx.send('You are not high enough in role hierarchy to remove roles to this member.')

        if role.position > ctx.guild.me.top_role.position:
            to_send = ""
            to_send += (
                f"\🔴 I am unable to remove this role due to discord hierarchy rules."
                f"\nMy top role's position ({ctx.guild.me.top_role.mention}) is lower than the configured mute role."
                f"\n\nMy top role position: {ctx.guild.me.top_role.position} • `@{role.name}` position: {role.position}"
                f"\n\nPlease move my top role higher to make this command work!"
            )
            return await ctx.send(to_send)

        try:
            await member.remove_roles(role, reason=f'Role command invoked by: {ctx.author} (ID: {ctx.author.id})')
        except discord.HTTPException as e:
            return await ctx.send(f"Had trouble removing this role: {e}")
        await ctx.send(f"Removed **{role.name}** from **{member}**")

    @role.command(name='addmulti')
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_guild_permissions(manage_roles=True)
    @commands.check(Cooldown(1, 6, 1, 4, commands.BucketType.guild))
    async def role_addmulti(self, ctx: MyContext, role: RoleConverter, *members: discord.Member):
        """Add a role to multiple members."""

        if role.position > ctx.guild.me.top_role.position:
            to_send = ""
            to_send += (
                f"\🔴 I am unable to add this role due to discord hierarchy rules."
                f"\nMy top role's position ({ctx.guild.me.top_role.mention}) is lower than the configured mute role."
                f"\n\nMy top role position: {ctx.guild.me.top_role.position} • `@{role.name}` position: {role.position}"
                f"\n\nPlease move my top role higher to make this command work!"
            )
            return await ctx.send(to_send)

        success, hierarchy, already_has = [], [], []
        for member in members:
            if not can_execute_action(ctx, ctx.author, member):
                hierarchy.append(str(member))
                continue

            if role not in member.roles:
                await member.add_roles(role, reason=f'Add-multi role command invoked by: {ctx.author} (ID: {ctx.author.id})')
                success.append(str(member))
            else:
                already_has.append(str(member))

        to_send = []
        if success:
            to_send.append(f"Added **{role.name}** to {', '.join(success)}")
        if already_has:
            to_send.append(f"{', '.join(already_has)} already had **{role.name}**")
        if hierarchy:
            to_send.append(f"You are not high enough in role hierarchy to add roles to: {', '.join(hierarchy)}")
        if to_send:
            await ctx.send("\n".join(to_send))


    @role.command(name='removemulti')
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_guild_permissions(manage_roles=True)
    @commands.check(Cooldown(1, 6, 1, 4, commands.BucketType.guild))
    async def role_removemulti(self, ctx: MyContext, role : RoleConverter, *members: discord.Member):
        """Remove a role from multiple members."""

        if role.position > ctx.guild.me.top_role.position:
            to_send = ""
            to_send += (
                f"\🔴 I am unable to remove this role due to discord hierarchy rules."
                f"\nMy top role's position ({ctx.guild.me.top_role.mention}) is lower than the configured mute role."
                f"\n\nMy top role position: {ctx.guild.me.top_role.position} • `@{role.name}` position: {role.position}"
                f"\n\nPlease move my top role higher to make this command work!"
            )
            return await ctx.send(to_send)

        success, hierarchy, already_has = [], [], []
        for member in members:
            if not can_execute_action(ctx, ctx.author, member):
                hierarchy.append(str(member))
                continue

            if role in member.roles:
                await member.remove_roles(role, reason=f'Remove-multi role command invoked by: {ctx.author} (ID: {ctx.author.id})')
                success.append(str(member))
            else:
                already_has.append(str(member))

        to_send = []
        if success:
            to_send.append(f"Removed **{role.name}** from {', '.join(success)}")
        if already_has:
            to_send.append(f"{', '.join(already_has)} doesn't have **{role.name}**")
        if hierarchy:
            to_send.append(f"You are not high enough in role hierarchy to remove roles from: {', '.join(hierarchy)}")
        if to_send:
            await ctx.send("\n".join(to_send))


    @role.command(name='all')
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_guild_permissions(manage_roles=True)
    @commands.check(Cooldown(1, 120, 1, 90, commands.BucketType.guild))
    async def role_all(self, ctx: MyContext, *, role: RoleConverter):
        """Add a role to all members of the guild."""

        if role.position > ctx.guild.me.top_role.position:
            to_send = ""
            to_send += (
                f"\🔴 I am unable to add roles due to discord hierarchy rules."
                f"\nMy top role's position ({ctx.guild.me.top_role.mention}) is lower than the configured mute role."
                f"\n\nMy top role position: {ctx.guild.me.top_role.position} • `@{role.name}` position: {role.position}"
                f"\n\nPlease move my top role higher to make this command work!"
            )
            raise commands.BadArgument(to_send)

        confirm = await ctx.confirm(f"Are you sure you want to add **{role.name}** to **{ctx.guild.member_count}** members.")
        if confirm is False:
            raise commands.BadArgument("Canceled.")
        if confirm is None:
            raise commands.BadArgument("Timed out.")

        if ctx.guild.chunked is False:
            await ctx.guild.chunk()

        await ctx.send(f"Beginning to add **{role.name}** to **{len(ctx.guild.members)}** members.")
        
        success, failed, already_has = 0, 0, 0

        async with ctx.typing():
            for member in ctx.guild.members:
                if not can_execute_action(ctx, ctx.author, member):
                    failed += 1
                    continue

                if role in member.roles:
                    already_has += 1
                    continue

                try:
                    await member.add_roles(role, reason=f'Role-all invoked by: {ctx.author} (ID: {ctx.author.id})')
                    success += 1
                except discord.HTTPException:
                    failed += 1

        to_send = ""
        if success:
            to_send += f"Successfully added **{role.name}** to {success}/{len(ctx.guild.members)} members."
        if already_has:
            to_send += f"{already_has} members already had **{role.name}**"
        if failed:
            to_send += f"Failed to add **{role.name}** to {failed} members due to role hierarchy or permission errors."

        await ctx.send(to_send)

    @role.command(name='rall', aliases=['removeall'])
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_guild_permissions(manage_roles=True)
    @commands.check(Cooldown(1, 120, 1, 90, commands.BucketType.guild))
    async def role_rall(self, ctx: MyContext, *, role: RoleConverter):
        """Remove a role from all members of the guild."""

        if role.position > ctx.guild.me.top_role.position:
            to_send = ""
            to_send += (
                f"\🔴 I am unable to remove roles due to discord hierarchy rules."
                f"\nMy top role's position ({ctx.guild.me.top_role.mention}) is lower than the configured mute role."
                f"\n\nMy top role position: {ctx.guild.me.top_role.position} • `@{role.name}` position: {role.position}"
                f"\n\nPlease move my top role higher to make this command work!"
            )
            raise commands.BadArgument(to_send)

        confirm = await ctx.confirm(f"Are you sure you want to remove **{role.name}** from **{ctx.guild.member_count}** members.")
        if confirm is False:
            raise commands.BadArgument("Canceled.")
        if confirm is None:
            raise commands.BadArgument("Timed out.")

        if ctx.guild.chunked is False:
            await ctx.guild.chunk()

        await ctx.send(f"Beginning to remove **{role.name}** from **{len(ctx.guild.members)}** members.")
        
        success, failed, already_has = 0, 0, 0

        async with ctx.typing():
            for member in ctx.guild.members:
                if not can_execute_action(ctx, ctx.author, member):
                    failed += 1
                    continue

                if not role in member.roles:
                    already_has += 1
                    continue

                try:
                    await member.remove_roles(role, reason=f'Role-removeall invoked by: {ctx.author} (ID: {ctx.author.id})')
                    success += 1
                except discord.HTTPException:
                    failed += 1

        to_send = ""
        if success:
            to_send += f"Successfully removed **{role.name}** from {success}/{len(ctx.guild.members)} members."
        if already_has:
            to_send += f"{already_has} members didn't even have **{role.name}**"
        if failed:
            to_send += f"Failed to remove **{role.name}** from {failed} members due to role hierarchy or permission errors."

        await ctx.send(to_send)

    @role.command(name='info')
    @commands.bot_has_guild_permissions(embed_links=True)
    async def role_info(self, ctx: MyContext, *, role: RoleConverter):
        """Show a role's information."""
        await ctx.send(embed=await self.show_roleinfo(role))


