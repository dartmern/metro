from typing import Optional
import discord
from discord.ext import commands

import asyncpg
from bot import MyContext

from collections import defaultdict

from utils.converters import ChannelOrRoleOrMember, DiscordCommand

class configuration(commands.Cog, description=':gear: Configure the bot/server.'):
    def __init__(self, bot):
        self.bot = bot
        

        self.command_config = defaultdict(list)

    async def load_command_config(self):
        query = """
                SELECT entity_id, ARRAY_AGG(command) AS commands
                FROM command_config GROUP BY entity_id;
                """
        records = await self.bot.cxn.fetch(query)
        if records:
            [
                self.command_config[record["entity_id"]].extend(record["commands"])
                for record in records
            ]

    async def bot_check(self, ctx):
        if ctx.guild is None:
            return True  # Do not restrict in DMs.

        if ctx.author.id == ctx.bot.owner_id:
            return True  # Bot devs are immune.


        if str(ctx.command) in self.command_config[ctx.guild.id]:
            raise commands.BadArgument('This command is disabled in this guild.')
            return False  # Disabled for the whole server.

        if str(ctx.command) in self.command_config[ctx.channel.id]:
            raise commands.BadArgument('This command is disabled in this channel.')
            return False  # Disabled for the channel

        if str(ctx.command) in self.command_config[ctx.author.id]:
            raise commands.BadArgument('This command is disabled for you.')
            return False  # Disabled for the user

        if any(
            (
                str(ctx.command) in self.command_config[role_id]
                for role_id in ctx.author._roles
            )
        ):
            raise commands.BadArgument(f'This command is disabled for you.')
            return False  # Disabled for the role

        return True  # Ok just in case we get here...

    async def disable_command(self, ctx, entity, commands):
        query = """
                INSERT INTO command_config (server_id, entity_id, command)
                VALUES ($1, $2, $3);
                """
        failed = []
        success = []
        async with self.bot.db.acquire() as conn:
            async with conn.transaction():
                for command in commands:
                    try:
                        await self.bot.db.execute(
                            query, ctx.guild.id, entity.id, command
                        )
                    except asyncpg.exceptions.UniqueViolationError:
                        failed.append(
                            (
                                command,
                                f"Command is already disabled for entity `{entity}`",
                            )
                        )
                        continue
                    except Exception as e:
                        failed.append((command, e))
                        continue
                    else:
                        success.append(command)
                        self.command_config[entity.id].append(command)
        if success:
            await ctx.send(
                f"Disabled command{'' if len(success) == 1 else 's'} `{', '.join(success)}` for entity `{entity}`"
            )
        if failed:
            await ctx.send(
                f"Failed to disable the following commands: `{','.join(failed)}`"
            )

    
    async def enable_command(self, ctx, entity, commands):
        query = """
                DELETE FROM command_config
                WHERE server_id = $1
                AND entity_id = $2
                AND command = ANY($3::TEXT[]);
                """
        await self.bot.db.execute(query, ctx.guild.id, entity.id, commands)
        self.command_config[entity.id] = [
            x for x in self.command_config[entity.id] if x not in commands
        ]
        await ctx.send(
            f"Enabled commands `{', '.join(commands)}` for entity `{entity}`"
        )


    @commands.group(
        name='config',
        invoke_without_command=True,
        case_insensitive=True
    )
    async def config(self, ctx):
        """Handle the server or channel permission configuration for the bot."""

        await ctx.send_help('config')

    
    @config.group(
        name='disable',
        invoke_without_command=True,
        case_insensitive=True,
        usage='[entity] [commands...]'
    )
    @commands.has_permissions(manage_guild=True)
    async def config_disable(
        self, 
        ctx : MyContext, 
        entity : Optional[ChannelOrRoleOrMember] = None, 
        *commands : DiscordCommand):
        """Prevent specific commands from being run in channels, users, or roles.
        
        **Tip:** Use `~` in place of entity to disable a command for the entire guild.
        """

        if not commands:
            return await ctx.send_help('config disable')
        entity = entity or ctx.guild
        await ctx.trigger_typing()
        await self.disable_command(ctx, entity, [str(n.name) for n in commands])


    @config_disable.command(
        name='list'
    )
    @commands.has_permissions(manage_guild=True)
    async def config_disable_list(
        self,
        ctx : MyContext
    ):
        """Show disabled commands"""

        await ctx.trigger_typing()
        query = """
                SELECT entity_id,
                ARRAY_AGG(command) as commands
                FROM command_config
                WHERE server_id = $1
                GROUP BY entity_id;
                """
        records = await self.bot.db.fetch(query, ctx.guild.id)
        if not records:
            return await ctx.send("No commands are disabled.")

        guild_disabled_commands = []
    

        for record in records:
            
            guild = self.bot.get_guild(record["entity_id"])
            if not guild:
                pass
            else:
                guild_disabled_commands.extend(record["commands"])

        channel_keys = {}
        for record in records:
            try:
                channel = await commands.TextChannelConverter().convert(ctx, str(record["entity_id"]))
            except:
                continue
            channel_keys[channel] = record["commands"]

        role_keys = {}
        for record in records:
            try:
                role = await commands.RoleConverter().convert(ctx, str(record['entity_id']))
            except:
                continue
            role_keys[role] = record["commands"]

        member_keys = {}
        for record in records:
            try:
                member = await commands.MemberConverter().convert(ctx, str(record["entity_id"]))
            except:
                continue
            member_keys[member] = record["commands"]

        
        embed = discord.Embed(
            title='Disabled Commands',
            color=discord.Color.blurple()
        )
        if guild_disabled_commands:
            embed.add_field(
                name='Guild Disabled Commands:',
                value="\n".join(f"`{c}`" for c in guild_disabled_commands)
            )

        if bool(channel_keys) is True:
            finished_channels = []

            channel_key = list(channel_keys.keys())
            channel_value = list(channel_keys.values())

            
            for item in zip(channel_key, channel_value):
                
                new_item = list(item[1])

                items = ','.join(f'`{item}`' for item in new_item)
                finished_channels.append(f'{item[0].mention} : {items}')

            embed.add_field(
                name='Channel Disabled Commands:',
                value="\n".join(finished_channels),
                inline=False
            )

        if bool(role_keys) is True:
            finished_roles = []

            role_key = list(role_keys.keys())
            role_value = list(role_keys.values())

            
            for item in zip(role_key, role_value):
                
                new_item = list(item[1])

                items = ','.join(f'`{item}`' for item in new_item)
                finished_roles.append(f'{item[0].mention} : {items}')

            embed.add_field(
                name='Role Disabled Commands:',
                value="\n".join(finished_roles),
                inline=False
            )

        if bool(member_keys) is True:
            finished_members = []

            member_key = list(member_keys.keys())
            member_value = list(member_keys.values())
            print(member_key)
            print(member_value)
            
            for item in zip(member_key, member_value):
                
                new_item = list(item[1])

                items = ','.join(f'`{item}`' for item in new_item)
                finished_members.append(f'{item[0].mention} : {items}')

            print(finished_members)
            embed.add_field(
                name='Member Disabled Commands:',
                value="\n".join(finished_members),
                inline=False
            )
            
        await ctx.send(embed=embed)


        
    @config_disable.command(
        name='clear'
    )
    @commands.has_permissions(manage_guild=True)
    async def config_disable_clear(self, ctx : MyContext):
        """
        Clear all disabled commands.
        """

        confirm = await ctx.confirm(f'Are you sure you want to clear all your disabled commands?',timeout=30)

        if confirm is None:
            return await ctx.send('Timed out.')

        if confirm is False:
            return await ctx.send('Canceled.')

        await ctx.trigger_typing()
        query = "DELETE FROM command_config WHERE server_id = $1;"
        await self.bot.db.execute(query, ctx.guild.id)

        await ctx.send('Cleared the server\'s disabled command list.')






    @config.group(
        name='enable',
        invoke_without_command=True,
        case_insensitive=True
    )
    @commands.has_permissions(manage_guild=True)
    async def config_enable(
        self,
        ctx : MyContext,
        entity : Optional[ChannelOrRoleOrMember] = None,
        *commands : DiscordCommand
    ):
        """Let specific commands being runable in channels, users, or roles.
        
        **Tip:** Use `~` in place of entity to disable a command for the entire guild.
        """

        if not commands:
            return await ctx.send_help('config enable')

        await ctx.trigger_typing()
        entity = entity or ctx.guild
        await self.enable_command(ctx, entity, [str(c) for c in commands])


    @config_enable.command(
        name='all'
    )
    @commands.has_permissions(manage_guild=True)
    async def config_enable_all(self, ctx):
        """
        Clear all disabled commands.
        """

        await ctx.invoke(self.config_disable_clear)






        






def setup(bot):
    bot.add_cog(configuration(bot))