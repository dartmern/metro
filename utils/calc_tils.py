import pyparsing
import operator
import math
from functools import cmp_to_key




class NumericStringParser(object):
    """
    Most of this code comes from the fourFn.py pyparsing example
    """

    def pushFirst(self, strg, loc, toks):
        self.exprStack.append(toks[0])

    def pushUMinus(self, strg, loc, toks):
        if toks and toks[0] == "-":
            self.exprStack.append("unary -")

    def __init__(self):
        """
        Usage: calculate <expression>
        Aliases: -math, -calc
        Output: The result of your input
        Examples:
            -calc 2 + 2 + 4 + 5
            -calc sqrt(532)
            -calc log(2)
            -calc sin(PI * E)
        exponentiation: '^'
        multiplication: 'x' | '*'
        division: '/'
        addition: '+' | '-'
        integer: ['+' | '-'] '0'..'9'+
        constants: PI | E
        Functions:  # To be used in the form -calc function(expression)
            sqrt
            log
            sin
            cos
            tan
            arcsin
            arccos
            arctan
            sinh
            cosh
            tanh
            arcsinh
            arccosh
            arctanh
            abs
            trunc
            round
            sgn
        """
        point = pyparsing.Literal(".")
        e = pyparsing.CaselessLiteral("E")
        fnumber = pyparsing.Combine(
            pyparsing.Word("+-" + pyparsing.nums, pyparsing.nums)
            + pyparsing.Optional(
                point + pyparsing.Optional(pyparsing.Word(pyparsing.nums))
            )
            + pyparsing.Optional(
                e + pyparsing.Word("+-" + pyparsing.nums, pyparsing.nums)
            )
        )
        ident = pyparsing.Word(
            pyparsing.alphas, pyparsing.alphas + pyparsing.nums + "_$"
        )
        plus = pyparsing.Literal("+")
        minus = pyparsing.Literal("-")
        mult = pyparsing.Literal("x")
        div = pyparsing.Literal("/")
        lpar = pyparsing.Literal("(").suppress()
        rpar = pyparsing.Literal(")").suppress()
        addop = plus | minus
        multop = mult | div
        expop = pyparsing.Literal("^")
        pi = pyparsing.CaselessLiteral("PI")
        expr = pyparsing.Forward()
        atom = (
            (
                pyparsing.Optional(pyparsing.oneOf("- +"))
                + (pi | e | fnumber | ident + lpar + expr + rpar).setParseAction(
                    self.pushFirst
                )
            )
            | pyparsing.Optional(pyparsing.oneOf("- +"))
            + pyparsing.Group(lpar + expr + rpar)
        ).setParseAction(self.pushUMinus)
        # by defining exponentiation as "atom [ ^ factor ]..." instead of
        # "atom [ ^ atom ]...", we get right-to-left exponents, instead of left-to-right
        # that is, 2^3^2 = 2^(3^2), not (2^3)^2.
        factor = pyparsing.Forward()
        factor << atom + pyparsing.ZeroOrMore(
            (expop + factor).setParseAction(self.pushFirst)
        )
        term = factor + pyparsing.ZeroOrMore(
            (multop + factor).setParseAction(self.pushFirst)
        )
        expr << term + pyparsing.ZeroOrMore(
            (addop + term).setParseAction(self.pushFirst)
        )
        # addop_term = ( addop + term ).setParseAction( self.pushFirst )
        # general_term = term + ZeroOrMore( addop_term ) | OneOrMore( addop_term)
        # expr <<  general_term
        self.bnf = expr
        # map operator symbols to corresponding arithmetic operations
        epsilon = 1e-12
        self.opn = {
            "+": operator.add,
            "-": operator.sub,
            "x": operator.mul,
            "/": operator.truediv,
            "^": operator.pow,
        }
        self.fn = {
            "sqrt": math.sqrt,
            "log": math.log,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "arcsin": math.asin,
            "arccos": math.acos,
            "arctan": math.atan,
            "sinh": math.sinh,
            "cosh": math.cosh,
            "tanh": math.tanh,
            "arcsinh": math.asinh,
            "arccosh": math.acosh,
            "arctanh": math.atanh,
            "abs": abs,
            "trunc": lambda a: int(a),
            "round": round,
            "sgn": lambda a: abs(a) > epsilon and cmp_to_key(a, 0) or 0,
        }

    def evaluateStack(self, s):
        op = s.pop()
        if op == "unary -":
            return -self.evaluateStack(s)
        if op in "+-x/^":
            op2 = self.evaluateStack(s)
            op1 = self.evaluateStack(s)
            return self.opn[op](op1, op2)
        elif op == "PI":
            return math.pi  # 3.1415926535
        elif op == "E":
            return math.e  # 2.718281828
        elif op in self.fn:
            return self.fn[op](self.evaluateStack(s))
        elif op[0].isalpha():
            return 0
        else:
            return float(op)

    def eval(self, num_string, parseAll=True):
        self.exprStack = []
        results = self.bnf.parseString(num_string, parseAll)
        val = self.evaluateStack(self.exprStack[:])
        return val