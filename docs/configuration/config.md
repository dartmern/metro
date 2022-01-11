# Configuration

#### Configure the bot/server.
#

#### ⚠️ These commands are mainly reserved for members with `Manage Guild` ⚠️
#
**Tip:** Use `~` in place of entity to disable a command for the entire guild.
#
## config **enable**/**disable**
##### Permissions: `Manage Guild`

| Name | Description | Usage | Aliases
| :--- | :--- | :--- | :---
| config disable | Prevent specific commands from being run in channels, users, or roles. | `/config disable [entity] [commands...]` |
| config disable clear | Clear all disabled commands. | `/config disable clear` | 
| config disable list | Show disabled commands | `/config disable list` |
| config enable | Let specific commands being runable in channels, users, or roles. | `/config enable [entity] [commands...]` |
| config enable all | Clear all disabled commands. (alias) | `/config enable clear` |

## config **ignore**/**disable**
##### Permissions: `Manage Guild`

| Name | Description | Usage | Aliases
| :--- | :--- | :--- | :---
| config ignore | Ignore all commands in an entity. | `/config ignore [entities...]` |
| config ignore list | Show all ignored entities. | `/config ignore list` |
| config ignore clear | Clear the ignored list. | `/config ignore clear` |
| config unignore | Unignore ignored entities. | `/config unignore [entities...]` |
| config unignore all | Unignore all previously ignored entities. (alias) | `/config unignore all` |

