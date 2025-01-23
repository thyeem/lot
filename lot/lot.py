import calendar
import re
from collections import defaultdict
from datetime import datetime
from unicodedata import east_asian_width

import openpyxl
from foc import *
from openpyxl.styles import PatternFill
from ortools.sat.python import cp_model
from ouch import *

from .parser import *


# ----------------------
# parse LoT source code
# ----------------------
def parse_lot(f):
    _, s = jump(reader(f).read())
    g, s = parse_grid(s)
    _, s = parse_bar(s)
    a, s = parse_policy(s)
    if s:
        error(f"Error, incomplete parsing: {s[:64]}")
    return g, dict(a)  # (grid, policy)


def parse_grid(s):
    return sepby(token(string("+")), many(kwd_list))(s)


def parse_bar(s):
    try:
        _, s = char("-")(s)
        _, s = char("-")(s)
        _, s = some(char("-"))(s)
        _, s = jump(s)
        return None, s
    except:
        error(f"Error, failed to parse bar: {s[:64]}")


def parse_policy(s):
    def acts(s):
        _, s = token(char("@"))(s)
        r, s = token(digits)(s)
        return r, s

    def unit(s):
        v, s = token(
            angles(token(some(noneof("<>"), fold=True))),
        )(s)
        n, s = option("", acts)(s)
        r, s = many(choice(parse_x, parse_o))(s)
        if n:
            r.append(("@", n))
        return (v, r), s

    try:
        return some(unit)(s)
    except:
        error(f"Error, failed to parse policy: {s[:64]}")


def parse_x(s):
    try:
        _, s = token(char("-"))(s)
        x, s = token(oneof("xX"))(s)
        r, s = token(
            squares(sepby(token(char(",")), xkwd)),
        )(s)
        return (x.lower(), concatmapl(unfold, r)), s
    except:
        error(f"Error, failed to parse 'X': {s[:64]}")


def parse_o(s):
    try:
        _, s = token(char("-"))(s)
        o, s = token(oneof("oO"))(s)
        r, s = token(
            squares(sepby(token(char(",")), choice(qbound, xkwd))),
        )(s)
        return (o.lower(), concatmapl(unfold, r)), s
    except:
        error(f"Error, failed to parse 'O': {s[:64]}")


def kwd_list(s):
    r, s = token(squares(sepby(token(char(",")), kwd)))(s)
    return concatmapl(expand, r), s


def kwd_tuple(s):
    r, s = token(parens(sepby(token(char(",")), kwd)))(s)
    return concatmapl(expand, r), s


def kwd(s):
    return token(some(noneof("#[]<=>(),:+ \n\t"), fold=True))(s)


def xkwd(s):
    return token(sepby(char(":"), choice(kwd_tuple, kwd)))(s)


def qbound(s):
    o = []
    r, s = xkwd(s)
    o.append(tuple(r))
    r, s = token(
        choice(string("<="), string(">="), string("="), string("<"), string(">"))
    )(s)
    o.append(r)
    r, s = token(digits)(s)
    o.append(r)
    return ("#", o), s


def expand(x):
    span = re.fullmatch(r"(\d+)\s*-\s*(\d+)", x)
    if span:
        return map(str, seq(*map(int, span.groups())))
    step = re.fullmatch(r"(\d+)\s*-\s*(\d+)\s*;\s*(\d+)", x)
    if step:
        i, j, k = map(int, step.groups())
        return map(str, seq(i, i + k, j))
    return [x]


def unfold(q):
    def norm(q):
        return cartprodl(*[x if isinstance(x, list) else [x] for x in q])

    if fst(q) == "#":
        key, sym, val = snd(q)
        return [("#", (x, sym, val)) for x in norm(key)]
    else:
        return norm(q)


# ---------------------------------------------------------------------
#        LoT | grid + --- + policy
# ---------------------------------------------------------------------
#      nodes | cartprod(grid)            ;; junctions of grid
#     policy | { actor: [preference] }   ;; actor's requests
#     actors | policy.keys()             ;; target group
#        act | (actor, *node)            ;; unique id in vars
#       vars | { act: model.boolvar }    ;; model variables
#     coeffs | { act: float }            ;; weights of availability
#  objective | sum(coeffs[act] * vars[act], ...)
# ---------------------------------------------------------------------


def solve(args):
    grid, policy = parse_lot(args.FILE)
    validate_policy(grid, policy)
    consts = dict(
        grid=grid,
        policy=policy,
        nodes=gen_nodes(grid),
        actors=policy.keys(),
    )
    ub = args.ubound or len(consts["nodes"]) // len(consts["policy"]) or 1
    max_it = 10
    it = 0
    while True:
        model = cp_model.CpModel()
        vars = gen_vars(model, consts)
        coeffs = process_policy(model, vars, consts)
        rule_single_actor_per_node(model, vars, consts)
        rule_at_most_one_act_per_root(model, vars, consts)
        rule_clip_act_per_actor(model, vars, consts, ub)

        solver = cp_model.CpSolver()
        set_objective(model, vars, coeffs, consts)
        if solver.solve(model) in (cp_model.FEASIBLE, cp_model.OPTIMAL):
            o = collect_results(solver, vars, coeffs, consts)
            report_and_export(consts, o, args)
            break
        if it > max_it:
            print("Error, maximum iterations reached: Aborting.")
            return
        ub += 1
        it += 1
        if args.verbose:
            print(f"Warning, not found feasible, set ub={ub}.")
    if args.verbose:
        print()
        print(justf("number of acts\t", 20, ">"), f"{ub}")
        print(justf("conflicts\t", 20, ">"), f"{solver.num_conflicts}")
        print(justf("branches\t", 20, ">"), f"{solver.num_branches}")
        print(justf("wall time\t", 20, ">"), f"{solver.wall_time:4f} s")


def gen_nodes(grid):
    return cf_(dsort, concat)(cartprod(*g) for g in grid)


def gen_vars(model, consts):
    vars = {}
    for actor in consts["actors"]:
        for node in consts["nodes"]:
            act = (actor, *node)
            vars[act] = model.new_bool_var("_".join(act))
    return vars


def match_node(prefs, node):
    return any(set(item).issubset(set(node)) for item in prefs)


def dsort(x):
    return sort(
        x,
        key=cf_(
            lambda o: int(o) if o.isdigit() else o,
            op.itemgetter(0),
        ),
    )


def expr(sym, lhs, rhs):
    return (
        {"<": op.lt, "<=": op.le, "=": op.eq, ">": op.gt, ">=": op.ge}.get(sym)
        or error(f"Error, no such operator provided: {sym}")
    )(lhs, rhs)


def validate_policy(grid, policy):
    keys = set(flat(grid))
    found = []
    for actor, prefs in policy.items():
        d = read_prefs(prefs)
        for k in flat(d["o"], d["x"]):
            if k not in keys:
                found.append((k, actor))
    if found:
        print("Invalid keywords:")
        for k, actor in found:
            print(f"    '{k}', from <{actor}>")
        error(f"Error, found {len(found)} error(s).")


def process_policy(model, vars, consts):
    coeffs = {}
    for actor, prefs in consts["policy"].items():
        d = read_prefs(prefs)
        # process @-acts if any
        if d["@"]:
            model.add(
                sum(vars[(actor, *node)] for node in consts["nodes"]) == d["@"],
            )
        # process q-preference
        for key, sym, val in d["q"]:
            lhs = sum(
                vars[(actor, *node)]
                for node in consts["nodes"]
                if match_node([key], node)
            )
            model.add(expr(sym, lhs, int(val)))
        for node in consts["nodes"]:
            act = (actor, *node)
            # process o-preference
            coeffs[act] = 1 if not d["o"] or match_node(d["o"], node) else 0
            # process x-preference
            if match_node(d["x"], node):
                model.add(vars[act] == 0)
    return coeffs


def read_prefs(prefs):
    d = defaultdict(list)
    for sym, items in prefs:
        if sym == "o":
            for item in items:
                if fst(item) == "#":
                    d["o"].append(fst(snd(item)))
                    d["q"].append(snd(item))
                else:
                    d["o"].append(item)
        elif sym == "x":
            d["x"].extend(items)
        elif sym == "@":
            d["@"] = int(items)
        else:
            error(f"Error, used illegal symbol: {sym}")
    return d


def rule_single_actor_per_node(model, vars, consts):
    for node in consts["nodes"]:
        model.add(sum(vars[(actor, *node)] for actor in consts["actors"]) == 1)


def rule_at_most_one_act_per_root(model, vars, consts):
    root = cf_(uniq, fst, zip)(*consts["nodes"])
    rmap = {}
    for node in consts["nodes"]:
        r = fst(node)
        if r in rmap:
            rmap[r].append(node)
        else:
            rmap[r] = [node]
    for actor in consts["actors"]:
        for r in root:
            model.add(sum(vars[(actor, *node)] for node in rmap[r]) <= 1)


def rule_clip_act_per_actor(model, vars, consts, ub):
    for actor in consts["actors"]:
        acts = []
        for node in consts["nodes"]:
            act = (actor, *node)
            acts.append(vars[act])
        model.add(1 <= sum(acts))  # assign at least once per actor
        model.add(sum(acts) <= ub)


def set_objective(model, vars, coeffs, consts):
    model.maximize(
        sum(
            (coeffs[(actor, *node)] + rand(0.1)) * vars[(actor, *node)]
            for actor in consts["actors"]
            for node in consts["nodes"]
        )
    )


def collect_results(solver, vars, coeffs, consts):
    o = dict(nodes={}, actors=defaultdict(list))
    for actor in consts["actors"]:
        for node in consts["nodes"]:
            act = (actor, *node)
            if solver.value(vars[act]) == 1:
                if coeffs[act]:
                    o["nodes"][node] = actor
                    o["actors"][actor].append(node)
                else:
                    o["nodes"][node] = "*"
    return o


# ----------------------
# report and dump files
# ----------------------
def report_and_export(consts, o, args):
    def jx(node):
        return ":".join(node)

    def uni(s):
        return sum(2 if east_asian_width(c) in {"W", "F"} else 1 for c in s)

    def by_actors():
        print()
        for actor in sort(consts["actors"]):
            print(actor)
            print("\n".join([" " * 8 + jx(node) for node in o["actors"][actor]]))

    def by_nodes():
        c = max(uni(jx(node)) for node in consts["nodes"]) + 4
        print()
        for node in consts["nodes"]:
            print(f"{justf(jx(node), c, pad='.')}", f"{o['nodes'][node]}")

    def base_cal():
        year = args.year or datetime.today().year
        month = args.month or datetime.today().month
        cal = calendar.Calendar(firstweekday=6).monthdayscalendar(year, month)
        days = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
        events = defaultdict(list)
        for node in consts["nodes"]:
            events[int(fst(node))].append(f"{last(node)}:{o['nodes'][node][:4]}")
        return cal, days, events, year, month

    def to_cal():
        cal, days, events, *_ = base_cal()
        c = max(uni(x) for e in events.values() for x in e)
        bar = "-" * 7 * (c + 3)
        nul = " " * c
        print()
        print(bar)
        print(" | ".join(justf(str(day), c, "^") for day in days))
        print(bar)
        for week in cal:
            row = []
            for day in week:
                row.append(nul if day == 0 else justf(f"{day}", c))
            print(" | ".join(row))
            for i in range(max(len(events.get(day, [])) for day in week)):
                e = []
                for day in week:
                    e.append(
                        nul
                        if day == 0 or i >= len(events.get(day, []))
                        else justf(f"{events[day][i]}", c)
                    )
                print(" | ".join(e))
            print(bar)

    def adjust(ws):
        for col in ws.iter_cols():
            c = max(uni(f"{cell.value}") if cell.value else 0 for cell in col)
            ws.column_dimensions[
                openpyxl.utils.get_column_letter(col[0].column)
            ].width = (c + 2)

    def by_actors_xl(wb):
        ws = wb.create_sheet(title="by-actors")
        for actor in sort(consts["actors"]):
            for i, node in enumerate(o["actors"][actor]):
                ws.append(["", jx(node)] if i else [actor, jx(node)])
        adjust(ws)

    def by_nodes_xl(wb):
        ws = wb.create_sheet(title="by-nodes")
        for node in consts["nodes"]:
            ws.append([jx(node), o["nodes"][node]])
        adjust(ws)

    def to_cal_xl(wb):
        cal, days, events, year, month = base_cal()
        ws = wb.create_sheet(title=f"{year}-{month:02d}")
        skyblue = PatternFill(start_color="cfecf7", fill_type="solid")
        gray = PatternFill(start_color="efefef", fill_type="solid")
        for col, day in enumerate(days, start=1):
            ws.cell(row=1, column=col, value=day).fill = gray
        for week in cal:
            row = []
            for col, day in enumerate(week, start=1):
                row.append("" if day == 0 else day)
            ws.append(row)
            for col, day in enumerate(week, start=1):
                ws.cell(row=ws.max_row, column=col).fill = skyblue
            for i in range(max(len(events.get(day, [])) for day in week)):
                e = []
                for day in week:
                    e.append(
                        ""
                        if day == 0 or i >= len(events.get(day, []))
                        else events[day][i]
                    )
                ws.append(e)
        adjust(ws)

    if args.actor:
        by_actors()
    if args.node:
        by_nodes()
    if args.cal:
        to_cal()
    if args.output:
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        to_cal_xl(wb)
        by_nodes_xl(wb)
        by_actors_xl(wb)
        wb.save(
            args.output
            if args.output.split(".")[-1] in ("xlsx", "xls")
            else f"{args.output}.xlsx"
        )
