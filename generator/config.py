"""Fixed settings for the LIFELINE generator (group 40)."""

import random

GROUP_SEED = 40
NUM_CASES = 50

# The 20 sheets and their headers, in the exact order of Section 3.
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

# Size ranges per tier (Section 3). Tier X uses tier L unless its trap says otherwise.
TIER_RANGES = {
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

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
PATTERN_LENGTHS = [2, 4, 8, 12, 20, 40]
PENALTIES = [0, 1, 2, 4, 6]

SCENARIO_NAMES = {1: "Delta Flood", 2: "Mountain Earthquake", 3: "Coastal Cyclone",
                  4: "Urban Flash Flood", 5: "Landslide Corridor", 6: "Outbreak Camp"}


def tier_of(case_no):
    if case_no <= 19:
        return "S"
    if case_no <= 39:
        return "M"
    if case_no <= 45:
        return "L"
    return "X"


def scenario_of(case_no):
    # Also correct for the traps: 46 -> 5, 47 -> 6, 48 -> 1, 49 -> 2.
    return case_no % 6 + 1


def ranges_of(tier):
    if tier == "X":
        return TIER_RANGES["L"]
    return TIER_RANGES[tier]


def make_rng(case_no, module):
    """One independent random stream per (case, module), derived from the group seed.

    Changing one module or one case never changes the numbers of another.
    """
    return random.Random("%d-%d-%s" % (GROUP_SEED, case_no, module))
