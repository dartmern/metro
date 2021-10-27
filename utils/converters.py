import discord
from discord.ext import commands



  
def can_execute_action(ctx, user, target):
    return (
        user.id == ctx.bot.owner_id
        or user == ctx.guild.owner
        or user.top_role > target.top_role
    )

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
                raise commands.BadArgument(
                    f"{argument} is not a valid member or member ID"
                )

        if not can_execute_action(ctx, ctx.author, m):
            raise commands.BadArgument(
                f"{self.bot.cross} You cannot do this action on this user due to role hierarchy."
            )
        return m



#for multiban (only takes ids and turns into all members)
class MemberID(commands.Converter):
    async def convert(self, ctx, argument):
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
    async def convert(self, ctx, argument):
        ret = f'Action requested by {ctx.author} (ID: {ctx.author.id})\nReason: {argument}'

        if len(ret) > 512:
            reason_max = 512 - len(ret) + len(argument)
            raise commands.BadArgument(f'Reason is too long ({len(argument)}/{reason_max})')
        return ret






async def prettify(ctx, arg):
    pretty_arg = await commands.clean_content().convert(ctx, str(arg))
    return pretty_arg


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

































































