from foc import *
from ouch import reader
from z3 import *

from .parser import *


def read_lot(f):
    return snd(jump()(reader(f).read()))


def parse_lot(f):
    s = read_lot(f)
    d, s = parse_domain(s)
    _, s = parse_bar(s)
    c, s = parse_constraint(s)
    if s:
        error(f"Error, incomplete parsing: {s[:16]}")
    return d, c  # (domains, constraints)


def parse_domain(s):
    return sepby(token(string("+")), many(parse_list))(s)


def parse_list(s):
    return token(
        between(
            token(string("[")),
            token(string("]")),
            sepby(
                token(char(",")),
                token(some(noneof(",[]_+ \n\t"), fold=True)),
            ),
        )
    )(s)


def parse_bar(s):
    try:
        _, s = char("-")(s)
        _, s = char("-")(s)
        _, s = some(char("-"))(s)
        _, s = jump()(s)
        return None, s
    except:
        error(f"Error, failed to parse bar: {s[:16]}")


def parse_constraint(s):
    def unit(s):
        o = []
        u, s = token(
            between(
                token(string("<")),
                token(string(">")),
                token(some(noneof("<>"), fold=True)),
            )
        )(s)
        r, s = many(choice(parse_o, parse_x, parse_cond))(s)
        return (u, r), s

    try:
        return some(unit)(s)
    except:
        error(f"Error, failed to parse constraints: {s[:16]}")


def parse_o(s):
    try:
        _, s = token(char("-"))(s)
        _, s = token(oneof("oO"))(s)
        r, s = parse_list(s)
        return ("o", r), s
    except:
        error(f"Error, failed to parse constraint 'O': {s[:16]}")


def parse_x(s):
    try:
        _, s = token(char("-"))(s)
        _, s = token(oneof("xX"))(s)
        r, s = parse_list(s)
        return ("x", r), s
    except:
        error(f"Error, failed to parse constraint 'X': {s[:16]}")


def parse_cond(s):
    try:
        o = []
        _, s = token(char("-"))(s)
        r, s = token(some(noneof(">=< \n\t"), fold=True))(s)
        o.append(r)
        r, s = token(oneof(">=<"))(s)
        o.append(r)
        r, s = token(digits())(s)
        o.append(r)
        return ("v", o), s
    except:
        error(f"Error, failed to cond-var: {s[:16]}")


def prepare(d, c):
    o = ["_".join(x) for x in concat([cartprod(*x) for x in d])]
    u = {k: {x: Bool(x) for x in o} for k, _ in c}
    return o, u


def solve():
    pass
