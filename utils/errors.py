from discord.ext import commands
import discord
from discord import app_commands

class UserBlacklisted(commands.CheckFailure):
    pass

class UserBlacklistedInteraction(app_commands.CheckFailure):
    pass

class ConverterError(commands.BadArgument):
    def __init__(self, message: str = None, embed: discord.Embed = None, *args) -> None:
        super().__init__(message, *args)
        self.embed = embed
