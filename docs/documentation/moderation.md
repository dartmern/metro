# Moderation

**Moderation commands.**
#
For better readability this will be separated into different sections.
#

#### Permissions for:
- **kick**: `Kick Members`
- **softban**, **ban**, **unban**, **multiban**, **tempban**: `Ban Members`

| Name | Description | Usage | Aliases |
| :--- | :--- | :--- | :---
| kick | Kick a member from the server | `/kick <member> [reason]`
| softban | Soft-bans a member from the server. | `/softban <member> [delete_days=1] [reason]` 
| ban | Ban a member from the server. | `/ban <member> [delete_days=0] [reason]`
| unban | Unban a previously banned member. | `/unban <member>` |
| listbans | List all the banned users for this guild. | `/listbans` 
| multiban | Ban multiple people from the server. | `/multiban [users...] [reason]` 
| tempban | Temporarily bans a member for the specified duration. | `/tempban <member> <duration> [reason]` | 

#
#
#### Permissions for:
- **purge**: `Manage Messages`
- **slowmode**: `Manage Channels`
- **cleanup**: If amount if more than 25, `Manage Messages` is required

| Name | Description | Usage | Aliases |
| :--- | :--- | :--- | :---
| cleanup | Cleanup the bot's messages | `/cleanup [amount=25]`|
| slowmode | Change the slowmode for the current channel. | `/slowmode [duration=0] [--silent]` | sm |
| purge | Remove messages that meet a certain criteria. | `/purge <amount>` | clear, clean
| purge user | Remove all messages sent by that member. | `/purge user <user> <amount>`
| purge custom | A more advanced purge command with a command-line-like syntax. | `/purge custom [args]`
| purge embeds | Remove messages that have embeds in them. | `/purge embeds <amount>`
| purge contains | Remove all messages containing a substring. | `/purge contains <text>`
| purge images | Remove messages that have embeds or attachments. | `/purge images <amount>`
| purge threads | Remove threads from the channel. | `/purge threads <amount>`
| purge reactions | Remove all reactions from messages that have them. | `/purge reactions <amount>`
| purge bot | Remove a bot's user messages and messages with their optional prefix. | `/purge bot [prefix] [search=25]`
| purge files | Remove messages that have files in them. | `/purge files <search>`
| purge emoji | Remove all messages containing a custom emoji. | `/purge emoji <amount>`
| purge all | Remove all messages. | `/purge all <amount>`

#
#
#### Permissions: `Manage Channels`

| Name | Description | Usage | Aliases |
| :--- | :--- | :--- | :---
| block | Block a member from your channel. | `/block <member>`
| unblock | Unblock a member from your channel. | `/unblock <member>`
| tempblock | Temporarily blocks a user from your channel. | `/tempblock <member> <duration>`

#
#
#### Permissions for: 
- **mute**, **unmute**: `Manage Roles`
- **selfmute**, **mutelist**: `No Permissions`
- **muterole**: `Manage Server`

| Name | Description | Usage | Aliases |
| :--- | :--- | :--- | :---
| mute | Mute multiple members using the configured muted role. | `/mute <members...> [duration] [reason]` | moot |
| unmute | Unmute previously muted members. | `/unmute <members...> [reason]` | unmoot |
| selfmute | Temporarily mute yourself for a specific duration. | `/selfmute <duration>`
| mutelist | List all the current and active mutes in this server. | `/mutelist`
| muterole | Manage this guild's mute role with an interactive menu. | `/muterole`
