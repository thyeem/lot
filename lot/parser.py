from unicodedata import east_asian_width

from foc import *
from ouch import *


def cast(f):
    def go(s, *args, **kwargs):
        return f(state(s) if isinstance(s, str) else s, *args, **kwargs)

    return go


def many(p, fold=False):
    @cast
    def parse(s):
        o = []
        while s:
            try:
                r, s = p(s)
                o.append(r)
            except ParseError as e:
                if e.s > s:
                    raise e
                break
        return unchars(o) if fold else o, s

    return parse


def some(p, fold=False):
    @cast
    def parse(s):
        r, s = p(s)
        m, s = many(p)(s)
        o = cons(r, m)
        return unchars(o) if fold else o, s

    return parse


def choice(*ps):
    """
    >>> choice(char("f"), digit)("777")
    ('7', '77')
    """

    @cast
    def parse(s):
        error = None
        for p in ps:
            try:
                return p(s)
            except ParseError as e:
                if not error or e.s > error.s:
                    error = e
                pass
        raise error

    return parse


def option(default, p):
    """
    >>> option('7', digits)("seven")
    ('7', 'seven')
    """

    @cast
    def parse(s):
        try:
            return p(s)
        except ParseError as e:
            return default, e.s

    return parse


def count(n, p):
    """
    >>> count(3, char("f"))("ffffff")
    (['f', 'f', 'f'], 'fff')
    """

    @cast
    def parse(s):
        o = []
        for _ in range(n):
            r, s = p(s)
            o.append(r)
        return o, s

    return parse


def atleast(n, p):
    """
    >>> atleast(3, char("f"))("ffffff")
    (['f', 'f', 'f', 'f', 'f', 'f'], '')
    """

    @cast
    def parse(s):
        o, s = count(n, p)(s)
        q, s = many(p)(s)
        o.extend(q)
        return o, s

    return parse


def atmost(n, p):
    """
    >>> atmost(3, char("f"))("ff")
    (['f', 'f'], '')
    """

    def parse(s):
        o = []
        for _ in range(n):
            try:
                r, s = p(s)
                o.append(r)
            except ParseError:
                break
        return o, s

    return parse


def between(bra, ket, p):
    """
    >>> between(char("("),char(")"),digits)("(777)")
    ('777', '')
    """

    @cast
    def parse(s):
        _, s = bra(s)
        r, s = p(s)
        _, s = ket(s)
        return r, s

    return parse


def sepby(sep, p):
    """
    >>> sepby(char(","), digits)("1,2,3")
    (['1', '2', '3'], '')
    """

    def go(s):
        _, s = sep(s)
        r, s = p(s)
        return r, s

    @cast
    def parse(s):
        o = []
        r, s = p(s)
        o.append(r)
        r, s = many(go)(s)
        if r:
            o.extend(r)
        return o, s

    return parse


def endby(end, p):
    """
    >>> endby(char(","), digits)("1,2,3,")
    (['1', '2', '3'], '')
    """

    def go(s):
        r, s = p(s)
        _, s = end(s)
        return r, s

    @cast
    def parse(s):
        return some(go)(s)

    return parse


def manytill(end, p, fold=False):
    """
    >>> manytill(char(";"), anychar)(";bleu;rosso")
    ([], 'bleu;rosso')
    >>> manytill(char(";"), anychar, fold=True)("bleu;rosso")
    ('bleu', 'rosso')
    """

    @cast
    def parse(s):
        try:
            return sometill(end, p, fold=fold)(s)
        except ParseError:
            _, s = end(s)
            return [], s

    return parse


def sometill(end, p, fold=False):
    """
    >>> sometill(char("."), digit)("3.141592")
    (['3'], '141592')
    """

    @cast
    def parse(s):
        o = []
        while True:
            try:
                r, s = end(s)
                break
            except ParseError:
                r, s = p(s)
                o.append(r)
        return unchars(o) if fold else o, s

    return parse


def skip(p):
    """
    >>> skip(char("s"))("sofia")
    (None, 'ofia')
    """

    @cast
    def parse(s):
        _, s = p(s)
        return None, s

    return parse


def skipmany(p):
    """
    >>> skipmany(char("s"))("sssssofia")
    (None, 'ofia')
    """
    return skip(many(p))


def skipsome(p):
    """
    >>> skipsome(char("m"))("mmmmmaria")
    (None, 'aria')
    """
    return skip(some(p))


def peek(p):
    @cast
    def parse(s):
        try:
            _, _ = p(s)
            return True, s
        except ParseError as e:
            raise e

    return parse


@fx
def label(expected, p):
    @cast
    def parse(s):
        try:
            return p(s)
        except ParseError as e:
            fail("", e.s, expected=expected)

    return parse


def charby(predicate):
    @cast
    def parse(s):
        if not s:
            fail("Reached end-of-stream", s.get("EOF"))
        if predicate(s[0]):
            return s[0], s.update(s[0])
        fail("Unexpected char", s.get(s[0]))

    return parse


def char(c):
    """
    >>> char("s")("sofia")
    ('s', 'ofia')
    """
    return label(f"'{c}'", charby(_ == c))


@cast
def anychar(s):
    """
    >>> anychar("maria")
    ('m', 'aria')
    """
    return label("'any character'", charby(const(True)))(s)


def anycharbut(c):
    """
    >>> anycharbut("s")("maria")
    ('m', 'aria')
    """
    return label(f"any character but '{c}'", charby(_ != c))


def oneof(cs):
    """
    >>> oneof("coffee")("claire")
    ('c', 'laire')
    """
    return label(f"one of {list(cs)}", charby(lambda x: x in cs))


def noneof(cs):
    """
    >>> noneof("12345")("012345")
    ('0', '12345')
    """
    return label(f"none of {list(cs)}", charby(lambda x: x not in cs))


def digit(s):
    """
    >>> digit("2010")
    ('2', '010')
    """
    return label("'digit'", oneof("0123456789"))(s)


def digits(s):
    """
    >>> digits("2010SEP")
    ('2010', 'SEP')
    """
    return some(digit, fold=True)(s)


def integer(s):
    """
    >>> integer("-273.15")
    ('-273', '.15')
    """
    q, s = option("", char("-"))(s)
    _, _ = peek(digit)(s)
    _, _ = peek(anycharbut("0"))(s)
    i, s = digits(s)
    return q + i, s


def floating(s):
    """
    >>> floating("-273.15")
    ('-273.15', '')
    """
    q, s = option("", char("-"))(s)
    if q:
        peek(digit)(s)
    i, s = option("", digits)(s)
    p, s = char(".")(s)
    d, s = digits(s)
    return q + i + p + d, s


def number(s):
    """
    >>> number(".125")
    ('.125', '')
    """
    return choice(floating, integer)(s)


def string(cs):
    """
    >>> string("ave-")("ave-maria")
    ('ave-', 'maria')
    """

    @cast
    def parse(s):
        o = []
        for c in cs:
            r, s = char(c)(s)
            o.append(r)
        return unchars(o), s

    return parse


@cast
def anystring(s):
    """
    >>> anystring("sofiamaria")
    ('sofiamaria', '')
    """
    return many(anychar, fold=True)(s)


def anystringbut(cs):
    """
    >>> anystringbut(".")("-273.15")
    ('-273', '.15')
    """

    @cast
    def parse(s):
        o = []
        while s and not s.rest.startswith(cs):
            c, s = anychar(s)
            o.append(c)
        return unchars(o), s

    return label(f"any string but '{cs}'", parse)


@cast
def quote(s):
    """
    >>> quote("'single-quote'")
    ('single-quote', '')
    """
    return between(symbol("'"), symbol("'"), anystringbut("'"))(s)


@cast
def qquote(s):
    """
    >>> qquote('"double-quote"')
    ('double-quote', '')
    """
    return between(symbol('"'), symbol('"'), anystringbut('"'))(s)


@cast
def eof(s):
    """
    >>> eof("")
    (None, '')
    """
    if s:
        fail("Expected 'end-of-stream'", s)
    return None, s


def blank(s):
    """
    >>> blank(" NULL")
    (' ', 'NULL')
    """
    return char(" ")(s)


def tab(s):
    """
    >>> tab("\\tNULL")
    ('\\t', 'NULL')
    """
    return char("\t")(s)


def cr(s):
    """
    >>> cr("\\rNULL")
    ('\\r', 'NULL')
    """
    return char("\r")(s)


def lf(s):
    """
    >>> lf("\\nNULL")
    ('\\n', 'NULL')
    """
    return char("\n")(s)


def whitespace(s):
    """
    >>> whitespace(" LOVE")
    (' ', 'LOVE')
    """
    return label("'whitespace'", choice(blank, tab, lf))(s)


@cast
def comment(s):
    """
    >>> comment("#LOVE\\nCONQUERS ALL")
    ('LOVE', 'CONQUERS ALL')
    """
    _, s = char("#")(s)
    return manytill(choice(lf, eof), anychar, fold=True)(s)


def lexeme(consumer):
    """
    >>> lexeme(jump)(floating)("2.71828182 \\n\\t # Euler's-number")
    ('2.71828182', '')
    """

    def consume(p):
        @cast
        def parse(s):
            r, s = p(s)
            _, s = consumer(s)
            return r, s

        return parse

    return consume


def token(p):
    """
    >>> token(floating)("2.71828182 \\n\\t # Euler's-number")
    ('2.71828182', '')
    """
    return lexeme(jump)(p)


@cast
def jump(s):
    """
    >>> jump(" \\n \\t # comment\\nLOVE")
    (None, 'LOVE')
    """
    return skipmany(choice(whitespace, comment))(s)


def strip(p):
    """
    >>> strip(string("LOVE"))(" \\n \\tLOVE \\n\\t")
    ('LOVE', '')
    """
    return between(many(whitespace), many(whitespace), p)


@cast
def symbol(s):
    """
    >>> symbol("LOVE")("LOVE \\n \\t # comment")
    ('LOVE', '')
    """
    return token(string(s))


def parens(p):
    """
    >>> parens(symbol("sofia"))("( sofia )")
    ('sofia', '')
    """
    return between(symbol("("), symbol(")"), p)


def squares(p):
    """
    >>> squares(symbol("maria"))("[ maria ]")
    ('maria', '')
    """
    return between(symbol("["), symbol("]"), p)


def braces(p):
    """
    >>> braces(symbol("claire"))("{ claire }")
    ('claire', '')
    """
    return between(symbol("{"), symbol("}"), p)


def angles(p):
    """
    >>> angles(symbol("francis"))("< francis >")
    ('francis', '')
    """
    return between(symbol("<"), symbol(">"), p)


class state:
    __slots__ = ("rest", "line", "col", "buf", "got")

    def __init__(self, rest, line=1, col=1, buf=None, got=None):
        self.rest = rest
        self.line = line
        self.col = col
        self.buf = self.from_rest(3) if buf is None else buf
        self.got = got

    def update(self, c):
        if c == "\n":
            return state(self.rest[1:], self.line + 1, 1, None)
        elif c == "\t":
            return state(self.rest[1:], self.line, self.col + 4, self.buf)
        else:
            return state(self.rest[1:], self.line, self.col + 1, self.buf)

    def from_rest(self, n=1):
        return self.rest.split("\n")[:n]

    def get(self, got):
        return state(self.rest, self.line, self.col, self.buf, got=got)

    def __repr__(self):
        return repr(self.rest)

    def __bool__(self):
        return bool(self.rest)

    def __eq__(self, o):
        return self.line == o.line and self.col == o.col

    def __gt__(self, o):
        return self.line > o.line or (self.line == o.line and self.col > o.col)

    def __lt__(self, o):
        return o.__gt__(self)

    def __len__(self):
        return len(self.rest)

    def __getitem__(self, index):
        return self.rest[index]


class ParseError(Exception):
    def __init__(self, reason="", s=state(""), expected=None):
        self.reason = reason
        self.s = s
        self.expected = expected
        super().__init__(self.format_error())

    def format_error(self):
        def escape(s):
            return s if s.isprintable() else repr(s)[1:-1]

        col = (
            sum(
                2 if east_asian_width(c) in {"W", "F"} else 1
                for c in self.s.buf[0][: self.s.col - 1]
            )
            if self.s.buf[0]
            else 0
        )
        err, *context = self.s.buf
        mismatch = (
            f"Expected {escape(self.expected)} but got '{escape(self.s.got)}'"
            if self.expected is not None and self.s.got is not None
            else ""
        )
        errors = filter(
            bool,
            [
                f"Parse error at line {self.s.line}, column {self.s.col}:",
                " ",
                f"{self.s.line:>4} | {err}",
                f"{' ':>4} | {' ' * col}^",
                unlines(f"{' ':>4} | {c}" for c in context if c),
                " ",
                self.reason,
                mismatch,
                " ",
            ],
        )
        return unlines(errors)


def fail(reason, s, expected=None):
    raise ParseError(reason, s, expected=expected)


@fx
def run_parser(p, s):
    try:
        return p(s)
    except ParseError as e:
        raise e
    except Exception as e:
        raise e
