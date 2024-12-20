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


def prepare(domain, constraints):
    grid = ["_".join(x) for x in concat([cartprod(*x) for x in domain])]
    ugrid = {u: {g: Bool(f"{u}_{g}") for g in grid} for u, _ in constraints}
    return grid, ugrid


# def init_solver(solver, ug):
# for u in ug:
# for grid in ug[u]:
# solver.add(Not(ug[u][grid]))


def in_grid(item, g):
    return item in g.split("_")


def set_constraints(solver, constraints, grid, ugrid):
    for u, c in constraints:
        if not c:
            continue
        for action, o in c:
            if action == "o":
                for item in o:
                    for g in grid:
                        if in_grid(item, g):
                            solver.add(ugrid[u][g] == True)  # noqa
            elif action == "x":
                for item in o:
                    for g in grid:
                        if in_grid(item, g):
                            solver.add(ugrid[u][g] == False)  # noqa
            elif action == "v":
                item, op_, val = o
                op_ = (
                    op.lt
                    if op_ == "<"
                    else (
                        op.gt
                        if op_ == ">"
                        else (
                            op.eq
                            if op_ == "="
                            else error(f"Error, not supported such operator: {op_}")
                        )
                    )
                )
                # TODO: check item is in grid
                solver.add(
                    op_(
                        Sum([If(ugrid[u][g], 1, 0) for u in ugrid if in_grid(item, g)]),
                        int(val),
                    )
                )
            else:
                error(f"Error, no such action: {action}")


def nodup_completep(solver, grid, ugrid):
    for g in grid:
        solver.add(Sum([If(ugrid[u][g], 1, 0) for u in ugrid]) == 1)


def solve(f):
    domain, constraints = parse_lot(f)
    grid, ugrid = prepare(domain, constraints)

    solver = Solver()
    # init_solver(solver, ug)
