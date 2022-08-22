import re
import typing
import discord
from discord.ext import commands

from utils.converters import RoleConverter
from utils.custom_context import MyContext

import re
import typing
from utils.converters import RoleConverter

from .mee6_converter import MEE6_Converter

class Requirements(commands.Converter):
    async def convert(self, ctx: MyContext, argument: str) -> typing.Dict:

        requirements = {
            "role": [],
            "bypass": [],
            "blacklist": [],
            "mee6": None           
        }
        if argument.lower() == "none": # no requirement
            return requirements

        pattern = re.compile(r"\||;;")
        argument = pattern.split(argument)

        for arg in argument:
            split = arg.lower().split(":")

            if len(split) == 1:
                role = await RoleConverter().convert(ctx, arg)
                requirements["role"] += [role.id]
                continue
                
            if split[0] == "role":
                role = await RoleConverter().convert(ctx, split[1])
                requirements["role"] += [role.id]
                continue

            if split[0] == "bypass":
                role = await RoleConverter().convert(ctx, split[1])
                requirements["bypass"] += [role.id]
                continue

            if split[0] == "blacklist":
                role = await RoleConverter().convert(ctx, split[1])
                requirements["blacklist"] += [role.id]

            if split[0] == "mee6":
                level = await MEE6_Converter().convert(ctx, split[1])
                requirements["mee6"] = level

        requirements["role"] = list(set(requirements["role"]))
        requirements["bypass"] = list(set(requirements["bypass"]))
        requirements["blacklist"] = list(set(requirements["blacklist"]))

        return requirements
        