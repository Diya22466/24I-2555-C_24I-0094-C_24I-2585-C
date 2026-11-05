"""Sites and planted tour, pipeline, drum prices, sensors, safety rules, rations.

Data for modules G, H and I. Every planted object is valid by construction.
"""


# ---------- sites and the planted tour ----------

def make_sites(rng, n):
    seen = set()
    sites = []
    while len(sites) < n:
        x, y = rng.randint(0, 999), rng.randint(0, 999)
        if (x, y) not in seen:
            seen.add((x, y))
            sites.append({"site_no": len(sites), "x": x, "y": y})
    return sites


def manhattan(a, b):
    return abs(a["x"] - b["x"]) + abs(a["y"] - b["y"])


def tour_length(sites, order):
    total = 0
    for i in range(len(order)):
        total += manhattan(sites[order[i]], sites[order[(i + 1) % len(order)]])
    return total


def nearest_neighbour_tour(sites):
    """From site 0, always go to the nearest unvisited site (ties: smaller site_no)."""
    order = [0]
    visited = [False] * len(sites)
    visited[0] = True
    for step in range(len(sites) - 1):
        current = sites[order[-1]]
        best = None
        for site in sites:
            if not visited[site["site_no"]]:
                if best is None or manhattan(current, site) < manhattan(current, best):
                    best = site
        order.append(best["site_no"])
        visited[best["site_no"]] = True
    return order


def two_opt(sites, order, max_passes):
    """Reverse a segment whenever that makes the closed tour shorter. Site 0 stays first."""
    n = len(order)
    dist = [[manhattan(a, b) for b in sites] for a in sites]
    for p in range(max_passes):
        improved = False
        for i in range(n - 2):
            for j in range(i + 2, n if i > 0 else n - 1):
                a, b = order[i], order[i + 1]
                c, d = order[j], order[(j + 1) % n]
                if dist[a][c] + dist[b][d] < dist[a][b] + dist[c][d]:
                    order[i + 1:j + 1] = reversed(order[i + 1:j + 1])
                    improved = True
        if not improved:
            break
    return order


def make_tour(sites):
    """Planted tour = nearest-neighbour tour improved by 2-opt.

    2-opt only accepts shorter tours, so the result is never longer than the
    nearest-neighbour tour (required on tiers L and X).
    """
    order = two_opt(sites, nearest_neighbour_tour(sites), max_passes=8)
    tour = []
    for step in range(len(order)):
        tour.append({"step": step, "site_no": order[step]})
    return tour, tour_length(sites, order)


# ---------- pipeline and drum ----------

def make_pipeline(rng, n_stages):
    dims = []
    for idx in range(n_stages + 1):
        dims.append({"idx": idx, "dim": rng.randint(2, 100)})
    return dims


def make_drum_prices(rng, L):
    """Price grows with length but with noise, capped at 500, never all proportional."""
    per_unit = rng.uniform(0.6, 1.0) * 500 / L
    prices = []
    for length in range(1, L + 1):
        price = round(per_unit * length * rng.uniform(0.75, 1.25))
        prices.append({"length": length, "price": max(1, min(500, price))})
    proportional = True
    for item in prices:
        if item["price"] != prices[0]["price"] * item["length"]:
            proportional = False
    if proportional:
        prices[0]["price"] += 1
    return prices


# ---------- sensors and the planted cover ----------

def make_sensors(rng, n, tier):
    share = {"S": (0.25, 0.45), "M": (0.20, 0.40)}.get(tier, (0.10, 0.30))
    k = round(n * rng.uniform(*share))
    k = max(2, min(n // 2, k))
    cover = sorted(rng.sample(range(n), k))
    in_cover = [False] * n
    for node in cover:
        in_cover[node] = True

    edge_set = set()

    def add(u, v):
        if u != v:
            edge_set.add((min(u, v), max(u, v)))

    # Every node outside the cover gets one edge into the cover.
    for node in range(n):
        if not in_cover[node]:
            add(node, rng.choice(cover))
    # More edges, each with at least one end in the cover (so the cover touches all).
    max_edges = k * (k - 1) // 2 + k * (n - k)
    target = min(max_edges, max(n - 1, round(n * rng.uniform(1.2, 2.2))))
    while len(edge_set) < target:
        add(rng.choice(cover), rng.randint(0, n - 1))

    edges = []
    for u, v in sorted(edge_set):
        edges.append({"u": u, "v": v})
    return edges, [{"node": node} for node in cover]


# ---------- safety rules and the planted assignment ----------

def safety_ratio_range(case_no, tier):
    """Rules per switch. Tiers M and L cycle through three bands (variety rule 3)."""
    if tier in ("M", "L"):
        band = (case_no - 20) % 3
        return [(2.6, 3.4), (3.6, 4.7), (4.9, 5.9)][band]
    if tier == "X":
        return (3.6, 4.7)
    return (2.0, 6.0)


def make_safety(rng, n_vars, ratio_range):
    n_rules = round(n_vars * rng.uniform(*ratio_range))
    n_rules = max(2 * n_vars, min(6 * n_vars, n_rules))
    assignment = [rng.randint(0, 1) for i in range(n_vars + 1)]  # index 0 unused

    rules = []
    seen = set()
    while len(rules) < n_rules:
        switches = rng.sample(range(1, n_vars + 1), 3)
        lits = []
        for s in switches:
            lits.append(s if rng.random() < 0.5 else -s)
        # Make sure the planted assignment satisfies the rule: if no literal is
        # true, flip one literal so that it becomes true.
        satisfied = False
        for lit in lits:
            if (lit > 0 and assignment[lit] == 1) or (lit < 0 and assignment[-lit] == 0):
                satisfied = True
        if not satisfied:
            i = rng.randint(0, 2)
            lits[i] = -lits[i]
        key = tuple(sorted(lits))
        if key not in seen:
            seen.add(key)
            rules.append({"rule_no": len(rules) + 1, "lit_1": lits[0], "lit_2": lits[1],
                          "lit_3": lits[2]})

    planted = []
    for switch in range(1, n_vars + 1):
        planted.append({"switch": switch, "value": assignment[switch]})
    return rules, planted


# ---------- rations and the planted selection ----------

def make_rations(rng, n_items):
    values = [rng.randint(1, 1000) for i in range(n_items)]
    n_planted = rng.randint(max(1, n_items // 5), max(1, n_items // 2))
    planted = set(rng.sample(range(n_items), n_planted))
    rations = []
    target = 0
    for item in range(n_items):
        flag = 1 if item in planted else 0
        target += values[item] * flag
        rations.append({"item": item, "value": values[item], "planted": flag})
    return rations, target
