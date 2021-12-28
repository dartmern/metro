from typing import Optional
import discord
from discord.ext import commands

from bot import MetroBot
from utils.checks import can_execute_action
from utils.custom_context import MyContext
from utils.converters import RoleConverter
from utils.parsing import RoleParser
from utils.remind_utils import FutureTime, human_timedelta
from utils.useful import Cooldown, Embed



# This cog has parts of code from phencogs
# https://github.com/phenom4n4n/phen-cogs/blob/master/roleutils/roles.py

def setup(bot : MetroBot):
    bot.add_cog(roleutils(MetroBot))

class roleutils(commands.Cog, description=' Manage anything role related.'):
    def __init__(self, bot : MetroBot) -> None:
        self.bot = bot

    @property
    def emoji(self) -> str:
        return '<:role:923611835066908712>'

    async def cleanup_code(self, content):
        """Automatically removes code blocks from the code."""
        # remove ```py\n```
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])

        # remove `foo`
        return content.strip('` \n')

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
                f"\nMy top role's position ({ctx.guild.me.top_role.mention}) is lower than `@{role.name}`"
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
                f"\nMy top role's position ({ctx.guild.me.top_role.mention}) is lower than `@{role.name}`"
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
                f"\nMy top role's position ({ctx.guild.me.top_role.mention}) is lower than `@{role.name}`"
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
                f"\nMy top role's position ({ctx.guild.me.top_role.mention}) is lower than `@{role.name}`"
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
                f"\nMy top role's position ({ctx.guild.me.top_role.mention}) is lower than `@{role.name}`"
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
                f"\nMy top role's position ({ctx.guild.me.top_role.mention}) is lower than `@{role.name}``"
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

    @role.command(name='bots')
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_guild_permissions(manage_roles=True)
    @commands.check(Cooldown(1, 120, 1, 90, commands.BucketType.guild))
    async def role_bots(self, ctx: MyContext, *, role: RoleConverter):
        """Add a role to all bots in the guild."""

        if role.position > ctx.guild.me.top_role.position:
            to_send = ""
            to_send += (
                f"\🔴 I am unable to add roles due to discord hierarchy rules."
                f"\nMy top role's position ({ctx.guild.me.top_role.mention}) is lower than `@{role.name}`"
                f"\n\nMy top role position: {ctx.guild.me.top_role.position} • `@{role.name}` position: {role.position}"
                f"\n\nPlease move my top role higher to make this command work!"
            )
            raise commands.BadArgument(to_send)

        confirm = await ctx.confirm(f"Are you sure you want to add **{role.name}** to **{len(ctx.guild.bots)}** bots.")
        if confirm is False:
            raise commands.BadArgument("Canceled.")
        if confirm is None:
            raise commands.BadArgument("Timed out.")

        if ctx.guild.chunked is False:
            await ctx.guild.chunk()

        await ctx.send(f"Beginning to add **{role.name}** to **{len(ctx.guild.bots)}** bots.")
        
        success, failed, already_has = 0, 0, 0

        async with ctx.typing():
            for bot in ctx.guild.bots:
                if not can_execute_action(ctx, ctx.author, bot):
                    failed += 1
                    continue

                if role in bot.roles:
                    already_has += 1
                    continue

                try:
                    await bot.add_roles(role, reason=f'Role-all-bots invoked by: {ctx.author} (ID: {ctx.author.id})')
                    success += 1
                except discord.HTTPException:
                    failed += 1

        to_send = ""
        if success:
            to_send += f"Successfully added **{role.name}** to {success}/{len(ctx.guild.bots)} bots."
        if already_has:
            to_send += f"{already_has} bots already had **{role.name}**"
        if failed:
            to_send += f"Failed to add **{role.name}** to {failed} bots due to role hierarchy or permission errors."

        await ctx.send(to_send)

    @role.command(name='rbots')
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_guild_permissions(manage_roles=True)
    @commands.check(Cooldown(1, 120, 1, 90, commands.BucketType.guild))
    async def role_rbots(self, ctx: MyContext, *, role: RoleConverter):
        """Remove a role from all bots in the guild."""

        if role.position > ctx.guild.me.top_role.position:
            to_send = ""
            to_send += (
                f"\🔴 I am unable to remove roles due to discord hierarchy rules."
                f"\nMy top role's position ({ctx.guild.me.top_role.mention}) is lower than `@{role.name}``"
                f"\n\nMy top role position: {ctx.guild.me.top_role.position} • `@{role.name}` position: {role.position}"
                f"\n\nPlease move my top role higher to make this command work!"
            )
            raise commands.BadArgument(to_send)

        confirm = await ctx.confirm(f"Are you sure you want to remove **{role.name}** from **{len(ctx.guild.bots)}** bots.")
        if confirm is False:
            raise commands.BadArgument("Canceled.")
        if confirm is None:
            raise commands.BadArgument("Timed out.")

        if ctx.guild.chunked is False:
            await ctx.guild.chunk()

        await ctx.send(f"Beginning to remove **{role.name}** from **{len(ctx.guild.bots)}** bots.")
        
        success, failed, already_has = 0, 0, 0

        async with ctx.typing():
            for bot in ctx.guild.bots:
                if not can_execute_action(ctx, ctx.author, bot):
                    failed += 1
                    continue

                if not role in bot.roles:
                    already_has += 1
                    continue

                try:
                    await bot.remove_roles(role, reason=f'Role-removeall-bots invoked by: {ctx.author} (ID: {ctx.author.id})')
                    success += 1
                except discord.HTTPException:
                    failed += 1

        to_send = ""
        if success:
            to_send += f"Successfully removed **{role.name}** from {success}/{len(ctx.guild.bots)} bots."
        if already_has:
            to_send += f"{already_has} bots didn't even have **{role.name}**"
        if failed:
            to_send += f"Failed to remove **{role.name}** to {failed} bots due to role hierarchy or permission errors."

        await ctx.send(to_send)

    @role.command(name='humans')
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_guild_permissions(manage_roles=True)
    @commands.check(Cooldown(1, 120, 1, 90, commands.BucketType.guild))
    async def role_humans(self, ctx: MyContext, *, role: RoleConverter):
        """Add a role to all humans in the guild."""

        if role.position > ctx.guild.me.top_role.position:
            to_send = ""
            to_send += (
                f"\🔴 I am unable to add roles due to discord hierarchy rules."
                f"\nMy top role's position ({ctx.guild.me.top_role.mention}) is lower than `@{role.name}`"
                f"\n\nMy top role position: {ctx.guild.me.top_role.position} • `@{role.name}` position: {role.position}"
                f"\n\nPlease move my top role higher to make this command work!"
            )
            raise commands.BadArgument(to_send)

        confirm = await ctx.confirm(f"Are you sure you want to add **{role.name}** to **{len(ctx.guild.humans)}** humans.")
        if confirm is False:
            raise commands.BadArgument("Canceled.")
        if confirm is None:
            raise commands.BadArgument("Timed out.")

        if ctx.guild.chunked is False:
            await ctx.guild.chunk()

        await ctx.send(f"Beginning to add **{role.name}** to **{len(ctx.guild.humans)}** humans.")
        
        success, failed, already_has = 0, 0, 0

        async with ctx.typing():
            for human in ctx.guild.humans:
                if not can_execute_action(ctx, ctx.author, human):
                    failed += 1
                    continue

                if role in human.roles:
                    already_has += 1
                    continue

                try:
                    await human.add_roles(role, reason=f'Role-all-humans invoked by: {ctx.author} (ID: {ctx.author.id})')
                    success += 1
                except discord.HTTPException:
                    failed += 1

        to_send = ""
        if success:
            to_send += f"Successfully added **{role.name}** to {success}/{len(ctx.guild.humans)} humans."
        if already_has:
            to_send += f"{already_has} humans already had **{role.name}**"
        if failed:
            to_send += f"Failed to add **{role.name}** to {failed} humans due to role hierarchy or permission errors."

        await ctx.send(to_send)

    @role.command(name='rhumans')
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_guild_permissions(manage_roles=True)
    @commands.check(Cooldown(1, 120, 1, 90, commands.BucketType.guild))
    async def role_rhumans(self, ctx: MyContext, *, role: RoleConverter):
        """Remove a role from all humans in the guild."""

        if role.position > ctx.guild.me.top_role.position:
            to_send = ""
            to_send += (
                f"\🔴 I am unable to remove roles due to discord hierarchy rules."
                f"\nMy top role's position ({ctx.guild.me.top_role.mention}) is lower than `@{role.name}`"
                f"\n\nMy top role position: {ctx.guild.me.top_role.position} • `@{role.name}` position: {role.position}"
                f"\n\nPlease move my top role higher to make this command work!"
            )
            raise commands.BadArgument(to_send)

        confirm = await ctx.confirm(f"Are you sure you want to remove **{role.name}** from **{len(ctx.guild.humans)}** humans.")
        if confirm is False:
            raise commands.BadArgument("Canceled.")
        if confirm is None:
            raise commands.BadArgument("Timed out.")

        if ctx.guild.chunked is False:
            await ctx.guild.chunk()

        await ctx.send(f"Beginning to remove **{role.name}** from **{len(ctx.guild.humans)}** humans.")
        
        success, failed, already_has = 0, 0, 0

        async with ctx.typing():
            for human in ctx.guild.humans:
                if not can_execute_action(ctx, ctx.author, human):
                    failed += 1
                    continue

                if not role in human.roles:
                    already_has += 1
                    continue

                try:
                    await human.remove_roles(role, reason=f'Role-removeall-humans invoked by: {ctx.author} (ID: {ctx.author.id})')
                    success += 1
                except discord.HTTPException:
                    failed += 1

        to_send = ""
        if success:
            to_send += f"Successfully removed **{role.name}** from {success}/{len(ctx.guild.humans)} humans."
        if already_has:
            to_send += f"{already_has} humans didn't even have **{role.name}**"
        if failed:
            to_send += f"Failed to remove **{role.name}** to {failed} humans due to role hierarchy or permission errors."

        await ctx.send(to_send)

    @role.command(
        name='list',
        extras= {
            "examples" : "[p]role list \n [p]role list Name: {role.name} - ID: {role.id} \n [p]role list Role created at: {role.created_at_timestamp}"
        }
    )
    @commands.bot_has_guild_permissions(embed_links=True)
    async def role_list(self, ctx: MyContext, *, tagscript : str = None) -> Embed:
        """
        List all the roles the guild has.
        
        The `tagscript` argument is the way you want to format the roles.
        [Any attribute](https://enhanced-dpy.readthedocs.io/en/latest/api.html#discord.Role) a role has, you can add there.
        """

        if not tagscript:
            e = Embed()
            e.colour = discord.Colour.yellow()
            e.description = "\n".join([f'{x.mention} - {x.id}' for x in ctx.guild.roles])
            e.set_footer(text=f'{len(ctx.guild.roles)} roles.')
            return await ctx.send(embed=e)
        else:
            tagscript = await self.cleanup_code(tagscript)
            to_append = []
            for role in ctx.guild.roles:
                r = RoleParser.parse(tagscript, {"role" : role})
                to_append.append(r)

            e = Embed()
            e.colour = discord.Colour.yellow()
            e.description = '\n'.join(to_append)

            await ctx.send(embed=e)
            

    @role.command(name='info')
    @commands.bot_has_guild_permissions(embed_links=True)
    async def role_info(self, ctx: MyContext, *, role: RoleConverter):
        """Show a role's information."""
        await ctx.send(embed=await self.show_roleinfo(role))


    @role.command(name='color')
    @commands.bot_has_guild_permissions(manage_roles=True)
    @commands.has_guild_permissions(manage_roles=True)
    async def role_color(self, ctx: MyContext, role: RoleConverter, *, color: discord.Color):
        """Change a role's color."""

        if role.position > ctx.guild.me.top_role.position:
            to_send = ""
            to_send += (
                f"\🔴 I am unable to edit this role due to discord hierarchy rules."
                f"\nMy top role's position ({ctx.guild.me.top_role.mention}) is lower than `@{role.name}`"
                f"\n\nMy top role position: {ctx.guild.me.top_role.position} • `@{role.name}` position: {role.position}"
                f"\n\nPlease move my top role higher to make this command work!"
            )
            raise commands.BadArgument(to_send)

        await role.edit(color=color)
        await ctx.send(f"Changed **{role.name}**'s color to **{color}**", embed=await self.show_roleinfo(role))
    
    @role.command(name='hoist')
    @commands.bot_has_guild_permissions(manage_roles=True)
    @commands.has_guild_permissions(manage_roles=True)
    async def role_hoist(self, ctx: MyContext, role: RoleConverter, hoisted: bool = None):
        """Toggle a role's hoist status."""

        if role.position > ctx.guild.me.top_role.position:
            to_send = ""
            to_send += (
                f"\🔴 I am unable to edit this role due to discord hierarchy rules."
                f"\nMy top role's position ({ctx.guild.me.top_role.mention}) is lower than `@{role.name}`"
                f"\n\nMy top role position: {ctx.guild.me.top_role.position} • `@{role.name}` position: {role.position}"
                f"\n\nPlease move my top role higher to make this command work!"
            )
            raise commands.BadArgument(to_send)

        hoisted = hoisted if hoisted is not None else not role.hoist
        print(hoisted)
        await role.edit(hoist=hoisted)
        term = "now longer" if hoisted is False else "now"
        await ctx.send(f"**{role.name}** is {term} hoisted.")

    @role.command(name='rename', aliases=['name'])
    @commands.bot_has_guild_permissions(manage_roles=True)
    @commands.has_guild_permissions(manage_roles=True)
    async def role_rename(self, ctx: MyContext, role: RoleConverter, *, name: str):
        """Rename a role's name."""

        if role.position > ctx.guild.me.top_role.position:
            to_send = ""
            to_send += (
                f"\🔴 I am unable to edit this role due to discord hierarchy rules."
                f"\nMy top role's position ({ctx.guild.me.top_role.mention}) is lower than `@{role.name}`"
                f"\n\nMy top role position: {ctx.guild.me.top_role.position} • `@{role.name}` position: {role.position}"
                f"\n\nPlease move my top role higher to make this command work!"
            )
            raise commands.BadArgument(to_send)

        oldname = role.name
        await role.edit(name=name)
        await ctx.send(f"Renammed from **{oldname}** to **{name}**.", embed=await self.show_roleinfo(role))

    @role.command(name='create')
    @commands.bot_has_guild_permissions(manage_roles=True)
    @commands.has_guild_permissions(manage_roles=True)
    async def role_create(
        self, 
        ctx: MyContext, 
        color: Optional[discord.Color] = discord.Color.default(),
        hoist: Optional[bool] = False,
        *,
        name: str
    ):
        """Create a new role."""

        if len(ctx.guild.roles) >= 250:
            raise commands.BadArgument("This server has reached the maximum role limit: [250/250]")

        role = await ctx.guild.create_role(name=name, colour=color, hoist=hoist, reason=f'Role create command invoked by: {ctx.author} (ID: {ctx.author.id})')
        await ctx.send(f"**{role.name}** created.", embed=await self.show_roleinfo(role))

    @role.command(name='in')
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_guild_permissions(manage_roles=True)
    @commands.check(Cooldown(1, 120, 1, 90, commands.BucketType.guild))
    async def role_in(self, ctx: MyContext, base_role: RoleConverter, *, target_role: RoleConverter):
        """Add a role to members of another role."""

        if target_role.position > ctx.guild.me.top_role.position:
            to_send = ""
            to_send += (
                f"\🔴 I am unable to add roles due to discord hierarchy rules."
                f"\nMy top role's position ({ctx.guild.me.top_role.mention}) is lower than `@{target_role.name}`"
                f"\n\nMy top role position: {ctx.guild.me.top_role.position} • `@{target_role.name}` position: {target_role.position}"
                f"\n\nPlease move my top role higher to make this command work!"
            )
            raise commands.BadArgument(to_send)

        confirm = await ctx.confirm(f"Are you sure you want to add **{target_role.name}** to **{len(base_role.members)}** members.")
        if confirm is False:
            raise commands.BadArgument("Canceled.")
        if confirm is None:
            raise commands.BadArgument("Timed out.")

        if ctx.guild.chunked is False:
            await ctx.guild.chunk()

        await ctx.send(f"Beginning to add **{target_role.name}** to **{len(base_role.members)}** members.")
        
        success, failed, already_has = 0, 0, 0

        async with ctx.typing():
            for human in base_role.members:
                if not can_execute_action(ctx, ctx.author, human):
                    failed += 1
                    continue

                if target_role in human.roles:
                    already_has += 1
                    continue

                try:
                    await human.add_roles(target_role, reason=f'Role-in invoked by: {ctx.author} (ID: {ctx.author.id})')
                    success += 1
                except discord.HTTPException:
                    failed += 1

        to_send = ""
        if success:
            to_send += f"Successfully added **{target_role.name}** to {success}/{len(base_role.members)} members."
        if already_has:
            to_send += f"{already_has} members already had **{target_role.name}**"
        if failed:
            to_send += f"Failed to add **{target_role.name}** to {failed} members due to role hierarchy or permission errors."

        await ctx.send(to_send)


    @role.command(name='rin')
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_guild_permissions(manage_roles=True)
    @commands.check(Cooldown(1, 120, 1, 90, commands.BucketType.guild))
    async def role_rin(self, ctx: MyContext, base_role: RoleConverter, *, target_role: RoleConverter):
        """Remove a role from members of another role."""

        if target_role.position > ctx.guild.me.top_role.position:
            to_send = ""
            to_send += (
                f"\🔴 I am unable to remove roles due to discord hierarchy rules."
                f"\nMy top role's position ({ctx.guild.me.top_role.mention}) is lower than `@{target_role.name}`"
                f"\n\nMy top role position: {ctx.guild.me.top_role.position} • `@{target_role.name}` position: {target_role.position}"
                f"\n\nPlease move my top role higher to make this command work!"
            )
            raise commands.BadArgument(to_send)

        confirm = await ctx.confirm(f"Are you sure you want to remove **{target_role.name}** from **{len(base_role.members)}** members.")
        if confirm is False:
            raise commands.BadArgument("Canceled.")
        if confirm is None:
            raise commands.BadArgument("Timed out.")

        if ctx.guild.chunked is False:
            await ctx.guild.chunk()

        await ctx.send(f"Beginning to remove **{target_role.name}** from **{len(base_role.members)}** members.")
        
        success, failed, already_has = 0, 0, 0

        async with ctx.typing():
            for human in base_role.members:
                if not can_execute_action(ctx, ctx.author, human):
                    failed += 1
                    continue

                if not target_role in human.roles:
                    already_has += 1
                    continue

                try:
                    await human.remove_roles(target_role, reason=f'Role-rin invoked by: {ctx.author} (ID: {ctx.author.id})')
                    success += 1
                except discord.HTTPException:
                    failed += 1

        to_send = ""
        if success:
            to_send += f"Successfully removed **{target_role.name}** from {success}/{len(base_role.members)} members."
        if already_has:
            to_send += f"{already_has} members didn't even have **{target_role.name}**"
        if failed:
            to_send += f"Failed to remove **{target_role.name}** from {failed} members due to role hierarchy or permission errors."

        await ctx.send(to_send)

    @commands.command(name='temprole', usage='<member> <duration> <role>')
    @commands.check(Cooldown(2, 10, 2, 8, commands.BucketType.member))
    @commands.has_guild_permissions(manage_roles=True)
    @commands.bot_has_guild_permissions(manage_roles=True)
    async def temprole(
        self, 
        ctx: MyContext, 
        member: discord.Member, 
        duration: FutureTime,
        *,
        role: RoleConverter
    ):
        """Adds a role to a member and removes it after the specified duration"""

        if role in member.roles:
            return await ctx.send("This member already has that role. \nIf you want to extend the temprole duration remove the role first.")

        if role.position > ctx.guild.me.top_role.position:
            to_send = ""
            to_send += (
                f"\🔴 I am unable to remove roles due to discord hierarchy rules."
                f"\nMy top role's position ({ctx.guild.me.top_role.mention}) is lower than `@{role.name}`"
                f"\n\nMy top role position: {ctx.guild.me.top_role.position} • `@{role.name}` position: {role.position}"
                f"\n\nPlease move my top role higher to make this command work!"
            )
            raise commands.BadArgument(to_send)

        if not can_execute_action(ctx, ctx.author, member):
            return await ctx.send('You are not high enough in role hierarchy to give roles to this member.')

        reminder_cog = ctx.bot.get_cog('utility')
        if reminder_cog is None:
            return await ctx.send('This function is not available at this time. Try again later.')

        try:
            timer = await reminder_cog.create_timer(
                duration.dt,
                "temprole",
                ctx.guild.id,
                ctx.author.id,
                role.id,
                member.id,
                connection=ctx.bot.db,
                created_at=ctx.message.created_at
            )
        except Exception as e:
            return await ctx.send(str(e))

        await member.add_roles(role, reason=f'Temprole command invoked by: {ctx.author} (ID: {ctx.author.id})')

        embed = Embed()
        embed.colour = discord.Colour.blue()
        embed.description = "__**Temporary role added**__"\
            f"\n{member.mention} was granted the {role.mention} role for {human_timedelta(duration.dt, accuracy=50)}"
        await ctx.send(embed=embed)