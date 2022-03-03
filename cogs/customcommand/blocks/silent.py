from typing import Optional

from TagScriptEngine import Block, Context, helper_parse_if


class SilentBlock(Block):
    # This is an undocumented block and should not be used.
    def will_accept(self, ctx: Context) -> bool:
        dec = ctx.verb.declaration.lower()
        return any([dec == "silent", dec == "silence"])

    def process(self, ctx: Context) -> Optional[str]:
        if "silent" in ctx.response.actions.keys():
            return None
        if ctx.verb.parameter is None:
            value = True
        else:
            value = helper_parse_if(ctx.verb.parameter)
        ctx.response.actions["silent"] = value
        return ""