"""Crates and truck capacity (module A data), including traps 46 and 47."""

import math

# Story rule per case study: these categories make up at least this share of crates.
# 0 Food, 1 Water, 2 Medicine, 3 Tool, 4 Rare.
CATEGORY_RULE = {
    1: ([0, 1], 0.62),     # Delta Flood: food and water matter most (signature >= 55%)
    2: ([2, 3], 0.52),     # Mountain Earthquake: medicine and tools (signature >= 45%)
    3: ([0, 1, 2], 0.50),  # Coastal Cyclone: no rule, mixed basic supplies
    4: ([4], 0.14),        # Urban Flash Flood: rare equipment available (signature >= 10%)
    5: ([0, 3], 0.45),     # Landslide Corridor: no rule, food and digging tools
    6: ([1, 2], 0.62),     # Outbreak Camp: medicine and water (signature >= 55%)
}

# Typical value and expiry hour range per category.
VALUE_RANGE = {0: (10, 50), 1: (10, 45), 2: (40, 100), 3: (25, 80), 4: (60, 100)}
EXPIRY_RANGE = {0: (24, 400), 1: (100, 999), 2: (150, 800), 3: (500, 999), 4: (300, 999)}

# Capacity as a share of the total crate weight (the PDF allows 10% to 70%).
CAPACITY_SHARE = {"S": (0.30, 0.60), "M": (0.20, 0.40), "L": (0.10, 0.25), "X": (0.10, 0.25)}


def make_categories(rng, n, main_cats, share):
    n_main = math.ceil(share * n)
    cats = []
    for i in range(n_main):
        cats.append(rng.choice(main_cats))
    for i in range(n - n_main):
        cats.append(rng.randint(0, 4))
    rng.shuffle(cats)
    return cats


def new_serials(rng, n):
    return rng.sample(range(10000000, 100000000), n)


def make_crates(rng, n, scenario):
    main_cats, share = CATEGORY_RULE[scenario]
    cats = make_categories(rng, n, main_cats, share)
    serials = new_serials(rng, n)
    crates = []
    for i in range(n):
        cat = cats[i]
        weight = rng.randint(1, 20)
        low, high = VALUE_RANGE[cat]
        # Heavier crates tend to be worth a bit more, so the knapsack is not trivial.
        value = rng.randint(low, high) + 2 * weight - 20
        value = max(10, min(100, value))
        expiry = rng.randint(*EXPIRY_RANGE[cat])
        crates.append({"crate_id": i + 1, "cat": cat, "weight": weight, "value": value,
                       "expiry": expiry, "serial": serials[i]})

    if scenario == 6:
        # Outbreak Camp: supplies spoil, so at least half expire by hour 300.
        spoiling = rng.sample(range(n), math.ceil(0.55 * n))
        for i in spoiling:
            crates[i]["expiry"] = rng.randint(24, 300)
    return crates


def make_capacity(rng, crates, tier):
    total = 0
    for crate in crates:
        total += crate["weight"]
    low_share, high_share = CAPACITY_SHARE[tier]
    capacity = round(total * rng.uniform(low_share, high_share))
    # Keep it inside 10% .. 70% of the total weight, and at least 1.
    capacity = max(capacity, (total + 9) // 10, 1)
    capacity = min(capacity, 7 * total // 10)
    return capacity


def make_dock_order_crates(rng, n):
    """Trap 46: the list is already sorted in four of the five fields.

    weight is non-increasing and value is non-decreasing, so value-per-kg is
    non-decreasing as well; serial is increasing. Only expiry is random.
    """
    weights = sorted([rng.randint(1, 20) for i in range(n)], reverse=True)
    values = sorted([rng.randint(10, 100) for i in range(n)])
    serials = sorted(new_serials(rng, n))
    crates = []
    for i in range(n):
        crates.append({"crate_id": i + 1, "cat": rng.randint(0, 4), "weight": weights[i],
                       "value": values[i], "expiry": rng.randint(0, 999), "serial": serials[i]})
    return crates


def make_greedy_trap_crates(rng):
    """Trap 47: greedy by value per kg reaches at most 60% of the optimum.

    Capacity is 40 kg. One light "decoy" crate has the best value per kg (> 5).
    Two to four 20 kg crates have value 100 (exactly 5 per kg). Every other crate
    has value per kg below 5 and is too heavy for the gap the decoy leaves.
    Greedy: decoy + one 20 kg crate = at most 120.  Optimum: two 20 kg crates = 200.
    """
    n = rng.randint(12, 18)
    decoy_weight = rng.randint(1, 3)
    decoy_value = rng.randint(5 * decoy_weight + 1, 20)
    decoy_value = max(decoy_value, 10)
    n_big = rng.randint(2, 4)

    items = [(2, decoy_weight, decoy_value)]  # (cat, weight, value)
    for i in range(n_big):
        items.append((1, 20, 100))
    while len(items) < n:
        weight = rng.randint(21 - decoy_weight, 20)
        value = rng.randint(10, min(100, 5 * weight - 1))
        items.append((rng.randint(0, 4), weight, value))
    rng.shuffle(items)

    serials = new_serials(rng, n)
    crates = []
    for i in range(n):
        cat, weight, value = items[i]
        crates.append({"crate_id": i + 1, "cat": cat, "weight": weight, "value": value,
                       "expiry": rng.randint(24, 999), "serial": serials[i]})
    return crates, 40
