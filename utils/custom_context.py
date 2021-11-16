import discord
from discord.ext import commands, menus

from typing import List, Optional

from utils.new_pages import SimplePageSource, SimplePages



class ConfirmationView(discord.ui.View):
    def __init__(self, *, timeout: float, author_id: int, ctx, delete_after: bool) -> None:
        super().__init__(timeout=timeout)
        self.value: Optional[bool] = None
        self.delete_after: bool = delete_after
        self.author_id: int = author_id
        self.ctx = ctx
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user and interaction.user.id == self.author_id:
            return True
        else:
            await interaction.response.send_message('This confirmation dialog is not for you.', ephemeral=True)
            return False

    async def on_timeout(self) -> None:
        self.confirm.disabled = True
        self.cancel.disabled = True
        self.value = None
        await self.message.edit(view=self)

    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.green)
    async def confirm(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.value = True
        await interaction.response.defer()
        if self.delete_after:
            await interaction.delete_original_message()
        self.stop()

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.red)
    async def cancel(self, button: discord.ui.Button, interaction: discord.Interaction):
        self.value = False
        await interaction.response.defer()
        if self.delete_after:
            await interaction.delete_original_message()
        self.stop()



class MyContext(commands.Context):

    async def check(self):
        emoji = self.bot.get_emoji(819254444197019669)

        try:
            await self.message.add_reaction(emoji)
        except discord.HTTPException:
            pass
               

    async def cross(self):
        emoji = self.bot.get_emoji(819254444217860116)

        try:
            await self.message.add_reaction(emoji)
        except discord.HTTPException:
            pass

    async def defer(self):

        if self.interaction:
            pass
        else:
            await self.trigger_typing()

    async def send(self, content : str = None, embed : discord.Embed = None, hide : bool = False, **kwargs):

        if content: 
            content=str(content)

            if self.bot.http.token in content:
                content = content.replace(self.bot.http.token, "[Token Hidden]")

        if self.interaction == None:
            message = await super().send(content=content, embed=embed, **kwargs)
        else:
            if embed:
                message = await super().send(content=content, embed=embed, ephemeral=hide, **kwargs)
            else:
                message = await super().send(content=content, ephemeral=hide, **kwargs)
            
        return message
          

    async def confirm(
        self,
        message : str,
        *,
        timeout : float = 60.0,
        delete_after : bool = True,
        author_id : Optional[int] = None

    ) -> Optional[bool]:

        author_id = author_id or self.author.id

        view = ConfirmationView(
            timeout=timeout,
            delete_after=delete_after,
            ctx=self,
            author_id=author_id

        )
        view.message = await self.send(message, view=view)
        await view.wait()
        return view.value
        

    async def paginate(
        self,
        entries : List,
        *,
        per_page : int = 8,
        source : Optional[menus.ListPageSource] = None,
        hide : bool = False

    ):

        default_source = SimplePageSource(
            entries=list(entries),
            per_page=per_page
        )
        source = source or default_source

        menu = SimplePages(
            source=source, ctx=self, hide=hide)
        await menu.start()

    @discord.utils.cached_property
    def replied_reference(self):
        ref = self.message.reference
        if ref and isinstance(ref.resolved, discord.Message):
            return ref.resolved.to_reference()
        return None

    
    async def help(self):
        await self.send_help(self.command)

    async def get_message(self, id : int, channel : Optional[discord.TextChannel] = None):
        channel = channel or self.channel

        message = discord.utils.get(self.bot.cached_messages, id=id)
        if message:
            return message
        else:
            if channel:
                return await channel.fetch_message(id)
            else:
                return None
                