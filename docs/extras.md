# API Commands

| Name | Description | Usage | Aliases |
| :--- | :--- | :--- | :---
shorten_url | Shorten a long url. | `/shorten_url <url>` | shorten
| repl | Compile code through coliru. | `/repl <code>` | coliru
| nsfw-check | Check for NSFW in an image. | `/nsfw-check [member ∣ image]` | 

#

- **shorten_url** is powered by [Bitly API](https://dev.bitly.com/)
#
- **repl** is powered by [Coliru](http://coliru.stacked-crooked.com/compile) <br />
Pass in a codeblock using the language of your choice. <br />
You can use `py` or `css` as a language inside codeblocks.
#
- **nsfw-check** is powered by [OpenRobot API](https://api.openrobot.xyz/api/docs#operation/do_nsfw_check_api_nsfw_check_get)


# Miscellaneous 

**Miscellaneous commands for your server.**
#
| Name | Description | Usage | Aliases |
| :--- | :--- | :--- | :---
| whatcog | Show what cog a command belongs to. | `/whatcog <commnand>` |
| length | Get the length of a string. | `/length <object>` |
| calculate | Calculate an equation. | `/calculate [equation]` | calc
| poll | Simple yes/no poll with reactions. | `/poll <question>` |