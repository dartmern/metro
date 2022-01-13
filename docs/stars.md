# Stars

**Manage and create starboard commands.**


Credit for cog this is 100% of [R. Danny's](https://github.com/Rapptz/RoboDanny/blob/1fb95d76d1b7685e2e2ff950e11cddfc96efbfec/cogs/) starboard cog. 
#

#### Permissions required: `Manage Guild`

| Name | Description | Usage | Aliases |
| :--- | :--- | :--- | :---
| starboard | Setup the starboard for this server <br /> <br />This will create a new channel with the specified name and make it into the server's "starboard". If no name is passed then it will default to the name "starboard". <br /><br /> You can edit details about the starboard channel after running this command and after I create the channel. | `/starboard [name='starboard']`
| star | Stars a message via message ID. | `/star <message>`
| star age | Sets the maximum age of a message valid for starring. | `/star age <number> [units='days']`
| star limit | Sets the minimum number of stars required to show up. | `/star limit <stars>`
| star lock | Locks the starboard from being processed. | `/star lock`
| star unlock | Unlocks the starboard for re-processing. | `/star unlock`