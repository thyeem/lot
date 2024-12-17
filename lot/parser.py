from foc import *


def many(parser):
    def go(s):
        o = []
        while True:
            try:
                r, s = parser(s)
                o.append(r)
            except:
                break
        return o, s

    return go


def some(parser):
    def go(s):
        r, s = many(parser)(s)
        if not r:
            error("Error, expected at least one successful parse.")
        return r, s

    return go


def between(bra, ket, parser):
    def parse(s):
        _, s = bra(s)
        r, s = parser(s)
        _, s = ket(s)
        return unchars(r), s

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


def anychar():
    """
    >>> anychar()("sofia")
    ('s', 'ofia')
    """
    return charby(const(True), expect="anycharacter")


def anycharbut(c):
    """
    >>> anycharbut("s")("maria")
    ('m', 'aria')
    """
    return charby(_ != c, expect=f"any character but {c}")


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


def anystring():
    """
    >>> anystring()("sofiamaria")
    ('sofiamaria', '')
    """

    def parse(s):
        r, s = many(anychar())(s)
        return unchars(r), s

    return parse


def anystringbut(cs):
    def parse(s):
        o = []
        while not s.startswith(cs):
            r, s = anycharbut(cs[0])(s)
            o.append(r)
        return unchars(o), s

    return parse
