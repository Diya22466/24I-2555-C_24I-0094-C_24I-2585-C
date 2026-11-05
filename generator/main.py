"""LIFELINE data generator, group 40.

Usage (from the project folder):   python generator/main.py
Writes cases.xlsx (50 cases, 20 sheets). The same seed always gives the same file.
"""

import os
import sys
import time

from openpyxl import Workbook

from config import GROUP_SEED, NUM_CASES, SHEETS, tier_of, scenario_of, ranges_of, make_rng
from crates import make_crates, make_capacity, make_dock_order_crates, make_greedy_trap_crates
from network import make_network, make_trap48_network
from radio import make_log, make_patterns, split_parts, make_reports, make_trap49_radio
from scheduling import make_windows, make_incidents
from planning import (make_sites, make_tour, make_pipeline, make_drum_prices, make_sensors,
                      safety_ratio_range, make_safety, make_rations)
from claims import best_cargo, greedy_cargo, best_windows, best_drum, shortest_tour, min_cover


def make_case(case_no):
    tier = tier_of(case_no)
    scenario = scenario_of(case_no)
    sizes = ranges_of(tier)
    case = {"case_id": "%d-%02d" % (GROUP_SEED, case_no)}

    # Module A: crates and capacity.
    rng = make_rng(case_no, "crates")
    if case_no == 46:
        crates = make_dock_order_crates(rng, rng.randint(1500, 3000))
        capacity = make_capacity(rng, crates, tier)
    elif case_no == 47:
        crates, capacity = make_greedy_trap_crates(rng)
    else:
        n_crates = rng.randint(*sizes["crates"])
        while True:
            crates = make_crates(rng, n_crates, scenario)
            capacity = make_capacity(rng, crates, tier)
            # Variety rule 1: on even tier-S cases, greedy by value/kg is not optimal.
            if tier != "S" or case_no % 2 == 1:
                break
            if greedy_cargo(crates, capacity) < best_cargo(crates, capacity):
                break
    case["crates"] = crates

    # Modules B and F: locations, roads, closure waves, targets.
    rng = make_rng(case_no, "network")
    if case_no == 48:
        locations, roads, waves, targets = make_trap48_network(rng)
    else:
        V = rng.randint(*sizes["locations"])
        # Variety rule 2 on tier-S cases whose story has alternative routes.
        need_route_gap = tier == "S" and scenario in (1, 3, 4, 6)
        locations, roads, waves, targets = make_network(rng, V, scenario, need_route_gap)
    case["locations"] = locations
    case["roads"] = roads
    case["waves"] = waves

    # Module E: radio log, patterns, reports.
    rng = make_rng(case_no, "radio")
    if case_no == 49:
        log, patterns = make_trap49_radio(rng)
    else:
        log = make_log(rng, scenario, rng.randint(*sizes["log"]))
        patterns = make_patterns(rng, log)
    case["radio_log"] = split_parts(rng, log, tier)
    case["radio_patterns"] = patterns
    report_a, report_b, edit_bound = make_reports(rng, scenario, sizes["report"])
    case["radio_reports"] = [{"report_a": report_a, "report_b": report_b}]

    # Modules C and D: rescue windows and alarms.
    rng = make_rng(case_no, "windows")
    case["windows"] = make_windows(rng, rng.randint(*sizes["windows"]), scenario)
    rng = make_rng(case_no, "incidents")
    case["incidents"] = make_incidents(rng, rng.randint(*sizes["alarms"]), tier, scenario)

    # Modules G, H, I: sites and tour, pipeline, drum, sensors, safety, rations.
    rng = make_rng(case_no, "sites")
    sites = make_sites(rng, rng.randint(*sizes["sites"]))
    tour, tour_len = make_tour(sites)
    case["sites"] = sites
    case["tour"] = tour

    rng = make_rng(case_no, "pipeline")
    case["pipeline_dims"] = make_pipeline(rng, rng.randint(*sizes["stages"]))
    rng = make_rng(case_no, "drum")
    case["drum_prices"] = make_drum_prices(rng, rng.randint(*sizes["drum"]))

    rng = make_rng(case_no, "sensors")
    n_sensors = rng.randint(*sizes["sensors"])
    sensor_edges, sensor_cover = make_sensors(rng, n_sensors, tier)
    case["sensor_edges"] = sensor_edges
    case["sensor_cover"] = sensor_cover

    rng = make_rng(case_no, "safety")
    n_vars = rng.randint(*sizes["safety_vars"])
    rules, planted = make_safety(rng, n_vars, safety_ratio_range(case_no, tier))
    case["safety_rules"] = rules
    case["safety_planted"] = planted

    rng = make_rng(case_no, "rations")
    rations, rations_target = make_rations(rng, rng.randint(*sizes["rations"]))
    case["rations"] = rations

    case["cases"] = [{
        "group_seed": GROUP_SEED, "case_no": case_no, "tier": tier, "scenario": scenario,
        "capacity": capacity, "target_0": targets[0], "target_1": targets[1],
        "target_2": targets[2], "edit_bound": edit_bound, "tour_length": tour_len,
        "sensor_nodes": n_sensors, "sensor_k": len(sensor_cover), "safety_vars": n_vars,
        "rations_target": rations_target,
    }]

    # Claims (tier S only): exhaustive-search optima.
    case["claims"] = []
    if tier == "S":
        window_count, window_value = best_windows(case["windows"])
        case["claims"].append({
            "cargo_opt": best_cargo(crates, capacity),
            "window_count_opt": window_count,
            "window_value_opt": window_value,
            "drum_opt": best_drum(case["drum_prices"]),
            "tour_opt": shortest_tour(sites),
            "cover_min": min_cover(n_sensors, sensor_edges),
        })
    return case


def write_workbook(all_cases, path):
    book = Workbook(write_only=True)
    for name, headers in SHEETS:
        sheet = book.create_sheet(name)
        sheet.append(headers)
        for case in all_cases:
            for item in case[name]:
                row = [case["case_id"]]
                for column in headers[1:]:
                    row.append(item[column])
                sheet.append(row)
    book.save(path)


def main():
    project = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(project, "cases.xlsx")
    all_cases = []
    for case_no in range(NUM_CASES):
        started = time.time()
        all_cases.append(make_case(case_no))
        print("case %02d  tier %s  scenario %d  (%.1f s)"
              % (case_no, tier_of(case_no), scenario_of(case_no), time.time() - started))
    write_workbook(all_cases, path)
    print("wrote", path)


if __name__ == "__main__":
    main()
