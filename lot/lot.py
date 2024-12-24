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
    a, s = parse_angles(s)
    if s:
        error(f"Error, incomplete parsing: {s[:16]}")
    return d, a  # (domain, angles)


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


def parse_angles(s):
    def unit(s):
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
        error(f"Error, failed to parse angles: {s[:16]}")


def parse_o(s):
    try:
        _, s = token(char("-"))(s)
        a, s = token(oneof("oO"))(s)
        r, s = parse_list(s)
        return (a.lower(), r), s
    except:
        error(f"Error, failed to parse 'O': {s[:16]}")


def parse_x(s):
    try:
        _, s = token(char("-"))(s)
        a, s = token(oneof("xX"))(s)
        r, s = parse_list(s)
        return (a.lower(), r), s
    except:
        error(f"Error, failed to parse 'X': {s[:16]}")


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
    return sort_(grid), vmap


def from_angles(angles):
    policy = []
    constraints = []
    for k, v in angles:
        if k == "*":
            policy.extend(v)
        else:
            constraints.append((k, v))
    return constraints, policy


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
    cmap = {}
    for v, conds in constraints:
        for action, cond in conds:
            if action == "o":
                for g in grid:
                    if not any(in_grid(item, g) for item in cond):
                        o = vmap[v][g]
                        cmap[o.decl().name()] = o == False  # noqa
            elif action == "x":
                for item in cond:
                    for g in grid:
                        if in_grid(item, g):
                            o = vmap[v][g]
                            cmap[o.decl().name()] = o == False  # noqa
            elif action == "v":
                item, op, val = cond
                check = in_grid
                if item.startswith("!"):
                    item = item[1:]
                    check = cf_(not_, in_grid)
                lhs = Sum([If(vmap[v][g], 1, 0) for g in grid if check(item, g)])
                cmap[lhs.hash()] = expr(op, lhs, int(val))
    return list(cmap.values())


def ensure_nodup_populated(grid, vmap):
    return [Sum([If(vmap[v][g], 1, 0) for v in vmap]) == 1 for g in grid]


def ensure_nodup_root(grid, vmap):
    root = set(g.split("_")[0] for g in grid)
    return [
        AtMost(*[vmap[v][g] for g in grid if in_grid(r, g)], 1)
        for v in vmap
        for r in root
    ]


def ensure_group_policy(policy, grid, vmap):
    o = []
    for v in vmap:
        for p in policy:
            item, op, val = cond
            check = in_grid
            if item.startswith("!"):
                item = item[1:]
                check = cf_(not_, in_grid)
            lhs = Sum([If(vmap[v][g], 1, 0) for g in grid if check(item, g)])
    o.append(And(expr(op, lhs, int(val))))
    return o
    return [
        And(
            AtLeast(*[vmap[v][g] for g in grid], 1),
            Sum(
                [
                    If(in_grid("평일10시", g), 0.5, 1) * If(vmap[v][g], 1, 0)
                    for g in grid
                ]
            )
            <= 3,
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


def res_by_var(model, grid, vmap):
    return {v: sort_([g for g in grid if model.eval(vmap[v][g])]) for v in vmap}


def res_by_domain(model, grid, vmap):
    return sort_({g: fst(v for v in vmap if model.eval(vmap[v][g])) for g in grid})


def solve(f):
    domain, (constraints, policy) = second(from_angles, parse_lot(f))
    grid, vmap = prepare(domain, constraints)

    opt = Optimize()
    opt.add(shuffle(assertions(constraints, grid, vmap)))
    opt.add(shuffle(ensure_nodup_populated(grid, vmap)))

    opt.add(shuffle(ensure_group_policy(policy, grid, vmap)))
    opt.add(shuffle(ensure_nodup_root(grid, vmap)))
    if opt.check() == sat:
        model = opt.model()
        return dmap(
            d=res_by_domain(model, grid, vmap),
            v=res_by_var(model, grid, vmap),
        )
    else:
        error("Error, No solution found")
