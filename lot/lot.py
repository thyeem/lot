from foc import *
from ouch import dmap, reader, shuffle
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
        v, s = token(
            between(
                token(string("<")),
                token(string(">")),
                token(some(noneof("<>"), fold=True)),
            )
        )(s)
        r, s = many(choice(parse_o, parse_x, parse_cond))(s)
        return (v, r), s

    try:
        return some(unit)(s)
    except:
        error(f"Error, failed to parse constraints: {s[:16]}")


def parse_o(s):
    try:
        _, s = token(char("-"))(s)
        a, s = token(oneof("oO"))(s)
        r, s = parse_list(s)
        return (a.lower(), r), s
    except:
        error(f"Error, failed to parse constraint 'O': {s[:16]}")


def parse_x(s):
    try:
        _, s = token(char("-"))(s)
        a, s = token(oneof("xX"))(s)
        r, s = parse_list(s)
        return (a.lower(), r), s
    except:
        error(f"Error, failed to parse constraint 'X': {s[:16]}")


def parse_cond(s):
    try:
        o = []
        _, s = token(char("-"))(s)
        r, s = token(some(noneof(">=< \n\t"), fold=True))(s)
        o.append(r)
        r, s = token(
            choice(
                string("<="),
                string(">="),
                string("<"),
                string(">"),
                string("="),
            )
        )(s)
        o.append(r)
        r, s = token(digits())(s)
        o.append(r)
        return ("v", o), s
    except:
        error(f"Error, failed to cond-var: {s[:16]}")


def prepare(domain, constraints):
    grid = ["_".join(x) for x in concat([cartprod(*x) for x in domain])]
    vmap = {v: {g: Bool(f"{v}_{g}") for g in grid} for v, _ in constraints}
    return grid, vmap


def in_grid(item, g):
    return item in g.split("_")


def expr(op, lhs, rhs):
    f = {
        "<": lambda x, y: x < y,
        "<=": lambda x, y: x <= y,
        ">": lambda x, y: x > y,
        ">=": lambda x, y: x >= y,
        "=": lambda x, y: x == y,
    }.get(op) or error(f"Error, not supported such operator: {op}")

    return f(lhs, rhs)


def assertions(constraints, grid, vmap):
    cmap = []
    for v, conds in constraints:
        for action, cond in conds:
            if action == "o":
                cmap.extend(
                    [
                        vmap[v][g] == False  # noqa
                        for g in grid
                        if not any(in_grid(item, g) for item in cond)
                    ]
                )
            elif action == "x":
                cmap.extend(
                    [
                        vmap[v][g] == False  # noqa
                        for item in cond
                        for g in grid
                        if in_grid(item, g)
                    ]
                )
            elif action == "v":
                item, op, val = cond
                lhs = Sum([If(vmap[v][g], 1, 0) for g in grid if in_grid(item, g)])
                cmap.append(expr(op, lhs, float(val)))
    return cmap


def ensure_nodup_domain(grid, vmap):
    return [Sum([If(vmap[v][g], 1, 0) for v in vmap]) == 1 for g in grid]


def ensure_nodup_root(grid, vmap):
    root = set(g.split("_")[0] for g in grid)
    return [
        AtMost(*[vmap[v][g] for g in grid if in_grid(r, g)], 1)
        for v in vmap
        for r in root
    ]


def ensure_var_occurrence(grid, vmap):
    return [
        And(
            AtLeast(*[vmap[v][g] for g in grid], 1),
            Sum(
                [
                    If(in_grid("평일10시", g), 0.3, 0.6) * If(vmap[v][g], 1, 0)
                    for g in grid
                ]
            )
            <= 2,
        )
        for v in vmap
    ]


def sort_(x):
    def extract(key):
        x = key.split("_")[0]
        return int(x) if x.isdigit() else x

    if isinstance(x, dict):
        return dict(sorted(x.items(), key=lambda x: extract(x[0])))
    elif isinstance(x, list):
        return sorted(x, key=extract)
    else:
        return x


def solve(f):
    domain, constraints = parse_lot(f)
    grid, vmap = prepare(domain, constraints)

    opt = Optimize()
    opt.add(shuffle(assertions(constraints, grid, vmap)))
    opt.add(shuffle(ensure_var_occurrence(grid, vmap)))
    opt.add(shuffle(ensure_nodup_domain(grid, vmap)))
    opt.add(shuffle(ensure_nodup_root(grid, vmap)))
    if opt.check() == sat:
        model = opt.model()
        return dmap(
            d=sort_(
                {g: next(v for v in vmap if model.eval(vmap[v][g])) for g in grid},
            ),
            v={v: sort_([g for g in grid if model.eval(vmap[v][g])]) for v in vmap},
        )
    else:
        error("Error, No solution found")
