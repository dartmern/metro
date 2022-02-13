from utils.custom_context import MyContext

class SilentContext(MyContext):
    """MyContext but is silent which prevents output."""

    async def send(self, *args, **kwargs):
        pass

    async def reply(self, *args, **kwargs):
        pass