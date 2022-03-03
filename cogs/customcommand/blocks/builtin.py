import TagScriptEngine as tse
from .delete import DeleteBlock
from .silent import SilentBlock

blocks = [
            tse.MathBlock(),
            tse.RandomBlock(),
            tse.RangeBlock(),
            tse.AnyBlock(),
            tse.IfBlock(),
            tse.AllBlock(),
            tse.BreakBlock(),
            tse.StrfBlock(),
            tse.StopBlock(),
            tse.AssignmentBlock(),
            tse.FiftyFiftyBlock(),
            tse.ShortCutRedirectBlock("args"),
            tse.LooseVariableGetterBlock(),
            tse.SubstringBlock(),
            tse.EmbedBlock(),
            tse.ReplaceBlock(),
            tse.PythonBlock(),
            tse.URLEncodeBlock(),
            tse.RequireBlock(),
            tse.BlacklistBlock(),
            tse.CommandBlock(),
            tse.OverrideBlock(),
            tse.RedirectBlock(),
            tse.CooldownBlock(),
            DeleteBlock(),
            SilentBlock()
]