# Reaction Roles

This is a simple implementation of reaction roles.
#

Please check out the [Reaction Roles FAQ](https://dartmern.github.io/metro/faq/#my-reaction-roles-arent-working-why) if you are having issues with reaction roles.

After setting up reaction roles please make sure the bot's top role is higher than the roles you want to hand out. You can do this by moving the `@Metro` role.
#
#### Permissions required: `Manage Server`

| Name | Description | Usage | Aliases |
| :--- | :--- | :--- | :---
| reactionrole | Base command for managing reaction roles. | `/reactionrole` | rr
| reactionrole add | Add a reaction role to a message. | `/rr add [message] <emoji> <role>` | create, +
| reactionrole remove | Remove a reaction role from a message. | `/rr remove [message] <emoji> <role>` | -
| reactionrole list | Display all the reaction roles for this guild. | `/rr list` 

#
This category is stil under development and you should report bugs to my [support server](https://discord.gg/2ceTMZ9qJh).
