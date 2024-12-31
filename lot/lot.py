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
    nodes = ["_".join(x) for x in concat([cartprod(*x) for x in domain])]
    vmap = {v: {n: Bool(f"{v}_{n}") for n in nodes} for v, _ in constraints}
    return sort_(nodes), vmap  # (all-nodes-in-domain, Z3-var-map)


def from_angles(angles):
    policy = []
    constraints = []
    for k, v in angles:
        if k == "*":
            policy.extend(v)
        else:
            constraints.append((k, v))
    return constraints, policy


def key_in_node(key, node):
    return key in node.split("_")


def keys_in_node(keys, node):
    return set(keys).issubset(set(node.split("_")))


def nodes_with_keys(keys, nodes):
    bases = mapl(set, zip(*[n.split("_") for n in nodes]))
    o = {i: [] for i in range(len(bases))}
    for key in keys:
        for i in range(len(bases)):
            if key in bases[i]:
                o[i].append(key)
    cart = cartprodl(*filter(null | not_, o.values()))
    return {n for n in nodes if any(keys_in_node(c, n) for c in cart)}


def expr(op, lhs, rhs):
    f = {
        "<": lambda x, y: x < y,
        "<=": lambda x, y: x <= y,
        ">": lambda x, y: x > y,
        ">=": lambda x, y: x >= y,
        "=": lambda x, y: x == y,
    }.get(op) or error(f"Error, not supported such operator: {op}")

    return f(lhs, rhs)


def assertions(constraints, nodes, vmap):
    def assert_by_expr(keys, cmap, nodes, vmap):
        key, op, val = keys
        check = key_in_node
        if key.startswith("!"):
            key = key[1:]
            check = cf_(not_, key_in_node)
        lhs = Sum([If(vmap[v][n], 1, 0) for n in nodes if check(key, n)])
        cmap[str(lhs)] = expr(op, lhs, int(val))

    cmap = {}
    for v, cs in constraints:
        for action, keys in cs:
            if action == "o":
                for n in set(nodes) - nodes_with_keys(keys, nodes):
                    o = vmap[v][n]
                    cmap[o.decl().name()] = o == False  # noqa
            elif action == "x":
                for key in keys:
                    assert_by_expr((key, "=", "0"), cmap, nodes, vmap)
            elif action == "v":
                assert_by_expr(keys, cmap, nodes, vmap)
    return list(cmap.values())


def ensure_nodup_populated(nodes, vmap):
    return [Sum([If(vmap[v][n], 1, 0) for v in vmap]) == 1 for n in nodes]


def ensure_nodup_root(nodes, vmap):
    root = set(n.split("_")[0] for n in nodes)
    return [
        AtMost(*[vmap[v][n] for n in nodes if key_in_node(r, n)], 1)
        for v in vmap
        for r in root
    ]


def ensure_group_policy(policy, nodes, vmap):
    o = []
    for v in vmap:
        for _, p in policy:
            key, op, val = p
            check = key_in_node
            if key.startswith("!"):
                key = key[1:]
                check = cf_(not_, key_in_node)
            lhs = Sum([If(vmap[v][n], 1, 0) for n in nodes if check(key, n)])
            o.append(
                And(
                    AtLeast(*[vmap[v][n] for n in nodes], 1),
                    expr(op, lhs, int(val)),
                )
            )
    return o


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


def res_by_var(model, nodes, vmap):
    return {v: sort_([n for n in nodes if model.eval(vmap[v][n])]) for v in vmap}


def res_by_domain(model, nodes, vmap):
    return sort_({n: fst(v for v in vmap if model.eval(vmap[v][n])) for n in nodes})


def solve(f):
    domain, (constraints, policy) = second(from_angles, parse_lot(f))
    nodes, vmap = prepare(domain, constraints)

    opt = Optimize()
    opt.add(shuffle(assertions(constraints, nodes, vmap)))
    opt.add(shuffle(ensure_nodup_populated(nodes, vmap)))
    opt.add(shuffle(ensure_group_policy(policy, nodes, vmap)))
    opt.add(shuffle(ensure_nodup_root(nodes, vmap)))
    if opt.check() == sat:
        model = opt.model()
        return dmap(
            d=res_by_domain(model, nodes, vmap),
            v=res_by_var(model, nodes, vmap),
        )
    else:
        error("Error, No solution found")
