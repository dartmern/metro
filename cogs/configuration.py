import discord
from discord.ext import commands

import asyncpg
from collections import defaultdict
from typing import Optional

from bot import MetroBot
from utils.checks import check_dev

from utils.converters import ChannelOrRoleOrMember, DiscordCommand
from utils.useful import Embed
from utils.custom_context import MyContext
from utils.decos import is_dev

def mod_check():
    def predicate(ctx: MyContext):
        modroles = ctx.bot.modroles.get(ctx.guild.id)
        if modroles and ctx.author.id in modroles:
            return True
        if ctx.channel.permissions_for(ctx.author).manage_guild:
            return True
        else:
            return False
    return commands.check(predicate)

class configuration(commands.Cog, description='Configure the bot/server.'):
    def __init__(self, bot : MetroBot):
        self.bot = bot

        bot.loop.create_task(self.load_command_config())
        bot.loop.create_task(self.load_plonks())
        
        self.ignored = defaultdict(list)
        self.command_config = defaultdict(list)

    @property
    def emoji(self) -> str:
        return '⚙️'

    async def load_plonks(self):
        await self.bot.wait_until_ready()
        query = """
                SELECT server_id, ARRAY_AGG(entity_id) AS entities
                FROM plonks GROUP BY server_id;
                """
        records = await self.bot.db.fetch(query)
        if records:
            [
                self.ignored[record["server_id"]].extend(record["entities"])
                for record in records
            ]   

    async def load_command_config(self):
        await self.bot.wait_until_ready()
        query = """
                SELECT entity_id, ARRAY_AGG(command) AS commands
                FROM command_config GROUP BY entity_id;
                """
        records = await self.bot.db.fetch(query)
        if records:
            [
                self.command_config[record["entity_id"]].extend(record["commands"])
                for record in records
            ]

    async def ignore_entities(self, ctx : MyContext, entities):
        failed = []
        success = []
        query = """
                INSERT INTO plonks (server_id, entity_id)
                VALUES ($1, $2)
                """

        async with self.bot.db.acquire() as conn:
            async with conn.transaction():
                for entity in entities:
                    try:
                        await self.bot.db.execute(query, ctx.guild.id, entity.id)
                    except asyncpg.exceptions.UniqueViolationError:
                        failed.append((str(entity), "Entity is already being ignored"))
                    except Exception as e:
                        failed.append(str(entity), e)
                        continue
                    else:
                        success.append(str(entity))
                        self.ignored[ctx.guild.id].append(entity.id)


        if success:
            await ctx.send(
                f"Ignored entit{'y' if len(success) == 1 else 'ies'} `{', '.join(success)}`"
            )
        if failed:
            await ctx.send(
                f'\n'.join(failed)
            )

    async def bot_check_once(self, ctx):

        # Reasons for bypassing
        if ctx.guild is None:
            return True  # Do not restrict in DMs.

        if check_dev(ctx.bot, ctx.author):
            return True

        if isinstance(ctx.author, discord.Member):
            if ctx.author.guild_permissions.manage_guild:
                return True  # Manage guild is immune.

        # Now check channels, roles, and users.
        if ctx.channel.id in self.ignored[ctx.guild.id]:
            return False  # Channel is ignored.

        if ctx.author.id in self.ignored[ctx.guild.id]:
            return False  # User is ignored.

        if any(
            (
                role_id in self.ignored[ctx.guild.id]
                for role_id in [r.id for r in ctx.author.roles]
            )
        ):
            return False  # Role is ignored.

        return True  # Ok just in case we get here...

    async def bot_check(self, ctx):
        if ctx.guild is None:
            return True  # Do not restrict in DMs.

        if check_dev(ctx.bot, ctx.author):
            return True  # Bot devs are immune.

        if isinstance(ctx.author, discord.Member):
            if ctx.author.guild_permissions.manage_guild:
                return True  # Manage guild is immune.


        if str(ctx.command) in self.command_config[ctx.guild.id]:
            return False  # Disabled for the whole server.

        if str(ctx.command) in self.command_config[ctx.channel.id]:
            return False  # Disabled for the channel

        if str(ctx.command) in self.command_config[ctx.author.id]:
            return False  # Disabled for the user

        if any(
            (
                str(ctx.command) in self.command_config[role_id]
                for role_id in ctx.author._roles
            )
        ):
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
    @commands.has_permissions(manage_guild=True)
    async def config(self, ctx):
        """Handle the server or channel permission configuration for the bot."""

        await ctx.send_help('config')

    
    @config.group(
        name='disable',
        invoke_without_command=True,
        case_insensitive=True,
        usage='[entity] [commands...]',
        extras={'examples' : '[p]config disable #general help\n[p]config disable @muted help about info\n[p]config disable ~ info'}
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
        await ctx.typing()
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

        await ctx.typing()
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

        confirm = await ctx.confirm(f'Are you sure you want to clear all your disabled commands?',timeout=30, delete_after=False)

        if not confirm.value:
            await confirm.message.edit(content='Canceled/Timed out.', view=None)
            return

        await ctx.typing()
        query = "DELETE FROM command_config WHERE server_id = $1;"
        await self.bot.db.execute(query, ctx.guild.id)
        self.command_config[ctx.guild.id].clear()
        await ctx.send('Cleared the server\'s disabled command list.')


    @config.group(
        name='enable',
        invoke_without_command=True,
        case_insensitive=True,
        extras={"examples" : "[p]config enable #general help\n[p]config enable @muted help about info\n[p]config enable ~ info"}
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

        await ctx.typing()
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


    @config.group(
        name='ignore',
        invoke_without_command=True,
        case_insensitive=True,
        usage = '[entities...]',
        extras = {"examples" : "[p]config ignore #general\n[p]config ignore #support @dartmern @muted\n[p]config ignore ~", "perms" : {"manage_guild" : True}}
    )
    @commands.has_permissions(manage_guild=True)
    async def config_ignore(self, ctx : MyContext, *entities : ChannelOrRoleOrMember):
        """Ignore all commands in an entity."""
        
        if not entities:
            return await ctx.send_help('config ignore')

        await ctx.typing()
        await self.ignore_entities(ctx, entities)

    
    @config_ignore.command(
        name='list'
    )
    @commands.has_permissions(manage_guild=True)
    async def config_ignore_list(self, ctx : MyContext):
        """Show all ignored entities."""

        await ctx.typing()
        query = """
                SELECT entity_id
                FROM plonks
                WHERE server_id = $1;"""
        records = await self.bot.db.fetch(query, ctx.guild.id)

        if not records:
            return await ctx.send(f'No entities are being ignored.')

        ignored_channel = []
        ignored_member = []
        ignored_role = []
        for record in records:
            if int(record["entity_id"]) == ctx.guild.id:
                return await ctx.send('The entire guild has been ignored.')

            try:
                entity = await ChannelOrRoleOrMember().convert(ctx, str(record["entity_id"]))
            except:
                continue

            else:
                if isinstance(entity, discord.Role):
                    ignored_role.append(entity.mention)
                elif isinstance(entity, discord.TextChannel):
                    ignored_channel.append(entity.mention)
                elif isinstance(entity, discord.Member):
                    ignored_member.append(entity.mention)
                else:
                    pass

                    
        embed = Embed()

        if ignored_channel:
            embed.add_field(
                name='Ignored Channels',
                value=', '.join(ignored_channel),
                inline=False
            )
        if ignored_member:
            embed.add_field(
                name='Ignored Members',
                value=', '.join(ignored_role),
                inline=False
            )
        if ignored_role:
            embed.add_field(
                name='Ignored Roles',
                value=', '.join(ignored_role),
                inline=False
            )

        return await ctx.send(embed=embed)

    @config_ignore.command(
        name='clear'
    )
    @commands.has_permissions(manage_guild=True)
    async def config_ignore_clear(self, ctx : MyContext):
        """Clear the ignored list."""

        await ctx.typing()

        confirm = await ctx.confirm('Are you sure you want to clear your ignored list?',timeout=30, delete_after=False)

        if not confirm.value:
            await confirm.message.edit(content='Canceled/Timed out.', view=None)
            return

        query = """
                DELETE FROM plonks WHERE server_id = $1;
                """

        await self.bot.db.execute(query, ctx.guild.id)
        self.ignored[ctx.guild.id].clear()
        await ctx.send(f'Cleared the server\'s ignored list.')


    @config.group(
        name='unignore',
        extras = {"examples" : "[p]config unignore #general\n[p]config unignore #support @dartmern @muted\n[p]config unignore ~"}
    )
    @commands.has_permissions(manage_guild=True)
    async def config_unignore(self, ctx : MyContext, *entities : ChannelOrRoleOrMember):
        """Unignore ignored entities."""

        if not entities:
            return await ctx.send_help('config unignore')

        await ctx.typing()
        query = """
                DELETE FROM plonks
                WHERE server_id = $1
                AND entity_id = ANY($2::BIGINT[]);"""

        entries = [c.id for c in entities]

        await self.bot.db.execute(query, ctx.guild.id, entries)
        self.ignored[ctx.guild.id] = [
            x for x in self.ignored[ctx.guild.id] if not x in entries
        ]
        await ctx.send(
            f'Removed `{", ".join([str(x) for x in entries])}` from the ignored list.'
        )


    @config_unignore.command(
        name='all'
    )
    @commands.has_permissions(manage_guild=True)
    async def config_unignore_all(self, ctx : MyContext):
        """Unignore all previously ignored entities."""

        await ctx.invoke(self.config_ignore_clear)
  

    @config.group(
        name='toggle',
        invoke_without_command=True,
        case_insensitive=True
    )
    @is_dev()
    async def config_toggle(self, ctx : MyContext, *, command : Optional[str] = None):
        """Globally toggle a command."""

        if command is None:
            return await ctx.help()

        EXCEPTIONS = ['toggle']

        cmd = self.bot.get_command(command)
        if cmd is None:
            return await ctx.send(f'Command `{command}` not found.')

        if cmd.name in EXCEPTIONS:
            return await ctx.send(
                f'{self.bot.cross} Command `{cmd.qualified_name}` cannot be disabled.'
            )

        cmd.enabled = not cmd.enabled
        ternary = "Enabled" if cmd.enabled else "Disabled"
        await ctx.send(f'{ternary} `{cmd.qualified_name}`')


    @config_toggle.command(
        name='list'
    )
    @is_dev()
    async def config_toggle_list(self, ctx : MyContext):
        """List all the toggle disabled commands."""

        disabled_commands = []
        for command in self.bot.walk_commands():
            if command.enabled:
                pass
            else:
                disabled_commands.append(f'`{command.qualified_name}`')

        if disabled_commands:
            await ctx.send(", ".join(disabled_commands))
        else:
            await ctx.send('No commands are toggled.')
            
async def setup(bot):
    await bot.add_cog(configuration(bot))