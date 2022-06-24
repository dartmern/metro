import re
import typing
import discord
from discord.ext import commands

from utils.converters import RoleConverter
from utils.custom_context import MyContext

import re
import typing
from utils.converters import RoleConverter

class Requirements(commands.Converter):
    async def convert(self, ctx: MyContext, argument: str) -> typing.Dict:

        requirements = {
            "role": [],
            "bypass": [],
            "blacklist": []            
        }
        if argument.lower() == "none": # no requirement
            return requirements

        pattern = re.compile(r"\||;;")
        argument = pattern.split(argument)

        for arg in argument:
            split = arg.lower().split(":")

            if len(split) == 1:
                role = await RoleConverter().convert(ctx, arg)
                requirements["role"] += [role]
                continue
                
            if split[0] == "role":
                role = await RoleConverter().convert(ctx, split[1])
                requirements["role"] += [role]
                continue

            if split[0] == "bypass":
                role = await RoleConverter().convert(ctx, split[1])
                requirements["bypass"] += [role]
                continue

            if split[0] == "blacklist":
                role = await RoleConverter().convert(ctx, split[1])
                requirements["blacklist"] += [role]

        requirements["role"] = list(set(requirements["role"]))
        requirements["bypass"] = list(set(requirements["bypass"]))
        requirements["blacklist"] = list(set(requirements["blacklist"]))

        return requirements
        