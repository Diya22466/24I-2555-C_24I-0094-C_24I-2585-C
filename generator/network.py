"""Locations, roads and closure waves (modules B and F data), including trap 48."""

import heapq
import math
from collections import deque

from config import PENALTIES

# Per case study: network shape, average degree range (2E/V), minutes per road, number of waves.
NETWORK_PROFILE = {
    1: ("local", (2.3, 3.0), (5, 40), (3, 5)),     # Delta: villages joined by raised roads
    2: ("tree", (2.0, 2.5), (10, 60), (2, 4)),     # Earthquake: few roads, almost no alternatives
    3: ("hub", (2.4, 3.2), (3, 30), (3, 5)),       # Cyclone: port city hub and fishing villages
    4: ("grid", (3.6, 4.6), (1, 15), (2, 5)),      # Urban: dense street grid, many alternatives
    5: ("highway", (2.0, 2.3), (10, 60), (3, 5)),  # Landslide: one highway along a gorge
    6: ("local", (2.2, 3.0), (1, 10), (2, 4)),     # Outbreak: compact camp paths
}

# Share of locations that are shelters (S), hospitals (H) and extra depots (D).
TYPE_SHARE = {1: (0.30, 0.10, 0.03), 2: (0.20, 0.12, 0.03), 3: (0.32, 0.08, 0.04),
              4: (0.22, 0.12, 0.05), 5: (0.22, 0.08, 0.03), 6: (0.25, 0.15, 0.05)}

# Penalty choices per case study (repeated values are more likely). Delta Flood is special.
PENALTY_CHOICES = {2: [0, 1, 1, 2, 2, 4, 6], 3: [0, 0, 1, 2, 4], 4: [0, 0, 0, 1, 1, 2],
                   5: [0, 1, 2, 4, 6], 6: [0, 0, 1, 1, 2]}


# ---------- building the road graph ----------

def pick_edge_count(rng, V, degree_range):
    low = max(V - 1, math.ceil(degree_range[0] * V / 2))
    high = min(3 * V, math.floor(degree_range[1] * V / 2), V * (V - 1) // 2)
    return rng.randint(low, high)


def tree_parent(rng, shape, node, V, degree):
    """Parent of a new node in the spanning tree; the shape gives the story."""
    if shape == "local":
        return rng.randint(max(0, node - 3), node - 1)
    if shape == "hub":
        hubs = max(2, V // 25)
        if rng.random() < 0.5:
            return rng.randint(0, min(node, hubs) - 1)
        return rng.randint(0, node - 1)
    if shape == "grid":
        width = math.ceil(math.sqrt(V))
        options = []
        if node % width > 0:
            options.append(node - 1)
        if node >= width:
            options.append(node - width)
        return rng.choice(options)
    if shape == "highway":
        highway_end = math.ceil(0.6 * V)
        if node < highway_end:
            return node - 1
        while True:
            parent = rng.randint(0, node - 1)
            if degree[parent] < 4:
                return parent
    return rng.randint(0, node - 1)  # "tree"


def grid_candidates(V):
    width = math.ceil(math.sqrt(V))
    pairs = []
    for node in range(V):
        col = node % width
        if col < width - 1 and node + 1 < V:
            pairs.append((node, node + 1))
        if node + width < V:
            pairs.append((node, node + width))
        if col < width - 1 and node + width + 1 < V:
            pairs.append((node, node + width + 1))
        if col > 0 and node + width - 1 < V:
            pairs.append((node, node + width - 1))
    return pairs


def extra_pair(rng, shape, V, neighbours):
    """A candidate extra road (creates a cycle, i.e. an alternative route)."""
    if shape in ("local", "grid"):
        u = rng.randint(0, V - 1)
        return u, min(V - 1, u + rng.randint(2, 5))
    if shape == "hub":
        return rng.randint(0, max(2, V // 25) - 1), rng.randint(0, V - 1)
    if shape == "highway":
        # A short local loop next to a side-valley node (never highway to highway).
        u = rng.randint(math.ceil(0.6 * V), V - 1)
        middle = rng.choice(neighbours[u])
        return u, rng.choice(neighbours[middle])
    return rng.randint(0, V - 1), rng.randint(0, V - 1)


def build_edges(rng, V, E, shape):
    max_degree = 4 if shape == "highway" else V
    edges = []
    edge_set = set()
    degree = [0] * V
    neighbours = [[] for i in range(V)]

    def add(u, v):
        if u == v:
            return
        if u > v:
            u, v = v, u
        if (u, v) in edge_set or degree[u] >= max_degree or degree[v] >= max_degree:
            return
        edges.append((u, v))
        edge_set.add((u, v))
        degree[u] += 1
        degree[v] += 1
        neighbours[u].append(v)
        neighbours[v].append(u)

    # 1) A spanning tree, so the network is connected before any closure.
    for node in range(1, V):
        add(tree_parent(rng, shape, node, V, degree), node)

    # 2) Extra roads up to E.
    if shape == "grid":
        candidates = grid_candidates(V)
        rng.shuffle(candidates)
        for u, v in candidates:
            if len(edges) >= E:
                break
            add(u, v)
    attempts = 0
    while len(edges) < E and attempts < 200 * E:
        attempts += 1
        u, v = extra_pair(rng, shape, V, neighbours)
        add(u, v)
    # Very small graphs: fill from all pairs if random picks were not enough.
    for u in range(V):
        for v in range(u + 1, V):
            if len(edges) < E:
                add(u, v)
    return edges


def make_roads(rng, edges, minutes_range):
    rng.shuffle(edges)
    roads = []
    for road_no in range(len(edges)):
        u, v = edges[road_no]
        minutes = rng.randint(*minutes_range)
        cable = round(minutes * rng.uniform(0.8, 2.0)) + rng.randint(0, 10)
        roads.append({"road_no": road_no, "u": u, "v": v, "minutes": minutes,
                      "cable": max(1, min(100, cable))})
    return roads


def make_locations(rng, V, scenario):
    s_share, h_share, d_share = TYPE_SHARE[scenario]
    n_shelters = max(1, math.ceil(s_share * V))
    n_hospitals = max(1, round(h_share * V))
    n_depots = round(d_share * V)
    types = ["S"] * n_shelters + ["H"] * n_hospitals + ["D"] * n_depots
    types += ["J"] * (V - 1 - len(types))
    rng.shuffle(types)
    types = ["D"] + types  # location 0 is the HQ

    penalties = [0]
    if scenario == 1:
        # Delta Flood: at least 40% of locations are flooded (penalty 2 or more).
        flooded = set(rng.sample(range(1, V), math.ceil(0.45 * V)))
        for loc in range(1, V):
            if loc in flooded:
                penalties.append(rng.choice([2, 4, 6]))
            else:
                penalties.append(rng.choice([0, 1]))
    else:
        for loc in range(1, V):
            penalties.append(rng.choice(PENALTY_CHOICES[scenario]))

    locations = []
    for loc in range(V):
        locations.append({"loc_id": loc, "type": types[loc], "penalty": penalties[loc]})
    return locations


def make_waves(rng, E, n_waves, forced_road=None, excluded=()):
    """Disjoint closure waves, each with 1 .. max(1, E // 4) roads."""
    size_limit = max(1, min(max(1, E // 4), E // 20))
    order = []
    for road_no in range(E):
        if road_no not in excluded and road_no != forced_road:
            order.append(road_no)
    rng.shuffle(order)
    if forced_road is not None:
        order.insert(0, forced_road)
    waves = []
    pos = 0
    for wave_no in range(1, n_waves + 1):
        size = rng.randint(1, size_limit)
        for road_no in sorted(order[pos:pos + size]):
            waves.append({"wave_no": wave_no, "road_no": road_no})
        pos += size
    return waves


# ---------- route helpers used while generating ----------

def adjacency(V, roads, skip=()):
    adj = [[] for i in range(V)]
    for road in roads:
        if road["road_no"] in skip:
            continue
        adj[road["u"]].append((road["v"], road["minutes"]))
        adj[road["v"]].append((road["u"], road["minutes"]))
    return adj


def bfs_hops(V, adj, source=0):
    hops = [-1] * V
    hops[source] = 0
    queue = deque([source])
    while queue:
        u = queue.popleft()
        for v, minutes in adj[u]:
            if hops[v] == -1:
                hops[v] = hops[u] + 1
                queue.append(v)
    return hops


def cheapest_costs(V, adj, penalties, source=0):
    cost = [None] * V
    cost[source] = 0
    heap = [(0, source)]
    while heap:
        c, u = heapq.heappop(heap)
        if c > cost[u]:
            continue
        for v, minutes in adj[u]:
            new_cost = c + minutes + penalties[v]
            if cost[v] is None or new_cost < cost[v]:
                cost[v] = new_cost
                heapq.heappush(heap, (new_cost, v))
    return cost


def fewest_road_costs(V, adj, penalties, hops):
    """Cheapest cost among the routes that use the fewest roads (one per node)."""
    order = sorted([v for v in range(V) if hops[v] >= 0], key=lambda v: hops[v])
    cost = [None] * V
    cost[order[0]] = 0
    for u in order:
        for v, minutes in adj[u]:
            if hops[v] == hops[u] + 1:
                new_cost = cost[u] + minutes + penalties[v]
                if cost[v] is None or new_cost < cost[v]:
                    cost[v] = new_cost
    return cost


def route_gap_targets(V, roads, locations):
    """Shelters/hospitals whose fewest-road routes all cost more than a cheapest route."""
    penalties = [loc["penalty"] for loc in locations]
    adj = adjacency(V, roads)
    hops = bfs_hops(V, adj)
    cheapest = cheapest_costs(V, adj, penalties)
    fewest = fewest_road_costs(V, adj, penalties, hops)
    result = []
    for loc in locations:
        t = loc["loc_id"]
        if t != 0 and loc["type"] in ("S", "H") and fewest[t] > cheapest[t]:
            result.append(t)
    return result


def find_cut_road(V, roads, target):
    """A road whose closure makes the target unreachable from the HQ, or None."""
    # Walk the BFS path from the target back to the HQ and test each road on it.
    adj_roads = [[] for i in range(V)]
    for road in roads:
        adj_roads[road["u"]].append((road["v"], road["road_no"]))
        adj_roads[road["v"]].append((road["u"], road["road_no"]))
    parent = [None] * V
    parent[0] = (0, -1)
    queue = deque([0])
    while queue:
        u = queue.popleft()
        for v, road_no in adj_roads[u]:
            if parent[v] is None:
                parent[v] = (u, road_no)
                queue.append(v)
    node = target
    while node != 0:
        prev, road_no = parent[node]
        if bfs_hops(V, adjacency(V, roads, skip={road_no}))[target] == -1:
            return road_no
        node = prev
    return None


def choose_targets(rng, locations, first=None):
    candidates = [loc["loc_id"] for loc in locations if loc["type"] in ("S", "H")]
    if first is not None:
        candidates.remove(first)
        return [first] + rng.sample(candidates, 2)
    return rng.sample(candidates, 3)


# ---------- the network of one case ----------

def make_network(rng, V, scenario, need_route_gap):
    shape, degree_range, minutes_range, wave_range = NETWORK_PROFILE[scenario]
    for attempt in range(500):
        E = pick_edge_count(rng, V, degree_range)
        edges = build_edges(rng, V, E, shape)
        if len(edges) != E:
            continue
        locations = make_locations(rng, V, scenario)
        roads = make_roads(rng, edges, minutes_range)
        n_waves = rng.randint(*wave_range)

        if scenario == 5:
            # Landslide: farthest location at least floor(V/4) roads away, and
            # the closures must cut at least one target off from the HQ.
            if max(bfs_hops(V, adjacency(V, roads))) < V // 4:
                continue
            first, cut_road = None, None
            candidates = [loc["loc_id"] for loc in locations if loc["type"] in ("S", "H")]
            rng.shuffle(candidates)
            for t in candidates:
                cut_road = find_cut_road(V, roads, t)
                if cut_road is not None:
                    first = t
                    break
            if first is None:
                continue
            targets = choose_targets(rng, locations, first)
            waves = make_waves(rng, E, n_waves, forced_road=cut_road)
            return locations, roads, waves, targets

        first = None
        if need_route_gap:
            gaps = route_gap_targets(V, roads, locations)
            if not gaps:
                continue
            first = rng.choice(gaps)
        targets = choose_targets(rng, locations, first)
        waves = make_waves(rng, E, n_waves)
        return locations, roads, waves, targets
    raise RuntimeError("could not build a network for scenario %d" % scenario)


def make_trap48_network(rng):
    """Trap 48: a very long delta chain, and a target whose fewest-road route is expensive.

    Backbone 0 - 1 - ... - (P-1) with P >= 550, so two locations are >= 549 roads apart.
    Villages hang off backbone nodes and only link inside their own group, so they
    never shorten the backbone. Near the HQ: 0-a-t is 2 roads but costs 126 + p(t);
    0-b-c-t is 3 roads and costs 3 + p(t).
    """
    V = rng.randint(1500, 3000)
    P = rng.randint(550, 700)
    a, b, c, t = P, P + 1, P + 2, P + 3

    edges = []
    for i in range(P - 1):
        edges.append((i, i + 1))
    groups = []
    for i in range(P):
        groups.append([i])
    for node in range(P + 4, V):
        group = groups[rng.randint(0, P - 1)]
        edges.append((rng.choice(group), node))
        group.append(node)

    edge_set = set(edges)
    E_villages = round(V * rng.uniform(1.2, 1.4)) - 5
    attempts = 0
    while len(edges) < E_villages and attempts < 100 * V:
        attempts += 1
        group = groups[rng.randint(0, P - 1)]
        if len(group) < 3:
            continue
        u, v = rng.sample(group, 2)
        if u > v:
            u, v = v, u
        if (u, v) not in edge_set:
            edges.append((u, v))
            edge_set.add((u, v))

    roads = make_roads(rng, edges, (5, 40))
    gadget = [(0, a, 60), (a, t, 60), (0, b, 1), (b, c, 1), (c, t, 1)]
    gadget_roads = set()
    for u, v, minutes in gadget:
        gadget_roads.add(len(roads))
        roads.append({"road_no": len(roads), "u": u, "v": v, "minutes": minutes,
                      "cable": rng.randint(1, 100)})

    locations = make_locations(rng, V, 1)
    locations[a] = {"loc_id": a, "type": "J", "penalty": 6}
    locations[b] = {"loc_id": b, "type": "J", "penalty": 0}
    locations[c] = {"loc_id": c, "type": "J", "penalty": 0}
    locations[t] = {"loc_id": t, "type": "H", "penalty": rng.choice(PENALTIES)}

    targets = choose_targets(rng, locations, t)
    waves = make_waves(rng, len(roads), rng.randint(3, 5), excluded=gadget_roads)
    return locations, roads, waves, targets
