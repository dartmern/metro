# Utilities

Get utilities like prefixes, serverinfo, source, etc.

Metro is very utility based and this category is
the most documented part of the bot.
#
| Name | Description | Usage | Aliases |
| :--- | :--- | :--- | :---
| mystbin | Create and post a mystbin online. | `/mystbin <text>`
| gist | Create and post a gist online. | `/gist <text>` |
| permissions | Shows a member's permissions in a specific channel. | `/permissions [member] [channel]`
| charinfo | Shows you information about a number of characters. <br />Only up to 25 characters at a time. | `/charinfo <characters>`
| source | Links to the bot's source code, or a specific command's | `/source [command | group-command]` | sourcecode, code, src
| archive | Archive a message by replying or passing in a message link. | `/archive [message]` | save
| raw-message | Get the raw json format of a message. <br > Pass in a message or reply to work this. | `/raw-message [message]` | rawmessage, rmsg, raw
| first-message | Get the first message in a channel. | `/first-message [channel]` | firstmsg, firstmessage
| embed | Post an embed from json. <br/><br/> Click here to build your embed, then click copy and paste that as an argument for this command. | `/embed <json>`
#
## Prefix Management
| Name | Description | Usage | Aliases |
| :--- | :--- | :--- | :---
| prefix | Manage prefixes for the bot. | `/prefix` 
| prefix add | Add a prefix to the guild's prefixes. | `/prefix add <prefix>`
| prefix remove | Remove a prefix from the bot's prefixes. | `/prefix remove <prefix>`
| prefix list |  Clears all my prefixes and resets to default. |`/prefix list`
| prefix clear | Clears all my prefixes and resets to default. | `/prefix clear`

#
## Todo List Management
| Name | Description | Usage | Aliases |
| :--- | :--- | :--- | :---
| todo | Manage your todo lists. | `/todo`
| todo add |  Add an item to your todo list | `/todo add <item>`
| todo remove | Remove one of your todo list entries. | `/todo remove <indxe>`
| todo list | Show your todo list. | `/todo list`
| todo clear | Clear all your todo entries. | `/todo clear`
| todo edit | Edit an exisiting todo list entry. | `/todo edit <index> <item>`

#
## Reminders
| Name | Description | Usage | Aliases |
| :--- | :--- | :--- | :---
| reminder | Reminds you of something after a certain amount of time. <br /><br />The input can be any direct date (e.g. YYYY-MM-DD) or a human readable offset. Examples: <br /><br/>- "next thursday at 3pm do something funny" <br /> - "do the dishes tomorrow" <br />- "in 3 days do the thing" <br /> - "2d unmute someone" | `/reminder <when>` | remind, rm
| reminder list | Display all your current reminders. | `/reminder list` 
| reminder delete | Deletes a reminder by it's id | `/reminder delete <id>` 
| reminder clear | Clear all reminders you set. | /reminder clear`


#
# Giveaways
This is just a simple giveaway system, don't rely on it too much.

| Name | Description | Usage | Aliases |
| :--- | :--- | :--- | :---
| giveaway | Manage and create giveaways for your server. | `/giveaway` | g
| giveaway start | Start a giveaway! | `/giveaway <duration> [winners=1] <prize> [flags]` 
| giveaway end | End a giveaway early. | `/giveaway end`
| giveaway list | List all the active giveaways. | `/giveaway list`


#
## Highlights

| Name | Description | Usage | Aliases |
| :--- | :--- | :--- | :---
| highlight | Highlight word notifications. | `/highlight` | hl
| highlight add | Add a word to your highlight list. | `/highlight add <word>`
| highlight remove | Remove a word from your highlight list. | `/highlight remove <word>`
| highlight list | Show your highlight list. | `/highlight list`
| highlight clear | Clear your highlights. | `/highlight clear`




