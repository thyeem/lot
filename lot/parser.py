from unicodedata import east_asian_width

from foc import *
from ouch import *


def many(parser, fold=False):
    def parse(s):
        o = []
        while s and bool(s.rest):
            try:
                r, s = parser(s)
                o.append(r)
            except ParseError as e:
                s = e.s
                break
        return (unchars(o) if fold else o, s)

    return parse


def some(parser, fold=False):
    def parse(s):
        r, s = many(parser, fold=fold)(s)
        if not r:
            fail(f"Expected '{expect(parser, '1+ successful parse')}'", s)
        return r, s

    if hasattr(parser, "expected"):
        parse.expected = f"one or more {parser.expected}"
    return parse


def between(bra, ket, parser):
    """
    >>> between(char("("),char(")"),digits)(stream("(777)"))
    ('777', '')
    """

    def parse(s):
        try:
            _, s = bra(s)
        except ParseError as e:
            fail(f"Expected '{expect(bra, 'opener')}'", e.s)
        r, s = parser(s)
        try:
            _, s = ket(s)
        except ParseError as e:
            fail(f"Expected '{expect(ket, 'closer')}'", e.s)
        return r, s

    parse.expected = f"{expect(bra, 'opener')}...{expect(ket, 'closer')}"
    return parse


def choice(*parsers):
    def parse(s):
        error = None
        line = col = -1
        for parser in parsers:
            try:
                return parser(s)
            except ParseError as e:
                if e.s.line > line or (e.s.line == line and e.s.col > col):
                    line, col = e.s.line, e.s.col
                    error = e
        raise error

    return parse


def option(default, parser):
    """
    >>> option('7', digits)(stream("seven"))
    ('7', 'seven')
    """

    def parse(s):
        try:
            return parser(s)
        except ParseError as e:
            return default, e.s

    return parse


def count(n, parser):
    """
    >>> count(3, char("f"))(stream("ffffff"))
    (['f', 'f', 'f'], 'fff')
    """

    def parse(s):
        o = []
        for _ in range(n):
            try:
                r, s = parser(s)
                o.append(r)
            except ParseError as e:
                fail(
                    f"Expected exactly {n} {expect(parser,'occurrences')}",
                    e.s,
                    expected=e.expected,
                    got=e.got,
                )
        return o, s

    return parse


def atleast(n, parser):
    """
    >>> atleast(3, char("f"))(stream("ffffff"))
    (['f', 'f', 'f', 'f', 'f', 'f'], '')
    """

    def parse(s):
        try:
            o, s = count(n, parser)(s)
            q, s = many(parser)(s)
            o.extend(q)
            return o, s
        except ParseError as e:
            fail(
                f"Expected atleast {n} {expect(parser,'occurrences')}",
                e.s,
                expected=e.expected,
                got=e.got,
            )

    return parse


def atmost(n, parser):
    """
    >>> atmost(3, char("f"))(stream("ff"))
    (['f', 'f'], '')
    """

    def parse(s):
        o = []
        for _ in range(n):
            try:
                r, s = parser(s)
                o.append(r)
            except ParseError:
                break
        return o, s

    return parse


def sepby(sep, parser):
    """
    >>> sepby(char(","), digits)(stream("1,2,3"))
    (['1', '2', '3'], '')
    """

    def parse(s):
        o = []
        try:
            r, s = parser(s)
            o.append(r)
        except ParseError as e:
            fail(
                f"Expected '{expect(parser, 'element')}'",
                e.s,
                expected=e.expected,
                got=e.got,
            )

        def rest(s):
            try:
                _, s = sep(s)
                return parser(s)
            except ParseError as e:
                raise e

        r, s = many(rest)(s)
        o.extend(r)
        return o, s

    return parse


def charby(p, expected):
    def parse(s):
        if not s:
            fail("Reached end-of-stream", s, expected=expected, got="end-of-stream")
        if p(s[0]):
            return s[0], s.update(s[0])
        fail("Unexpected char", s, expected=expected, got=s[0])

    parse.expected = expected
    return parse


def char(c):
    """
    >>> char("s")(stream("sofia"))
    ('s', 'ofia')
    """
    parser = charby(_ == c, expected=c)
    parser.expected = c
    return parser


def anychar(s):
    """
    >>> anychar(stream("maria"))
    ('m', 'aria')
    """
    return charby(const(True), expected="any character")(s)


def oneof(cs):
    """
    >>> oneof("coffee")(stream("claire"))
    ('c', 'laire')
    """
    expected = f"one of {cs}"
    parser = charby(lambda x: x in cs, expected=expected)
    parser.expected = expected
    return parser


def noneof(cs):
    """
    >>> noneof("12345")(stream("012345"))
    ('0', '12345')
    """
    expected = f"none of {cs}"
    parser = charby(lambda x: x not in cs, expected=expected)
    parser.expected = expected
    return parser


def anycharbut(c):
    """
    >>> anycharbut("s")(stream("maria"))
    ('m', 'aria')
    """
    expected = f"any character but {c}"
    parser = charby(_ != c, expected=expected)
    parser.expected = expected
    return parser


def digit(s):
    """
    >>> digit(stream("2010"))
    ('2', '010')
    """
    return oneof("0123456789")(s)


def digits(s):
    """
    >>> digits(stream("2010SEP"))
    ('2010', 'SEP')
    """
    return some(digit, fold=True)(s)


def string(cs):
    """
    >>> string("ave-")(stream("ave-maria"))
    ('ave-', 'maria')
    """

    def parse(s):
        for i, c in enumerate(cs):
            if s[0] != c:
                fail(
                    "Unexpected string",
                    s,
                    expected=f"'{cs}'",
                    got=f"'{s.rest[:i]}{s[0]}...'",
                )
            s = s.update(c)
        return cs, s

    parse.expected = cs
    return parse


def anystring(s):
    """
    >>> anystring(stream("sofiamaria"))
    ('sofiamaria', '')
    """
    return many(anychar, fold=True)(s)


def anystringbut(cs):
    """
    >>> anystringbut(".")(stream("-273.15"))
    ('-273', '.15')
    """

    def parse(s):
        o = []
        while s and not s.rest.startswith(cs):
            c, s = anychar(s)
            o.append(c)
        return unchars(o), s

    parse.expected = f"any string but {cs}"
    return parse


def parens(parser):
    return between(
        token(string("(")),
        token(string(")")),
        parser,
    )


def squares(parser):
    return between(
        token(string("[")),
        token(string("]")),
        parser,
    )


def braces(parser):
    return between(
        token(string("{")),
        token(string("}")),
        parser,
    )


def angles(parser):
    return between(
        token(string("<")),
        token(string(">")),
        parser,
    )


def whitespace(s):
    parser = choice(char(" "), char("\n"), char("\t"))
    parser.expected = "whitespace"
    return parser(s)


def comment(s):
    def parse(s):
        _, s = char("#")(s)
        r, s = anystringbut("\n")(s)
        return r, s

    parse.expected = "comment"
    return parse(s)


def jump(s):
    _, s = many(choice(whitespace, comment), fold=True)(s)
    return None, s


def token(parser):
    def parse(s):
        r, s = parser(s)
        _, s = many(whitespace)(s)
        return r, s

    if hasattr(parser, "expected"):
        parse.expected = parser.expected
    return parse


def expect(parser, fallback):
    return getattr(parser, "expected", fallback)


def escape(s):
    return s.replace("\n", "\\n").replace("\r", "\\r").replace("\t", "\\t")


class stream:
    def __init__(self, s, rest=None, line=1, col=1):
        self.orig = s
        self.line = line
        self.col = col
        self.rest = rest if rest is not None else s

    def update(self, c):
        if c == "\n":
            return stream(self.orig, self.rest[1:], self.line + 1, 1)
        if c == "\t":
            return stream(self.orig, self.rest[1:], self.line, self.col + 4)
        else:
            return stream(self.orig, self.rest[1:], self.line, self.col + 1)

    def __bool__(self):
        return bool(self.rest)

    def __getitem__(self, index):
        return self.rest[index]

    def __len__(self):
        return len(self.rest)

    def __repr__(self):
        return repr(self.rest)


class ParseError(Exception):
    def __init__(self, msg, s, expected=None, got=None):
        self.msg = msg
        self.s = s
        self.expected = expected and escape(expected)
        self.got = got and escape(got)
        super().__init__(self.format_error())

    def format_error(self):
        lines = self.s.orig.split("\n")
        j = self.s.line - 1
        num = str(j + 1)

        if j < len(lines):
            col = sum(
                2 if east_asian_width(c) in {"W", "F"} else 1
                for c in lines[j][: self.s.col - 1]
            )
        else:
            col = 0
        errors = [f"Parse error at line {j + 1}, column {self.s.col}:"]
        errors.append("")
        errors.append(f"{num:>4} | {lines[j] if j < len(lines) else ''}")
        errors.append(f"{' ':>4} | {' ' * col}^")

        for k in seq(1, 4):
            if j + k < len(lines):
                errors.append(f"{j + k + 1:>4} | {lines[j + k]}")

        errors.append("")
        errors.append(self.msg)  # reason
        if self.expected is not None and self.got is not None:
            errors.append(f"Expected '{self.expected}' but got '{self.got}'")
        errors.append("")
        return unlines(errors)


def fail(msg, stream, expected=None, got=None):
    raise ParseError(msg, stream, expected=expected, got=got)


def run_parser(parser, s):
    s = stream(reader(s).read() if exists(s) else s)
    try:
        r, s = parser(s)
        if s:
            fail("Incomplete parse", s)
        return r
    except ParseError as e:
        print(e)
        return
