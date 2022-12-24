import discord

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
