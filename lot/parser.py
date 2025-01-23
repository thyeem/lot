from foc import *


def many(parser, fold=False):
    def go(s):
        o = []
        while True:
            try:
                r, s = parser(s)
                o.append(r)
            except:
                break
        return (unchars(o) if fold else o, s)

    return go


def some(parser, fold=False):
    def go(s):
        r, s = many(parser, fold=fold)(s)
        if not r:
            error("Error, expected at least one successful parse.")
        return r, s

    return go


def between(bra, ket, parser):
    def parse(s):
        _, s = bra(s)
        r, s = parser(s)
        _, s = ket(s)
        return r, s

    return parse


def choice(*parsers):
    def parse(s):
        for parser in parsers:
            try:
                return parser(s)
            except:
                pass
        error("Error, no parser succeeded.")

    return parse


def option(default, parser):
    def parse(s):
        try:
            return parser(s)
        except:
            return default, s

    return parse


def sepby(sep, parser):
    def parse(s):
        o = []
        r, s = parser(s)
        o.append(r)

        def rest(s):
            _, s = sep(s)
            return parser(s)

        r, s = many(rest)(s)
        o.extend(r)
        return o, s

    return parse


def charby(p, expect):
    def parse(s):
        if not s:
            error("Error, nothing to parse.")
        if p(s[0]):
            return s[0], s[1:]
        error(f"Error, expected '{expect}', but got '{s[0]}'.")

    return parse


def char(c):
    """
    >>> char("s")("sofia")
    ('s', 'ofia')
    """
    return charby(_ == c, expect=c)


def anychar(s):
    """
    >>> anychar("sofia")
    ('s', 'ofia')
    """
    return charby(const(True), expect="anycharacter")(s)


def anycharbut(c):
    """
    >>> anycharbut("s")("maria")
    ('m', 'aria')
    """
    return charby(_ != c, expect=f"any character but {c}")


def oneof(cs):
    return charby(lambda x: x in cs, expect=f"one of {cs}")


def noneof(cs):
    return charby(lambda x: x not in cs, expect=f"none of {cs}")


def digit(s):
    return oneof("0123456789")(s)


def digits(s):
    return some(digit, fold=True)(s)


def string(cs):
    """
    >>> string("maria")("mariasofia")
    ('maria', 'sofia')
    """

    def parse(s):
        o = []
        for c in cs:
            r, s = char(c)(s)
            o.append(r)
        return unchars(o), s

    return parse


def anystring(s):
    """
    >>> anystring("sofiamaria")
    ('sofiamaria', '')
    """
    return many(anychar, fold=True)(s)


def anystringbut(cs):
    def parse(s):
        o = []
        while s and not s.startswith(cs):
            r, s = anychar(s)
            o.append(r)
        return unchars(o), s

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
    return choice(char(" "), char("\n"), char("\t"))(s)


def comment(s):
    _, s = char("#")(s)
    r, s = anystringbut("\n")(s)
    return r, s


def jump(s):
    _, s = many(choice(whitespace, comment), fold=True)(s)
    return None, s


def token(parser):
    def parse(s):
        r, s = parser(s)
        _, s = jump(s)
        return r, s

    return parse
