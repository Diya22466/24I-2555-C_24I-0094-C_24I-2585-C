"""Validation rules V1-V8 of Section 4.

Written independently of the generator: it has its own copy of the rules and
recomputes every value from the raw rows. Nothing in the file is trusted.
"""

import bisect
import heapq
from collections import deque
from fractions import Fraction

GROUP_SEED = 40

SHEETS = [
    ("cases", ["case_id", "group_seed", "case_no", "tier", "scenario", "capacity",
               "target_0", "target_1", "target_2", "edit_bound", "tour_length",
               "sensor_nodes", "sensor_k", "safety_vars", "rations_target"]),
    ("crates", ["case_id", "crate_id", "cat", "weight", "value", "expiry", "serial"]),
    ("locations", ["case_id", "loc_id", "type", "penalty"]),
    ("roads", ["case_id", "road_no", "u", "v", "minutes", "cable"]),
    ("waves", ["case_id", "wave_no", "road_no"]),
    ("radio_log", ["case_id", "part", "text"]),
    ("radio_patterns", ["case_id", "pattern_no", "pattern", "count"]),
    ("radio_reports", ["case_id", "report_a", "report_b"]),
    ("windows", ["case_id", "window_id", "start", "finish", "value"]),
    ("incidents", ["case_id", "alarm_id", "tick", "priority"]),
    ("sites", ["case_id", "site_no", "x", "y"]),
    ("tour", ["case_id", "step", "site_no"]),
    ("pipeline_dims", ["case_id", "idx", "dim"]),
    ("drum_prices", ["case_id", "length", "price"]),
    ("sensor_edges", ["case_id", "u", "v"]),
    ("sensor_cover", ["case_id", "node"]),
    ("safety_rules", ["case_id", "rule_no", "lit_1", "lit_2", "lit_3"]),
    ("safety_planted", ["case_id", "switch", "value"]),
    ("rations", ["case_id", "item", "value", "planted"]),
    ("claims", ["case_id", "cargo_opt", "window_count_opt", "window_value_opt",
                "drum_opt", "tour_opt", "cover_min"]),
]
TEXT_COLUMNS = {"case_id", "tier", "type", "text", "pattern", "report_a", "report_b"}

RANGES = {
    "S": {"crates": (8, 20), "locations": (6, 12), "log": (200, 500), "report": (10, 30),
          "windows": (8, 20), "alarms": (10, 40), "sites": (5, 9), "stages": (4, 8),
          "drum": (5, 14), "sensors": (6, 14), "safety_vars": (6, 15), "rations": (8, 20)},
    "M": {"crates": (40, 200), "locations": (30, 150), "log": (2000, 10000), "report": (30, 150),
          "windows": (50, 300), "alarms": (200, 1000), "sites": (10, 16), "stages": (15, 60),
          "drum": (40, 200), "sensors": (20, 40), "safety_vars": (20, 50), "rations": (24, 40)},
    "L": {"crates": (500, 1500), "locations": (500, 2000), "log": (20000, 100000), "report": (200, 1000),
          "windows": (1000, 3000), "alarms": (2000, 5000), "sites": (200, 500), "stages": (100, 300),
          "drum": (500, 2000), "sensors": (100, 400), "safety_vars": (20, 50), "rations": (50, 100)},
}
ALPHABET = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
PATTERN_LENGTHS = [2, 4, 8, 12, 20, 40]


def expected_tier(case_no):
    if case_no <= 19:
        return "S"
    if case_no <= 39:
        return "M"
    if case_no <= 45:
        return "L"
    return "X"


def size_range(item, tier, case_no):
    """Range of a size; tier X uses tier L except where its trap overrides it."""
    if case_no == 46 and item == "crates":
        return 1500, 3000
    if case_no == 47 and item == "crates":
        return 12, 60
    if case_no == 48 and item == "locations":
        return 1500, 3000
    if case_no == 49 and item == "log":
        return 50000, 100000
    if tier == "X":
        tier = "L"
    return RANGES[tier][item]


def in_range(errors, label, value, low, high):
    if not (low <= value <= high):
        errors.append("%s = %s, allowed %s..%s" % (label, value, low, high))


def consecutive(errors, label, values, start):
    if values != list(range(start, start + len(values))):
        errors.append("%s must run %d, %d, ... without gaps (found %s...)"
                      % (label, start, start + 1, values[:6]))


def full_log(case):
    parts = sorted(case["radio_log"], key=lambda r: r["part"])
    return "".join(r["text"] for r in parts)


# ====================================================================== V1

def check_book(book, full):
    """V1 for the workbook as a whole: sheets, headers, cell types, order, case ids."""
    errors = []
    expected_names = [name for name, header in SHEETS]
    if book["names"] != expected_names:
        errors.append("sheets are %s; expected exactly %s" % (book["names"], expected_names))
    for name, header in SHEETS:
        if name in book["headers"] and book["headers"][name] != header:
            errors.append("sheet %s header is %s; expected %s" % (name, book["headers"][name], header))
    for problem in book["file_problems"]:
        errors.append(problem)

    for name, header in SHEETS:
        rows = book["rows"].get(name, [])
        bad = 0
        for index in range(len(rows)):
            row = rows[index]
            for column in header:
                value = row.get(column)
                if column in TEXT_COLUMNS:
                    ok = isinstance(value, str) and value != "" and value.isascii()
                else:
                    ok = isinstance(value, int) and not isinstance(value, bool)
                if not ok:
                    bad += 1
                    if bad <= 3:
                        errors.append("%s row %d: %s = %r has the wrong type or is empty"
                                      % (name, index + 2, column, value))
        if bad > 3:
            errors.append("%s: %d more cells with the wrong type" % (name, bad - 3))
        if bad == 0:
            for index in range(1, len(rows)):
                before = (rows[index - 1]["case_id"], rows[index - 1][header[1]])
                after = (rows[index]["case_id"], rows[index][header[1]])
                if after < before:
                    errors.append("%s row %d is not sorted by case_id, then %s"
                                  % (name, index + 2, header[1]))
                    break

    case_rows = book["rows"].get("cases", [])
    ids = [row["case_id"] for row in case_rows]
    if len(set(ids)) != len(ids):
        errors.append("cases sheet has repeated case_ids")
    if full:
        wanted = ["%d-%02d" % (GROUP_SEED, k) for k in range(50)]
        if len(case_rows) != 50 or sorted(ids) != wanted:
            errors.append("cases sheet must have exactly the 50 case_ids %s .. %s"
                          % (wanted[0], wanted[-1]))
    for name, header in SHEETS[1:]:
        for row in book["rows"].get(name, []):
            if row["case_id"] not in ids:
                errors.append("sheet %s has case_id %r that is not in the cases sheet"
                              % (name, row["case_id"]))
                break
    return errors


def check_v1_case(case, case_id):
    """V1 for one case: id format, case_no, tier, scenario, required rows."""
    errors = []
    row = case["row"]
    parts = case_id.split("-")
    if len(parts) != 2 or parts[0] != str(GROUP_SEED) or len(parts[1]) != 2 or not parts[1].isdigit():
        errors.append("case_id %r is not in the format %d-kk" % (case_id, GROUP_SEED))
        return errors
    case_no = int(parts[1])
    if row["group_seed"] != GROUP_SEED:
        errors.append("group_seed %s, expected %d" % (row["group_seed"], GROUP_SEED))
    if row["case_no"] != case_no:
        errors.append("case_no %s does not match case_id %s" % (row["case_no"], case_id))
    if row["tier"] != expected_tier(case_no):
        errors.append("tier %s, expected %s" % (row["tier"], expected_tier(case_no)))
    if row["scenario"] != case_no % 6 + 1:
        errors.append("scenario %s, expected %d" % (row["scenario"], case_no % 6 + 1))
    if len(case["radio_reports"]) != 1:
        errors.append("needs exactly one radio_reports row, found %d" % len(case["radio_reports"]))
    claims_needed = 1 if expected_tier(case_no) == "S" else 0
    if len(case["claims"]) != claims_needed:
        errors.append("needs %d claims rows (claims are for tier S only), found %d"
                      % (claims_needed, len(case["claims"])))
    return errors


# ====================================================================== V2

def touching_pairs(windows):
    starts = {}
    for w in windows:
        starts[w["start"]] = starts.get(w["start"], 0) + 1
    pairs = 0
    for w in windows:
        pairs += starts.get(w["finish"], 0)
    return pairs


def check_v2(case, case_no, tier):
    """V2: every size and value is inside its range."""
    e = []
    row = case["row"]

    crates = case["crates"]
    in_range(e, "number of crates", len(crates), *size_range("crates", tier, case_no))
    total_weight = 0
    for c in crates:
        label = "crate %s" % c["crate_id"]
        in_range(e, label + " cat", c["cat"], 0, 4)
        in_range(e, label + " weight", c["weight"], 1, 20)
        in_range(e, label + " value", c["value"], 10, 100)
        in_range(e, label + " expiry", c["expiry"], 0, 999)
        in_range(e, label + " serial", c["serial"], 10000000, 99999999)
        total_weight += c["weight"]
    capacity = row["capacity"]
    if capacity < 1 or 10 * capacity < total_weight or 10 * capacity > 7 * total_weight:
        e.append("capacity %s is not 10%%..70%% of total weight %d (and >= 1)"
                 % (capacity, total_weight))

    locations = case["locations"]
    V = len(locations)
    in_range(e, "number of locations", V, *size_range("locations", tier, case_no))
    in_range(e, "number of roads", len(case["roads"]), V - 1, 3 * V)
    for loc in locations:
        if loc["type"] not in ("D", "S", "H", "J"):
            e.append("location %s has type %r" % (loc["loc_id"], loc["type"]))
        if loc["penalty"] not in (0, 1, 2, 4, 6):
            e.append("location %s has penalty %s" % (loc["loc_id"], loc["penalty"]))
    hq = [loc for loc in locations if loc["loc_id"] == 0]
    if len(hq) != 1 or hq[0]["type"] != "D" or hq[0]["penalty"] != 0:
        e.append("location 0 (HQ) must exist with type D and penalty 0")
    types = [loc["type"] for loc in locations]
    if "S" not in types or "H" not in types:
        e.append("needs at least one shelter (S) and one hospital (H)")
    for r in case["roads"]:
        in_range(e, "road %s minutes" % r["road_no"], r["minutes"], 1, 60)
        in_range(e, "road %s cable" % r["road_no"], r["cable"], 1, 100)
    n_waves = len(set(w["wave_no"] for w in case["waves"]))
    in_range(e, "number of closure waves", n_waves, 2, 5)

    log = full_log(case)
    in_range(e, "radio log length", len(log), *size_range("log", tier, case_no))
    if not set(log) <= ALPHABET:
        e.append("radio log has symbols outside the 38-symbol alphabet: %s"
                 % sorted(set(log) - ALPHABET)[:5])
    for p in case["radio_patterns"]:
        if not set(p["pattern"]) <= ALPHABET:
            e.append("pattern %s has symbols outside the alphabet" % p["pattern_no"])
    for report in case["radio_reports"]:
        for key in ("report_a", "report_b"):
            in_range(e, key + " length", len(report[key]), *size_range("report", tier, case_no))
            if not set(report[key]) <= ALPHABET:
                e.append("%s has symbols outside the alphabet" % key)

    windows = case["windows"]
    in_range(e, "number of windows", len(windows), *size_range("windows", tier, case_no))
    for w in windows:
        label = "window %s" % w["window_id"]
        if not (0 <= w["start"] < w["finish"] <= 1440):
            e.append(label + " must have 0 <= start < finish <= 1440")
        in_range(e, label + " duration", w["finish"] - w["start"], 5, 480)
        in_range(e, label + " value", w["value"], 1, 100)
    if len(windows) >= 8 and touching_pairs(windows) < 2:
        e.append("with 8 or more windows at least two pairs must touch, found %d"
                 % touching_pairs(windows))

    alarms = case["incidents"]
    n_alarms = len(alarms)
    in_range(e, "number of alarms", n_alarms, *size_range("alarms", tier, case_no))
    if n_alarms > 0:
        if alarms[0]["tick"] != 0:
            e.append("the first alarm tick must be 0")
        for i in range(1, n_alarms):
            if alarms[i]["tick"] < alarms[i - 1]["tick"]:
                e.append("alarm ticks decrease at alarm %s" % alarms[i]["alarm_id"])
                break
        for a in alarms:
            in_range(e, "alarm %s priority" % a["alarm_id"], a["priority"], 1, 10)
        if tier in ("M", "L", "X"):
            ticks = alarms[-1]["tick"] + 1
            # 1.2 <= n / ticks <= 1.8, written with integers
            if not (12 * ticks <= 10 * n_alarms <= 18 * ticks):
                e.append("alarms per tick %.3f not in 1.2..1.8" % (n_alarms / ticks))
            priorities = set(a["priority"] for a in alarms)
            if len(priorities) < 6 or 1 not in priorities:
                e.append("needs at least 6 distinct priorities including 1")

    sites = case["sites"]
    in_range(e, "number of sites", len(sites), *size_range("sites", tier, case_no))
    for s in sites:
        in_range(e, "site %s x" % s["site_no"], s["x"], 0, 999)
        in_range(e, "site %s y" % s["site_no"], s["y"], 0, 999)

    dims = case["pipeline_dims"]
    in_range(e, "number of pipeline stages", len(dims) - 1, *size_range("stages", tier, case_no))
    for d in dims:
        in_range(e, "dim %s" % d["idx"], d["dim"], 2, 100)

    prices = case["drum_prices"]
    in_range(e, "drum length", len(prices), *size_range("drum", tier, case_no))
    for p in prices:
        in_range(e, "price of length %s" % p["length"], p["price"], 1, 500)
    if prices and all(p["price"] * prices[0]["length"] == prices[0]["price"] * p["length"]
                      for p in prices):
        e.append("drum prices are all proportional to length")

    n_nodes = row["sensor_nodes"]
    in_range(e, "sensor_nodes", n_nodes, *size_range("sensors", tier, case_no))
    if len(case["sensor_edges"]) < n_nodes - 1:
        e.append("sensor graph has %d edges, needs at least n - 1 = %d"
                 % (len(case["sensor_edges"]), n_nodes - 1))
    k = row["sensor_k"]
    if not (2 <= k and 2 * k <= n_nodes):
        e.append("sensor_k %s must satisfy 2 <= k <= n/2 (n = %s)" % (k, n_nodes))

    n_vars = row["safety_vars"]
    in_range(e, "safety_vars", n_vars, *size_range("safety_vars", tier, case_no))
    n_rules = len(case["safety_rules"])
    if not (2 * n_vars <= n_rules <= 6 * n_vars):
        e.append("rules per switch %d/%d not in 2.0..6.0" % (n_rules, n_vars))
    for rule in case["safety_rules"]:
        lits = [rule["lit_1"], rule["lit_2"], rule["lit_3"]]
        switches = [abs(x) for x in lits]
        if 0 in lits or len(set(switches)) != 3:
            e.append("rule %s must use three non-zero literals on different switches"
                     % rule["rule_no"])
    for p in case["safety_planted"]:
        if p["value"] not in (0, 1):
            e.append("switch %s planted value %s is not 0/1" % (p["switch"], p["value"]))

    rations = case["rations"]
    in_range(e, "number of rations", len(rations), *size_range("rations", tier, case_no))
    for r in rations:
        in_range(e, "ration %s value" % r["item"], r["value"], 1, 1000)
        if r["planted"] not in (0, 1):
            e.append("ration %s planted flag %s is not 0/1" % (r["item"], r["planted"]))
    if row["rations_target"] < 1:
        e.append("rations_target must be positive")
    return e


# ====================================================================== V3

def check_v3(case):
    """V3: identifiers unique / consecutive; every reference exists."""
    e = []
    row = case["row"]
    consecutive(e, "crate_id", [c["crate_id"] for c in case["crates"]], 1)
    serials = [c["serial"] for c in case["crates"]]
    if len(set(serials)) != len(serials):
        e.append("crate serials are not distinct")

    V = len(case["locations"])
    consecutive(e, "loc_id", [loc["loc_id"] for loc in case["locations"]], 0)
    E = len(case["roads"])
    consecutive(e, "road_no", [r["road_no"] for r in case["roads"]], 0)
    pairs = set()
    for r in case["roads"]:
        if not (0 <= r["u"] < r["v"] < V):
            e.append("road %s has ends %s, %s (need 0 <= u < v < V = %d)"
                     % (r["road_no"], r["u"], r["v"], V))
        if (r["u"], r["v"]) in pairs:
            e.append("road pair (%s, %s) is repeated" % (r["u"], r["v"]))
        pairs.add((r["u"], r["v"]))
    for w in case["waves"]:
        if not (0 <= w["road_no"] < E):
            e.append("wave %s closes road %s, which does not exist" % (w["wave_no"], w["road_no"]))
    wave_numbers = sorted(set(w["wave_no"] for w in case["waves"]))
    consecutive(e, "wave_no", wave_numbers, 1)

    targets = [row["target_0"], row["target_1"], row["target_2"]]
    if len(set(targets)) != 3:
        e.append("targets %s are not distinct" % targets)
    type_of = {}
    for loc in case["locations"]:
        type_of[loc["loc_id"]] = loc["type"]
    for t in targets:
        if t == 0 or type_of.get(t) not in ("S", "H"):
            e.append("target %s must be an existing shelter or hospital, not the HQ" % t)

    consecutive(e, "window_id", [w["window_id"] for w in case["windows"]], 1)
    consecutive(e, "alarm_id", [a["alarm_id"] for a in case["incidents"]], 1)

    n_sites = len(case["sites"])
    consecutive(e, "site_no", [s["site_no"] for s in case["sites"]], 0)
    points = [(s["x"], s["y"]) for s in case["sites"]]
    if len(set(points)) != len(points):
        e.append("two sites have the same coordinates")
    consecutive(e, "tour step", [t["step"] for t in case["tour"]], 0)
    for t in case["tour"]:
        if not (0 <= t["site_no"] < n_sites):
            e.append("tour step %s visits site %s, which does not exist" % (t["step"], t["site_no"]))

    consecutive(e, "pipeline idx", [d["idx"] for d in case["pipeline_dims"]], 0)
    consecutive(e, "drum length", [p["length"] for p in case["drum_prices"]], 1)

    n_nodes = row["sensor_nodes"]
    edge_set = set()
    for edge in case["sensor_edges"]:
        if not (0 <= edge["u"] < edge["v"] < n_nodes):
            e.append("sensor edge (%s, %s) is invalid (need 0 <= u < v < %s)"
                     % (edge["u"], edge["v"], n_nodes))
        if (edge["u"], edge["v"]) in edge_set:
            e.append("sensor edge (%s, %s) is repeated" % (edge["u"], edge["v"]))
        edge_set.add((edge["u"], edge["v"]))
    cover = [c["node"] for c in case["sensor_cover"]]
    if len(set(cover)) != len(cover):
        e.append("cover nodes are not distinct")
    for node in cover:
        if not (0 <= node < n_nodes):
            e.append("cover node %s does not exist" % node)

    n_vars = row["safety_vars"]
    consecutive(e, "rule_no", [r["rule_no"] for r in case["safety_rules"]], 1)
    for rule in case["safety_rules"]:
        for lit in (rule["lit_1"], rule["lit_2"], rule["lit_3"]):
            if not (1 <= abs(lit) <= n_vars):
                e.append("rule %s uses switch %s, which does not exist" % (rule["rule_no"], lit))
    consecutive(e, "planted switch", [p["switch"] for p in case["safety_planted"]], 1)
    if len(case["safety_planted"]) != n_vars:
        e.append("safety_planted has %d switches, safety_vars is %s"
                 % (len(case["safety_planted"]), n_vars))
    consecutive(e, "ration item", [r["item"] for r in case["rations"]], 0)
    consecutive(e, "pattern_no", [p["pattern_no"] for p in case["radio_patterns"]], 0)
    return e


# ====================================================================== V4

def neighbours_of(V, roads, closed=()):
    adj = [[] for i in range(V)]
    for r in roads:
        if r["road_no"] not in closed and 0 <= r["u"] < V and 0 <= r["v"] < V:
            adj[r["u"]].append((r["v"], r["minutes"]))
            adj[r["v"]].append((r["u"], r["minutes"]))
    return adj


def hop_distances(adj, source):
    dist = [-1] * len(adj)
    dist[source] = 0
    queue = deque([source])
    while queue:
        u = queue.popleft()
        for v, minutes in adj[u]:
            if dist[v] == -1:
                dist[v] = dist[u] + 1
                queue.append(v)
    return dist


def check_v4(case):
    """V4: connected before closures; waves disjoint and within their size limit."""
    e = []
    V = len(case["locations"])
    E = len(case["roads"])
    dist = hop_distances(neighbours_of(V, case["roads"]), 0)
    unreachable = dist.count(-1)
    if unreachable > 0:
        e.append("network is not connected before closures (%d locations unreachable)" % unreachable)
    seen = set()
    for w in case["waves"]:
        if w["road_no"] in seen:
            e.append("road %s is closed twice (waves must be disjoint)" % w["road_no"])
        seen.add(w["road_no"])
    limit = max(1, E // 4)
    sizes = {}
    for w in case["waves"]:
        sizes[w["wave_no"]] = sizes.get(w["wave_no"], 0) + 1
    for wave_no in sorted(sizes):
        if not (1 <= sizes[wave_no] <= limit):
            e.append("wave %s has %d roads, allowed 1..%d" % (wave_no, sizes[wave_no], limit))
    return e


# ====================================================================== V5

def count_overlapping(text, pattern):
    """Naive scan of every start position (overlaps included)."""
    count = 0
    for i in range(len(text) - len(pattern) + 1):
        if text.startswith(pattern, i):
            count += 1
    return count


def edit_distance(a, b):
    previous = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        current = [i] + [0] * len(b)
        for j in range(1, len(b) + 1):
            replace = previous[j - 1] + (0 if a[i - 1] == b[j - 1] else 1)
            current[j] = min(previous[j] + 1, current[j - 1] + 1, replace)
        previous = current
    return previous[len(b)]


def knapsack_dp(crates, capacity):
    best = [0] * (capacity + 1)
    for c in crates:
        for w in range(capacity, c["weight"] - 1, -1):
            best[w] = max(best[w], best[w - c["weight"]] + c["value"])
    return best[capacity]


def greedy_by_ratio(crates, capacity):
    order = sorted(crates, key=lambda c: (-Fraction(c["value"], c["weight"]), c["crate_id"]))
    weight, value = 0, 0
    for c in order:
        if weight + c["weight"] <= capacity:
            weight += c["weight"]
            value += c["value"]
    return value


def max_compatible_count(windows):
    """Earliest finish first (touching windows are compatible)."""
    count, last_finish = 0, 0
    for w in sorted(windows, key=lambda w: w["finish"]):
        if w["start"] >= last_finish:
            count += 1
            last_finish = w["finish"]
    return count


def max_compatible_value(windows):
    """Weighted interval scheduling by DP over windows sorted by finish."""
    order = sorted(windows, key=lambda w: w["finish"])
    finishes = [w["finish"] for w in order]
    best = [0] * (len(order) + 1)
    for j in range(1, len(order) + 1):
        w = order[j - 1]
        p = bisect.bisect_right(finishes, w["start"], 0, j - 1)
        best[j] = max(best[j - 1], w["value"] + best[p])
    return best[len(order)]


def rod_cutting(prices):
    price = [0] + [p["price"] for p in prices]
    best = [0] * len(price)
    for length in range(1, len(price)):
        for first in range(1, length + 1):
            best[length] = max(best[length], price[first] + best[length - first])
    return best[len(price) - 1]


def manhattan(a, b):
    return abs(a["x"] - b["x"]) + abs(a["y"] - b["y"])


def held_karp(sites):
    """Shortest closed Manhattan tour from site 0 (DP over subsets)."""
    n = len(sites)
    if n == 1:
        return 0
    INF = float("inf")
    best = [[INF] * n for mask in range(1 << n)]
    best[1][0] = 0
    for mask in range(1 << n):
        if not mask & 1:
            continue
        for last in range(n):
            if best[mask][last] == INF:
                continue
            for nxt in range(n):
                if not mask & (1 << nxt):
                    new_mask = mask | (1 << nxt)
                    cost = best[mask][last] + manhattan(sites[last], sites[nxt])
                    if cost < best[new_mask][nxt]:
                        best[new_mask][nxt] = cost
    full = (1 << n) - 1
    return min(best[full][last] + manhattan(sites[last], sites[0]) for last in range(1, n))


def has_cover(edges, k):
    """Bounded search tree: some end of the first uncovered edge must be chosen."""
    if not edges:
        return True
    if k == 0:
        return False
    u, v = edges[0]
    for chosen in (u, v):
        rest = [edge for edge in edges if chosen not in edge]
        if has_cover(rest, k - 1):
            return True
    return False


def minimum_cover(edges):
    k = 0
    while not has_cover(edges, k):
        k += 1
    return k


def check_v5(case, tier):
    """V5: pattern counts, edit_bound, log parts, tier-S claims."""
    e = []
    row = case["row"]

    parts = [r["part"] for r in case["radio_log"]]
    consecutive(e, "radio log part", parts, 1)
    for r in case["radio_log"]:
        if not (1 <= len(r["text"]) <= 10000):
            e.append("radio log part %s has %d symbols (allowed 1..10000)" % (r["part"], len(r["text"])))

    log = full_log(case)
    patterns = case["radio_patterns"]
    lengths = [len(p["pattern"]) for p in patterns]
    if lengths != PATTERN_LENGTHS:
        e.append("pattern lengths are %s, expected %s" % (lengths, PATTERN_LENGTHS))
    occurring = 0
    for p in patterns:
        true_count = count_overlapping(log, p["pattern"])
        if true_count != p["count"]:
            e.append("pattern %s count is %s, true count %d" % (p["pattern_no"], p["count"], true_count))
        if true_count > 0:
            occurring += 1
    if occurring < 2 or occurring > len(patterns) - 1:
        e.append("%d patterns occur; need at least two occurring and at least one absent" % occurring)

    if len(case["radio_reports"]) == 1:
        a = case["radio_reports"][0]["report_a"]
        b = case["radio_reports"][0]["report_b"]
        true_distance = edit_distance(a, b)
        bound = row["edit_bound"]
        if not (true_distance <= bound <= len(a) + len(b)):
            e.append("edit_bound %s not in [true distance %d, len(a)+len(b) %d]"
                     % (bound, true_distance, len(a) + len(b)))

    if tier == "S" and len(case["claims"]) == 1:
        claims = case["claims"][0]
        edges = [(edge["u"], edge["v"]) for edge in case["sensor_edges"]]
        truth = {
            "cargo_opt": knapsack_dp(case["crates"], row["capacity"]),
            "window_count_opt": max_compatible_count(case["windows"]),
            "window_value_opt": max_compatible_value(case["windows"]),
            "drum_opt": rod_cutting(case["drum_prices"]),
            "tour_opt": held_karp(case["sites"]),
            "cover_min": minimum_cover(edges),
        }
        for key in truth:
            if claims[key] != truth[key]:
                e.append("claim %s = %s, recomputed optimum %s" % (key, claims[key], truth[key]))
    return e


# ====================================================================== V6

def nearest_neighbour_length(sites):
    n = len(sites)
    visited = [False] * n
    visited[0] = True
    current, total = 0, 0
    for step in range(n - 1):
        best = -1
        for s in range(n):
            if not visited[s]:
                if best == -1 or manhattan(sites[current], sites[s]) < manhattan(sites[current], sites[best]):
                    best = s
        total += manhattan(sites[current], sites[best])
        visited[best] = True
        current = best
    return total + manhattan(sites[current], sites[0])


def literal_true(lit, value_of):
    if lit > 0:
        return value_of.get(lit) == 1
    return value_of.get(-lit) == 0


def check_v6(case, tier):
    """V6: planted tour, cover, safety assignment and ration selection are valid."""
    e = []
    row = case["row"]

    sites = case["sites"]
    order = [t["site_no"] for t in case["tour"]]
    if sorted(order) != list(range(len(sites))):
        e.append("tour is not a permutation of all %d sites" % len(sites))
    elif order[0] != 0:
        e.append("tour does not start at site 0")
    else:
        length = 0
        for i in range(len(order)):
            length += manhattan(sites[order[i]], sites[order[(i + 1) % len(order)]])
        if length != row["tour_length"]:
            e.append("tour_length %s, but the planted tour is %d long" % (row["tour_length"], length))
        if tier in ("L", "X"):
            nn = nearest_neighbour_length(sites)
            if length > nn:
                e.append("planted tour %d is longer than the nearest-neighbour tour %d" % (length, nn))

    cover = set(c["node"] for c in case["sensor_cover"])
    if len(case["sensor_cover"]) != row["sensor_k"]:
        e.append("cover has %d nodes, sensor_k is %s" % (len(case["sensor_cover"]), row["sensor_k"]))
    for edge in case["sensor_edges"]:
        if edge["u"] not in cover and edge["v"] not in cover:
            e.append("cover misses sensor edge (%s, %s)" % (edge["u"], edge["v"]))
            break

    value_of = {}
    for p in case["safety_planted"]:
        value_of[p["switch"]] = p["value"]
    for rule in case["safety_rules"]:
        lits = (rule["lit_1"], rule["lit_2"], rule["lit_3"])
        if not any(literal_true(lit, value_of) for lit in lits):
            e.append("planted assignment breaks safety rule %s %s" % (rule["rule_no"], lits))
            break

    planted_sum = sum(r["value"] for r in case["rations"] if r["planted"] == 1)
    if planted_sum != row["rations_target"] or planted_sum < 1:
        e.append("planted rations add up to %d, rations_target is %s"
                 % (planted_sum, row["rations_target"]))
    return e


# ====================================================================== V7

def cheapest_route_costs(adj, penalty, source):
    cost = [None] * len(adj)
    cost[source] = 0
    heap = [(0, source)]
    while heap:
        c, u = heapq.heappop(heap)
        if c > cost[u]:
            continue
        for v, minutes in adj[u]:
            if cost[v] is None or c + minutes + penalty[v] < cost[v]:
                cost[v] = c + minutes + penalty[v]
                heapq.heappush(heap, (cost[v], v))
    return cost


def fewest_roads_costs(adj, penalty, source):
    """Cheapest cost among the routes with the fewest roads, layer by BFS layer."""
    hops = hop_distances(adj, source)
    cost = [None] * len(adj)
    cost[source] = 0
    layer = [source]
    while layer:
        next_layer = []
        for u in layer:
            for v, minutes in adj[u]:
                if hops[v] == hops[u] + 1:
                    if cost[v] is None:
                        next_layer.append(v)
                    if cost[v] is None or cost[u] + minutes + penalty[v] < cost[v]:
                        cost[v] = cost[u] + minutes + penalty[v]
        layer = next_layer
    return cost


def route_costs(case):
    V = len(case["locations"])
    penalty = [0] * V
    for loc in case["locations"]:
        penalty[loc["loc_id"]] = loc["penalty"]
    adj = neighbours_of(V, case["roads"])
    return cheapest_route_costs(adj, penalty, 0), fewest_roads_costs(adj, penalty, 0)


def targets_of(case):
    row = case["row"]
    return [row["target_0"], row["target_1"], row["target_2"]]


def window_overlap_total(windows):
    """Sum over windows of how many other windows overlap it (touching is not overlap)."""
    starts = sorted(w["start"] for w in windows)
    finishes = sorted(w["finish"] for w in windows)
    total = 0
    for w in windows:
        started_before_end = bisect.bisect_left(starts, w["finish"])
        finished_before_start = bisect.bisect_right(finishes, w["start"])
        total += started_before_end - finished_before_start - 1
    return total


def check_v7_signature(case, scenario, tier):
    """V7: the signature rules of the case study (cases 0 to 45)."""
    e = []
    V = len(case["locations"])
    E = len(case["roads"])
    crates = case["crates"]
    n = len(crates)
    n_waves = len(set(w["wave_no"] for w in case["waves"]))

    def share_of(cats):
        return sum(1 for c in crates if c["cat"] in cats)

    if scenario == 1:
        if not (10 * E >= 11 * V and 10 * E <= 16 * V):
            e.append("Delta: average degree %.2f not in 2.2..3.2" % (2 * E / V))
        flooded = sum(1 for loc in case["locations"] if loc["penalty"] >= 2)
        if 10 * flooded < 4 * V:
            e.append("Delta: only %d of %d locations have penalty >= 2 (need 40%%)" % (flooded, V))
        if n_waves < 3:
            e.append("Delta: needs at least 3 waves")
        if 20 * share_of((0, 1)) < 11 * n:
            e.append("Delta: food and water crates below 55%")
    elif scenario == 2:
        if not (E >= V and 10 * E <= 13 * V):
            e.append("Earthquake: average degree %.2f not in 2.0..2.6" % (2 * E / V))
        if 20 * share_of((2, 3)) < 9 * n:
            e.append("Earthquake: medicine and tool crates below 45%")
        alarms = case["incidents"]
        if sum(a["priority"] for a in alarms) < 6 * len(alarms):
            e.append("Earthquake: mean alarm priority below 6.0")
    elif scenario == 3:
        shelters = sum(1 for loc in case["locations"] if loc["type"] == "S")
        if 4 * shelters < V:
            e.append("Cyclone: shelters below 25% of locations")
        if n_waves < 3:
            e.append("Cyclone: needs at least 3 waves")
        windows = case["windows"]
        if window_overlap_total(windows) < 2 * len(windows):
            e.append("Cyclone: windows overlap fewer than 2 others on average")
        if len(set(full_log(case))) < 30:
            e.append("Cyclone: log uses fewer than 30 of the 38 symbols")
    elif scenario == 4:
        if 4 * E < 7 * V:
            e.append("Urban: average degree %.2f below 3.5" % (2 * E / V))
        alarms = case["incidents"]
        if tier in ("M", "L") and alarms:
            ticks = alarms[-1]["tick"] + 1
            if 2 * len(alarms) < 3 * ticks:
                e.append("Urban: fewer than 1.5 alarms per tick")
        if 10 * share_of((4,)) < n:
            e.append("Urban: rare crates below 10%")
    elif scenario == 5:
        if 5 * E > 6 * V:
            e.append("Landslide: average degree %.2f above 2.4" % (2 * E / V))
        degree = [0] * V
        for r in case["roads"]:
            degree[r["u"]] += 1
            degree[r["v"]] += 1
        if max(degree) > 4:
            e.append("Landslide: a location has more than 4 roads")
        dist = hop_distances(neighbours_of(V, case["roads"]), 0)
        if max(dist) < V // 4:
            e.append("Landslide: farthest location is %d roads away, needs floor(V/4) = %d"
                     % (max(dist), V // 4))
        if n_waves < 3:
            e.append("Landslide: needs at least 3 waves")
        closed = set(w["road_no"] for w in case["waves"])
        after = hop_distances(neighbours_of(V, case["roads"], closed), 0)
        if all(after[t] != -1 for t in targets_of(case)):
            e.append("Landslide: all waves together leave every target reachable")
    elif scenario == 6:
        if 20 * share_of((1, 2)) < 11 * n:
            e.append("Outbreak: medicine and water crates below 55%")
        if 2 * sum(1 for c in crates if c["expiry"] <= 300) < n:
            e.append("Outbreak: fewer than half of the crates expire by hour 300")
        log = full_log(case)
        most = max(log.count(symbol) for symbol in set(log))
        if 4 * most < len(log):
            e.append("Outbreak: no symbol is at least 25% of the log")
    return e


def module_fingerprints(case):
    """(module name, size, content) for variety rule 4."""
    def rows(sheet):
        result = []
        for r in case[sheet]:
            result.append(tuple(r[key] for key in sorted(r) if key != "case_id"))
        return tuple(result)

    row = case["row"]
    reports = case["radio_reports"][0] if case["radio_reports"] else {"report_a": "", "report_b": ""}
    return [
        ("crates", len(case["crates"]), (rows("crates"), row["capacity"])),
        ("network", len(case["locations"]), (rows("locations"), rows("roads"), rows("waves"))),
        ("radio log", len(full_log(case)), full_log(case)),
        ("radio reports", max(len(reports["report_a"]), len(reports["report_b"])),
         (reports["report_a"], reports["report_b"])),
        ("windows", len(case["windows"]), rows("windows")),
        ("incidents", len(case["incidents"]), rows("incidents")),
        ("sites", len(case["sites"]), rows("sites")),
        ("pipeline", len(case["pipeline_dims"]) - 1, rows("pipeline_dims")),
        ("drum", len(case["drum_prices"]), rows("drum_prices")),
        ("sensors", row["sensor_nodes"], (rows("sensor_edges"), row["sensor_nodes"])),
        ("safety", row["safety_vars"], rows("safety_rules")),
        ("rations", len(case["rations"]), rows("rations")),
    ]


def check_variety(cases):
    """V7 variety rules across all 50 cases."""
    e = []
    greedy_not_optimal = []
    route_gap = []
    ratios = []
    for case_id in sorted(cases):
        case = cases[case_id]
        case_no = int(case_id.split("-")[1])
        tier = expected_tier(case_no)
        if tier == "S":
            capacity = case["row"]["capacity"]
            if greedy_by_ratio(case["crates"], capacity) < knapsack_dp(case["crates"], capacity):
                greedy_not_optimal.append(case_id)
            cheapest, fewest = route_costs(case)
            if any(fewest[t] is not None and fewest[t] > cheapest[t] for t in targets_of(case)):
                route_gap.append(case_id)
        if tier in ("M", "L"):
            ratios.append(Fraction(len(case["safety_rules"]), case["row"]["safety_vars"]))

    if len(greedy_not_optimal) < 5:
        e.append("variety 1: greedy by value/kg is not optimal in only %d tier-S cases (need 5)"
                 % len(greedy_not_optimal))
    if len(route_gap) < 5:
        e.append("variety 2: fewest-road routes cost more than cheapest in only %d tier-S cases (need 5)"
                 % len(route_gap))
    low = sum(1 for r in ratios if r < Fraction(7, 2))
    middle = sum(1 for r in ratios if Fraction(7, 2) <= r <= Fraction(24, 5))
    high = sum(1 for r in ratios if r > Fraction(24, 5))
    if len(ratios) != 26 or any(r < Fraction(5, 2) or r > 6 for r in ratios):
        e.append("variety 3: rules per switch must lie in 2.5..6.0 in all 26 tier M/L cases")
    if low < 5 or middle < 8 or high < 5:
        e.append("variety 3: ratio bands are %d below 3.5, %d in 3.5..4.8, %d above 4.8 (need 5/8/5)"
                 % (low, middle, high))

    seen = {}
    for case_id in sorted(cases):
        for name, size, content in module_fingerprints(cases[case_id]):
            if size < 8:
                continue
            key = (name, content)
            if key in seen:
                e.append("variety 4: cases %s and %s are equal in module %s" % (seen[key], case_id, name))
            else:
                seen[key] = case_id
    summary = ("greedy not optimal in %d tier-S cases; route gap in %d tier-S cases; "
               "safety ratio bands %d/%d/%d" % (len(greedy_not_optimal), len(route_gap), low, middle, high))
    return e, summary


# ====================================================================== V8

def monotone(values):
    up = all(values[i] <= values[i + 1] for i in range(len(values) - 1))
    down = all(values[i] >= values[i + 1] for i in range(len(values) - 1))
    return up or down


def longest_periodic_segment(text, max_period):
    """Longest contiguous piece of text that repeats a block of length <= max_period."""
    best = 0
    for b in range(1, max_period + 1):
        run = 0
        for i in range(b, len(text)):
            if text[i] == text[i - b]:
                run += 1
                best = max(best, run + b)
            else:
                run = 0
    return best


def prefix_matches(text, pattern):
    """Start positions 0..N-m where the first m-1 symbols of the pattern match."""
    prefix = pattern[:-1]
    count = 0
    for i in range(len(text) - len(pattern) + 1):
        if text.startswith(prefix, i):
            count += 1
    return count


def check_v8(case, case_no):
    """V8: the trap rules of cases 46 to 49."""
    e = []
    crates = case["crates"]
    if case_no == 46:
        if not (1500 <= len(crates) <= 3000):
            e.append("trap 46: needs 1500..3000 crates, found %d" % len(crates))
        monotone_fields = []
        for field in ("value", "weight", "expiry", "serial"):
            if monotone([c[field] for c in crates]):
                monotone_fields.append(field)
        ratios = [Fraction(c["value"], c["weight"]) for c in crates]
        if monotone(ratios):
            monotone_fields.append("value-per-kg")
        if len(monotone_fields) < 3:
            e.append("trap 46: only %s are monotone in crate_id order (need 3)" % monotone_fields)
    elif case_no == 47:
        if not (12 <= len(crates) <= 60):
            e.append("trap 47: needs 12..60 crates, found %d" % len(crates))
        capacity = case["row"]["capacity"]
        greedy = greedy_by_ratio(crates, capacity)
        best = knapsack_dp(crates, capacity)
        if 10 * greedy > 6 * best:
            e.append("trap 47: greedy reaches %d of optimum %d (more than 60%%)" % (greedy, best))
    elif case_no == 48:
        V = len(case["locations"])
        if not (1500 <= V <= 3000):
            e.append("trap 48: needs 1500..3000 locations, found %d" % V)
        adj = neighbours_of(V, case["roads"])
        first = hop_distances(adj, 0)
        far = first.index(max(first))
        longest = max(hop_distances(adj, far))
        if longest < 500:
            e.append("trap 48: longest distance found is %d roads (need 500)" % longest)
        cheapest, fewest = route_costs(case)
        if not any(fewest[t] is not None and 2 * fewest[t] >= 3 * cheapest[t] for t in targets_of(case)):
            e.append("trap 48: no target where every fewest-road route costs >= 1.5 x cheapest")
    elif case_no == 49:
        log = full_log(case)
        N = len(log)
        if not (50000 <= N <= 100000):
            e.append("trap 49: log has %d symbols (need 50000..100000)" % N)
        if 10 * longest_periodic_segment(log, 8) < 9 * N:
            e.append("trap 49: less than 90% of the log repeats one block of <= 8 symbols")
        near_misses = 0
        for p in case["radio_patterns"]:
            m = len(p["pattern"])
            if 2 * prefix_matches(log, p["pattern"]) >= N - m + 1:
                near_misses += 1
        if near_misses < 4:
            e.append("trap 49: only %d patterns have prefix matches at half of the start positions"
                     % near_misses)
    return e
