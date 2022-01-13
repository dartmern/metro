# Server Utilities

**Server utilities like role, lockdown, nicknames.**
#
#### Permissions for:
- **lockdown**, **unlockdown**, **nuke-channel**: `Manage Channels`
- **grant**: `Administrator`

| Name | Description | Usage | Aliases |
| :--- | :--- | :--- | :---
| lockdown | Lockdown a channel. | `/lockdown [channel] [duration]` | lock
| unlockdown | Unlockdown a channel. | `/unlockdown [channel]` | unlock
| nuke-channel | Nuke a text channel. | `/nuke [channel]` | nuke
| grant-permissions | Grant an entity certain permissions. Entity may be a role **or** a member. | `/grant <entity> [perms...]` | grant-permissions

#
#### Permissions required for **role**: `Manage Roles`

| Name | Description | Usage | Aliases |
| :--- | :--- | :--- | :---
| role | Base command for modifying roles. | `/role <member> <role>` 
| role add | Add a role to a member. | `/role add <member> <role>` 
| role addmulti | Add a role to multiple members. | `/role addmulti <role> [members...]` |
| role all | Add a role to all members of the guild. | `/role all <role>`
| role bots | Add a role to all bots in the guild. | `/role bots <role>`
| role color | Change a role's color. | `/role color <role> <color>`
| role create | Create a new role. | `/role create [color=#000000] [hoist=False] <name>`
| role hoist | Toggle a role's hoist status. | `/role hoist <role>`
| role humans | Add a role to all humans in the guild. | `/role humans <role>`
| role in | Add a role to members of another role. | `/role in <base_role> <target_role>`
| role info | Show all the information about a role. | `/role info <role>`
| role list | List all the roles the guild has. The [tagscript](https://enhanced-dpy.readthedocs.io/en/latest/api.html#discord.Role) argument is the way you want to format the roles. Any attribute a role has, you can add there. | `/role list [tagscript]`
| role rall | Remove a role from all members of the guild. | `/role rall <role>`
| role rbots | Remove a role from all bots in the guild. | `/role rbots <role>`
| role remove | Remove a role from a member. | `/role remove <member> <role>`
| role removemulti | Remove a role from multiple members. | `/role removemulti <role> [members...]`
| role rename | Rename a role's name. | `/role rename <role> <name>`
| role rhumans | Remove a role from all humans in the guild. | `/role rhumans <role>`
| role rin | Remove a role from members of another role. | `/role rin <base_role> <target_role>`
| temprole | Adds a role to a member and removes it after the specified time | `/temprole <member> <role> <duration>`

#
#### Permissions required for **decancer** and **nickname**: `Manage Nicknames`

| Name | Description | Usage | Aliases |
| :--- | :--- | :--- | :---
| decancer | Remove special/cancerous characters from a user's nickname. | `/decancer <member>` | dc
| nickname | Change a member's nickname. | `/nickname [member] [nickname]` | nick

#
## Notes
| Name | Description | Usage | Aliases |
| :--- | :--- | :--- | :---
| note | Base command for managing notes. | `/note` 
| note add | Add a note to a member's notes. | `/note add <member> <note>` | +
| note remove | Remove a note by it's id. (You can only remove notes you added) | `/note remove <id>` | -
| note clear | Clear a member's notes. `Manage Server` only | `/note clear <member>` | wipe
| note redo | Clear a member's notes and replace with a single note. | `/note redo <member> <note>`
| note list | Show a member's notes. | `/note list <member>`
| notes | Show your own notes. | `/notes`

#
## Information/Stats
| Name | Description | Usage | Aliases |
| :--- | :--- | :--- | :---
| user-info | Shows all the information about the specified user/member. | `/user-info <member>` | userinfo, ui, whois
| server-info | Show all the information about the current guild. | `/server-info` | serverinfo, si
| channel-info | Show all the information about a channel. | `/channel-info [channel]` | channelinfo, ci
| role-info | Show all the information about a role. | `/role-info <role>` | ri

# 
## Emoji
#### Permissions required for **role**: `Manage Emojis`
| Name | Description | Usage | Aliases |
| :--- | :--- | :--- | :---
| emoji | Base command for managing emojis. | `/emoji`
| emoji add | Add a custom emoji. You can input a url or upload a png. | `/emoji add <name> [url]` | create, +
| emoji remove | Delete a emoji. | `/emoji remove <emoji>` | delete, -
| emoji list | List all the emojis in the guild. Use the `--ids` flag if you want emoji ids when listed. | `/emoji list [--ids]` | show
| emoji steal | Add an emoji from a specified messages. Supply a message or reply to one. | `/emoji steal [message]`
| emoji rename | Rename an emoji. | `/emoji rename <emoji> <name>`

