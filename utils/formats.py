import discord

import traceback

def clean_code(content: str):
    if content.startswith("```") and content.endswith("```"):
        return "\n".join(content.split("\n")[1:])[:-3]
    if content.startswith("```py") and content.endswith("```"):
        return "\n".join(content.split("\n")[1:])[:-3]
    else:
        return content

def to_codeblock(content: str, language="py", replace_existing=True, escape_md=True, new="'''"):
    if replace_existing:
        content = content.replace("```", new)
    if escape_md:
        content = discord.utils.escape_markdown(content)
    return f"```{language}\n{content}\n```"

class plural:
    def __init__(self, value):
        self.value = value

    def __format__(self, format_spec):
        v = self.value
        singular, sep, plural = format_spec.partition("|")
        plural = plural or f"{singular}s"
        if abs(v) != 1:
            return f"{v} {plural}"
        return f"{v} {singular}"

# Usage for plural
# "You have 0 {plural(1):tasks}"

def human_join(seq, delim=', ', final='or'):
    size = len(seq)
    if size == 0:
        return ''

    if size == 1:
        return seq[0]

    if size == 2:
        return f'{seq[0]} {final} {seq[1]}'

    return delim.join(seq[:-1]) + f' {final} {seq[-1]}'
