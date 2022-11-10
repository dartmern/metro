import discord

import tagformatter

RoleParser = tagformatter.Parser()

@RoleParser.tag("role")
def _role(env):
    return str(env.role)
        
@_role.tag('color', alias='colour')
def _role_color(env):
    return env.role.color

@_role.tag('created_at')
def _role_timestamp(env):
    return env.role.created_at

@_role.tag('created_at_timestamp')
def _role_created_at_timestamp(env):
    return discord.utils.format_dt(env.role.created_at, 'R')

@_role.tag('emoji')
def _role_emoji(env):
    return env.role.emoji

@_role.tag('guild')
def _role_guild(env):
    return env.role.guild

@_role.tag('hoist')
def _role_hoist(env):
    return env.role.hoist

@_role.tag('icon')
def _role_icon(env):
    return env.role.icon

@_role.tag('id')
def _role_id(env):
    return env.role.id

@_role.tag('managed')
def _role_managed(env):
    return env.role.managed

@_role.tag('members')
def _role_members(env):
    return len(env.role.members)

@_role.tag('mention')
def _role_mention(env):
    return env.role.mention

@_role.tag('mentionable')
def _role_mentionable(env):
    return env.role.mentionable

@_role.tag('name')
def _role_name(env):
    return env.role.name

@_role.tag('position')
def _role_position(env):
    return env.role.position
    