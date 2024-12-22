from foc import *
from ouch import dmap, randint, reader, shuffle
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
        r, s = token(
            choice(
                string("<"),
                string("<="),
                string(">"),
                string(">="),
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
    if op == "<":
        return lhs < rhs
    elif op == "<=":
        return lhs <= rhs
    elif op == ">":
        return lhs > rhs
    elif op == ">=":
        return lhs >= rhs
    elif op == "=":
        return lhs == rhs
    else:
        error(f"Error, not supported such operator: {op}")


def z3_constraints(constraints, grid, vmap):
    cmap = dict()

    def set_grid(x, when):
        for g in grid:
            cond = not in_grid(x, g) if when else in_grid(x, g)
            if cond:
                o = vmap[v][g]
                cmap[o.decl().name()] = o == False  # noqa

    for v, conds in constraints:
        for action, cond in conds:
            if action == "o":
                for item in cond:
                    set_grid(item, True)

            elif action == "x":
                for item in cond:
                    set_grid(item, False)

            elif action == "v":
                item, op, val = cond
                e = expr(
                    op,
                    Sum(
                        [If(vmap[v][g], 1, 0) for g in grid if in_grid(item, g)],
                    ),
                    int(val),
                )
                cmap[e.decl().name()] = e
            else:
                error(f"Error, no such action: {action}")
    return cmap


def ensure_domain_nodup(solver, grid, vmap):
    for g in grid:
        solver.add(Sum([If(vmap[v][g], 1, 0) for v in vmap]) == 1)


def ensure_var_occurrence(solver, grid, vmap):
    for v in vmap:
        solver.add(Sum([If(vmap[v][g], 1, 0) for g in grid]) >= 1)
        solver.add(Sum([If(vmap[v][g], 1, 0) for g in grid]) <= 2)


def by_domain(model, grid, vmap):
    o = dict()
    for g in grid:
        var = [v for v in vmap if model.eval(vmap[v][g])]
        guard(len(var) == 1, f"Error, variable not narrowed down to one: {var}")
        o[g] = var
    return o


def by_var(model, grid, vmap):
    o = dict()
    for v in vmap:
        assigned = [g for g in grid if model.eval(vmap[v][g])]
        o[v] = assigned
    return o


def solve(f):
    domain, constraints = parse_lot(f)
    grid, vmap = prepare(domain, constraints)
    cmap = z3_constraints(constraints, grid, vmap)

    solver = Solver()
    for assertion in shuffle(list(cmap.values())):
        solver.add(assertion)
    ensure_var_occurrence(solver, grid, vmap)
    ensure_domain_nodup(solver, grid, vmap)

    solver.set("random_seed", randint(1 << 64))
    if solver.check() == unsat:
        # error("Error, found no solution satisfying the given constraints.")
        print("Error, found no solution satisfying the given constraints.")
        return solver
    model = solver.model()
    return dmap(
        model=model,
        d=by_domain(model, grid, vmap),
        v=by_var(model, grid, vmap),
    )
