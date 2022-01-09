import discord
from discord.ext import commands


import re
from rapidfuzz import process
from unidecode import unidecode

from utils.checks import can_execute_action
from utils.custom_context import MyContext

async def prettify(ctx, arg):
    pretty_arg = await commands.clean_content().convert(ctx, str(arg))
    return pretty_arg

def is_admin(ctx):
    if (
        ctx.author.id in ctx.bot.constants.admins
        or ctx.author.id in ctx.bot.constants.owners
    ):
        return True
    return

SNOWFLAKE_REGEX = re.compile(r"([0-9]{15,21})$")
  
class BoolConverter(commands.Converter):
    async def convert(self, ctx, argument):
        lookup = {
                  True:  ('yes', 'y', 'true', 't', '1', 'enable', 'on'),
                  False: ('no', 'n', 'false', 'f', '0', 'disable', 'off')
                 }
        lower = argument.lower()
        for mode, storage in lookup.items():
            if lower in storage:
                return mode

        raise commands.BadArgument('whetever')

class MemberConverter(commands.Converter):
    async def convert(self, ctx, argument):
        try:
            m = await commands.MemberConverter().convert(ctx, argument)
        except commands.BadArgument:
            m = discord.utils.find(
                lambda x: x.name.lower() == argument.lower(), ctx.guild.members
            )
            if m is None:
                raise commands.MemberNotFound(argument)

        if not can_execute_action(ctx, ctx.author, m):
            raise commands.BadArgument(
                f"{self.bot.cross} You cannot do this action on this user due to role hierarchy."
            )
        return m


#for multiban (only takes ids and turns into all members)
class MemberID(commands.Converter):
    async def convert(self, ctx, argument) -> discord.Member:
        try:
            m = await commands.MemberConverter().convert(ctx, argument)
        except commands.BadArgument:
            try:
                member_id = int(argument, base=10)
            except ValueError:
                raise commands.BadArgument(f"{argument} is not a valid member or member ID.") from None
            else:
                m = await ctx.bot.get_or_fetch_member(ctx.guild, member_id)
                if m is None:
                    # hackban case
                    return type('_Hackban', (), {'id': member_id, '__str__': lambda s: f'Member ID {s.id}'})()

        if not can_execute_action(ctx, ctx.author, m):
            raise commands.BadArgument('You cannot do this action on this user due to role hierarchy.')
        return m

class ActionReason(commands.Converter):
    async def convert(self, ctx, argument) -> str:
        ret = f'Action requested by {ctx.author} (ID: {ctx.author.id})\nReason: {argument}'

        if len(ret) > 512:
            reason_max = 512 - len(ret) + len(argument)
            raise commands.BadArgument(f'Reason is too long ({len(argument)}/{reason_max})')
        return ret

class RoleConverter(commands.RoleConverter):
    """
    This will accept role ID's, mentions, and perform a fuzzy search for
    roles within the guild and return a list of role objects
    matching partial names
    Guidance code on how to do this from:
    https://github.com/Rapptz/discord.py/blob/rewrite/discord/ext/commands/converter.py#L85
    https://github.com/Cog-Creators/Red-DiscordBot/blob/V3/develop/redbot/cogs/mod/mod.py#L24
    """

    def __init__(self, response: bool = True):
        self.response = response
        super().__init__()

    async def convert(self, ctx: commands.Context, argument: str) -> discord.Role:
        try:
            basic_role = await super().convert(ctx, argument)
        except commands.BadArgument:
            pass
        else:
            return basic_role
        guild = ctx.guild
        result = [
            (r[2], r[1])
            for r in process.extract(
                argument,
                {r: unidecode(r.name) for r in guild.roles},
                limit=None,
                score_cutoff=75,
            )
        ]
        if not result:
            raise commands.BadArgument(f'Role "{argument}" not found.' if self.response else None)

        sorted_result = sorted(result, key=lambda r: r[1], reverse=True)
        return sorted_result[0][0]

class DiscordCommand(commands.Converter):
    """
    Basic command converter.
    """

    async def convert(self, ctx, argument):
        command = ctx.bot.get_command(argument.lower())
        if not command:
            raise commands.BadArgument(
                f"Command `{await prettify(ctx, argument)}` not found."
            )
        return command

class ChannelOrRoleOrMember(commands.Converter):
    """
    Converter for config command group
    """

    async def convert(self, ctx, argument):

        if argument.lower() == '~':
            return ctx.guild
            
        try:
            return await commands.TextChannelConverter().convert(ctx, argument)
        except commands.ChannelNotFound:
            try:
                return await commands.RoleConverter.convert(ctx, argument)
            except Exception:
                try:
                    return await commands.MemberConverter().convert(ctx, argument)
                except Exception:
                    raise commands.BadArgument(
                        f"Entity `{await prettify(ctx, argument)}` is an invalid input. Please specify a channel, role, or user."
                    )

class DiscordGuild(commands.Converter):
    """Match guild_id, or guild name exact, only if author is in the guild."""

    def get_by_name(self, ctx, guild_name):
        """Lookup by name.
        Returns list of possible matches.
        Try doing an exact match.
        Fall back to inexact match.
        Will only return matches if ctx.author is in the guild.
        """
        if is_admin(ctx):
            result = discord.utils.find(lambda g: g.name == guild_name, ctx.bot.guilds)
            if result:
                return [result]

            guild_name = guild_name.lower()

            return [g for g in ctx.bot.guilds if g.name.lower() == guild_name]
        else:
            result = discord.utils.find(
                lambda g: g.name == guild_name and g.get_member(ctx.author.id),
                ctx.bot.guilds,
            )
            if result:
                return [result]

            guild_name = guild_name.lower()

            return [
                g
                for g in ctx.bot.guilds
                if g.name.lower() == guild_name and g.get_member(ctx.author.id)
            ]

    async def find_match(self, ctx, argument):
        """Get a match...
        If we have a number, try lookup by id.
        Fallback to lookup by name.
        Only allow matches where ctx.author shares a guild.
        Disambiguate in case we have multiple name results.
        """
        lax_id_match = SNOWFLAKE_REGEX.match(argument)
        if lax_id_match:
            result = ctx.bot.get_guild(int(lax_id_match.group(1)))

            if is_admin(ctx):
                if result:
                    return result
            else:
                if result and result.get_member(ctx.author.id):
                    return result

        results = self.get_by_name(ctx, argument)
        if results:
            return results[0]

    async def convert(self, ctx, argument):
        match = await self.find_match(ctx, str(argument))

        if not match:
            raise commands.BadArgument(
                f"Server `{await prettify(ctx, argument)}` not found."
            )
        return match



class BotUser(commands.Converter):
    async def convert(self, ctx, argument):
        if not argument.isdigit():
            raise commands.BadArgument('Not a valid bot user ID.')
        try:
            user = await ctx.bot.fetch_user(argument)
        except discord.NotFound:
            raise commands.BadArgument('Bot user not found (404).')
        except discord.HTTPException as e:
            raise commands.BadArgument(f'Error fetching bot user: {e}')
        else:
            if not user.bot:
                raise commands.BadArgument('This is not a bot.')
            return user

class BotUserObject(commands.MemberConverter):
    async def convert(self, ctx, argument: str) -> discord.Member:
        user = await super().convert(ctx, argument)
        if not user.bot:
            raise commands.BadArgument("This is not a bot.")
        else:
            return user
        
        
class ImageConverter(commands.Converter):
    async def convert(self, ctx: MyContext, argument: str):
        
        if argument:
            x = re.findall(
                r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
                argument,
            )
            if x:
                return x[0]
        elif ctx.message.reference:
            x = re.findall(
                r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
                ctx.message.reference.resolved.content,
            )
            if x:
                return x[0]

        try:
            return (await commands.MemberConverter().convert(ctx, argument)).display_name.url
        except:
            try:
                return (
                    await commands.UserConverter().convert(ctx, argument)
                ).display_avatar.url
            except:
                pass

        if ctx.message.attachments:
            return ctx.message.attachments[0].url
        if ctx.message.reference:
            if ctx.message.reference.resolved.attachments:
                return ctx.message.reference.resolved.attachments[0].url

            elif ctx.message.reference.resolved.embeds:
                for embed in ctx.message.reference.resolved.embeds:
                    if embed.image is not discord.Embed.Empty:
                        return embed.image.url
                    elif embed.thumbnail is not discord.Embed.Empty:
                        return embed.thumbnail.url

        if ctx.message.content:
            if emoji := re.findall(
                r"<(?P<animated>a?):(?P<name>[a-zA-Z0-9_]{2,32}):(?P<id>[0-9]{18,22})>",
                ctx.message.content,
            ):
                emoji_id = emoji[0][2]
                return f"https://cdn.discordapp.com/emojis/{emoji_id}.png"
        elif ctx.message.reference:
            if ctx.message.reference.resolved.content:
                if emoji := re.findall(
                    r"<(?P<animated>a?):(?P<name>[a-zA-Z0-9_]{2,32}):(?P<id>[0-9]{18,22})>",
                    ctx.message.reference.resolved.content,
                ):
                    emoji_id = emoji[0][2]
                    return f"https://cdn.discordapp.com/emojis/{emoji_id}.png"

            return ctx.message.reference.resolved.author.avatar.url

        return None