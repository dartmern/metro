import discord
from discord.ext import commands

from utils.context import MyContext

from lark import Lark, Transformer, v_args

calc_grammar = """
    ?start: sum
          | NAME "=" sum    -> assign_var
    ?sum: product
        | sum "+" product   -> add
        | sum "-" product   -> sub
    ?product: atom
        | product "*" atom  -> mul
        | product "/" atom  -> div
    ?atom: NUMBER           -> number
         | "-" atom         -> neg
         | NAME             -> var
         | "(" sum ")"
    %import common.CNAME -> NAME
    %import common.NUMBER
    %import common.WS_INLINE
    %ignore WS_INLINE
"""

@v_args(inline=True)    # Affects the signatures of the methods
class CalculateTree(Transformer):
    from operator import add, sub, mul, truediv as div, neg
    number = float

    def __init__(self):
        self.vars = {}

    def assign_var(self, name, value):
        self.vars[name] = value
        return value

    def var(self, name):
        try:
            return self.vars[name]
        except KeyError:
            raise Exception("Variable not found: %s" % name)

calc_parser = Lark(calc_grammar, parser='lalr', transformer=CalculateTree())
calc = calc_parser.parse




class calculator(commands.Cog, description='<:calc:904080776847560714> Custom calculator.'):

    def __init__(self, bot):
        self.bot = bot


    @commands.command(
        name='calculator',
        aliases=['calc','math'],
        slash_command=True
    )
    async def calculator(self, ctx : MyContext, *, equation : str):
        """Use a calculator and solve equations."""

        await ctx.send(calc(equation),hide=True)

    
    

def setup(bot):
    bot.add_cog(calculator(bot))
