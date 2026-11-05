"""Build the test workbooks in validator/tests/ from cases.xlsx.

Usage (from the project folder):   python validator/tests/make_broken.py

For three valid cases it writes one valid copy, then several broken copies,
each with exactly one deliberate corruption. manifest.csv lists every file with
the check that must reject it. The validator report shows each rejection.
"""

import csv
import os

from openpyxl import Workbook, load_workbook

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(os.path.dirname(HERE))


def read_case(path, case_id):
    """Rows of one case (or of all cases when case_id is None):
    {"order": [...], "headers": {...}, "rows": {sheet: [dict]}}."""
    workbook = load_workbook(path, read_only=True)
    data = {"order": list(workbook.sheetnames), "headers": {}, "rows": {}}
    for sheet in workbook.worksheets:
        values = sheet.iter_rows(values_only=True)
        header = list(next(values))
        data["headers"][sheet.title] = header
        data["rows"][sheet.title] = [dict(zip(header, cells)) for cells in values
                                     if case_id is None or cells[0] == case_id]
    workbook.close()
    return data


def copy_case(data):
    new = {"order": list(data["order"]), "headers": {}, "rows": {}}
    for name in data["order"]:
        new["headers"][name] = list(data["headers"][name])
        new["rows"][name] = [dict(row) for row in data["rows"][name]]
    return new


def write_case(data, path):
    workbook = Workbook(write_only=True)
    for name in data["order"]:
        sheet = workbook.create_sheet(name)
        header = data["headers"][name]
        sheet.append(header)
        original = list(data["rows"][name][0].keys()) if data["rows"][name] else header
        for row in data["rows"][name]:
            sheet.append([row[key] for key in original])
    workbook.save(path)


# ---------- corruptions (each returns nothing; it edits data in place) ----------

def crate_weight_25(d):
    d["rows"]["crates"][0]["weight"] = 25


def duplicate_crate_id(d):
    d["rows"]["crates"][1]["crate_id"] = d["rows"]["crates"][0]["crate_id"]


def road_to_missing_location(d):
    d["rows"]["roads"][0]["v"] = len(d["rows"]["locations"]) + 3


def road_closed_twice(d):
    waves = d["rows"]["waves"]
    copy = dict(waves[0])
    copy["wave_no"] = waves[-1]["wave_no"]
    waves.append(copy)


def disconnect_last_location(d):
    """Delete every road touching the last location, renumber roads and waves."""
    last = len(d["rows"]["locations"]) - 1
    kept = [r for r in d["rows"]["roads"] if r["u"] != last and r["v"] != last]
    new_number = {}
    for i in range(len(kept)):
        new_number[kept[i]["road_no"]] = i
        kept[i]["road_no"] = i
    d["rows"]["roads"] = kept
    waves = []
    for w in d["rows"]["waves"]:
        if w["road_no"] in new_number:
            w["road_no"] = new_number[w["road_no"]]
            waves.append(w)
    d["rows"]["waves"] = sorted(waves, key=lambda w: (w["wave_no"], w["road_no"]))


def wrong_pattern_count(d):
    d["rows"]["radio_patterns"][0]["count"] += 1


def wrong_cargo_claim(d):
    d["rows"]["claims"][0]["cargo_opt"] += 1


def edit_bound_below_distance(d):
    """report_b = report_a with its first 3 symbols replaced by a symbol absent from it."""
    report = d["rows"]["radio_reports"][0]
    a = report["report_a"]
    absent = [s for s in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" if s not in a][0]
    report["report_b"] = absent * 3 + a[3:]
    d["rows"]["cases"][0]["edit_bound"] = 1


def assignment_breaks_rule(d):
    rule = d["rows"]["safety_rules"][0]
    for lit in (rule["lit_1"], rule["lit_2"], rule["lit_3"]):
        for p in d["rows"]["safety_planted"]:
            if p["switch"] == abs(lit):
                p["value"] = 0 if lit > 0 else 1


def tour_length_plus_7(d):
    d["rows"]["cases"][0]["tour_length"] += 7


def delta_no_flooding(d):
    for loc in d["rows"]["locations"]:
        loc["penalty"] = 0


def header_renamed(d):
    d["headers"]["crates"][3] = "kg"


def window_500_minutes(d):
    w = d["rows"]["windows"][0]
    w["start"] = 0
    w["finish"] = 500


def cover_node_missing(d):
    d["rows"]["sensor_cover"][0]["node"] = d["rows"]["cases"][0]["sensor_nodes"] + 5


def wave_too_large(d):
    E = len(d["rows"]["roads"])
    limit = max(1, E // 4)
    closed = set(w["road_no"] for w in d["rows"]["waves"])
    first = [w for w in d["rows"]["waves"] if w["wave_no"] == 1]
    for road_no in range(E):
        if len(first) > limit:
            break
        if road_no not in closed:
            new = {"case_id": first[0]["case_id"], "wave_no": 1, "road_no": road_no}
            d["rows"]["waves"].append(new)
            first.append(new)
    d["rows"]["waves"].sort(key=lambda w: (w["wave_no"], w["road_no"]))


def edit_bound_too_large(d):
    report = d["rows"]["radio_reports"][0]
    d["rows"]["cases"][0]["edit_bound"] = len(report["report_a"]) + len(report["report_b"]) + 1


def ration_flag_flipped(d):
    item = d["rows"]["rations"][0]
    item["planted"] = 1 - item["planted"]


def landslide_hq_five_roads(d):
    roads = d["rows"]["roads"]
    linked = set()
    for r in roads:
        if r["u"] == 0:
            linked.add(r["v"])
    degree = len(linked)
    for v in range(1, len(d["rows"]["locations"])):
        if degree >= 5:
            break
        if v not in linked:
            roads.append({"case_id": roads[0]["case_id"], "road_no": len(roads), "u": 0, "v": v,
                          "minutes": 30, "cable": 30})
            degree += 1


def sheets_swapped(d):
    i, j = d["order"].index("sites"), d["order"].index("tour")
    d["order"][i], d["order"][j] = d["order"][j], d["order"][i]


def lowercase_in_log(d):
    part = d["rows"]["radio_log"][0]
    part["text"] = "a" + part["text"][1:]


def trap47_decoy_weakened(d):
    """Give the best value-per-kg crate a poor ratio; greedy then finds the optimum."""
    best = max(d["rows"]["crates"], key=lambda c: c["value"] / c["weight"])
    best["weight"] = 3
    best["value"] = 10


def trap47_too_many_crates(d):
    crates = d["rows"]["crates"]
    for i in range(50):
        crates.append({"case_id": crates[0]["case_id"], "crate_id": len(crates) + 1, "cat": 0,
                       "weight": 1, "value": 10, "expiry": 500, "serial": 11000000 + i})


def tour_not_better_than_nn(d):
    """Visit sites in site_no order and store that tour's true length."""
    sites = d["rows"]["sites"]
    total = 0
    for i in range(len(sites)):
        a, b = sites[i], sites[(i + 1) % len(sites)]
        total += abs(a["x"] - b["x"]) + abs(a["y"] - b["y"])
    for i in range(len(d["rows"]["tour"])):
        d["rows"]["tour"][i]["site_no"] = i
    d["rows"]["cases"][0]["tour_length"] = total


def all_alarms_at_tick_0(d):
    for alarm in d["rows"]["incidents"]:
        alarm["tick"] = 0


def too_few_safety_rules(d):
    n_vars = d["rows"]["cases"][0]["safety_vars"]
    d["rows"]["safety_rules"] = d["rows"]["safety_rules"][:n_vars]


def windows_copied_between_cases(d):
    """Full workbook: case 40-27 gets exactly the windows of case 40-21 (variety rule 4)."""
    copied = []
    for w in d["rows"]["windows"]:
        if w["case_id"] == "40-21":
            new = dict(w)
            new["case_id"] = "40-27"
            copied.append(new)
    kept = [w for w in d["rows"]["windows"] if w["case_id"] != "40-27"]
    d["rows"]["windows"] = sorted(kept + copied, key=lambda w: (w["case_id"], w["window_id"]))


TESTS = [
    ("40-00", [
        (crate_weight_25, "V2", "crate weight 25 kg (allowed 1..20)"),
        (duplicate_crate_id, "V3", "two crates share crate_id"),
        (road_to_missing_location, "V3", "a road ends at a location that does not exist"),
        (road_closed_twice, "V4", "one road appears in two waves (waves not disjoint)"),
        (disconnect_last_location, "V4", "all roads of the last location removed (network not connected)"),
        (wrong_pattern_count, "V5", "pattern 0 count increased by 1"),
        (wrong_cargo_claim, "V5", "claim cargo_opt increased by 1"),
        (edit_bound_below_distance, "V5", "edit_bound 1 although report_b needs 3 edits"),
        (assignment_breaks_rule, "V6", "planted safety assignment makes rule 1 false"),
        (tour_length_plus_7, "V6", "tour_length does not match the planted tour"),
        (delta_no_flooding, "V7", "Delta Flood signature broken: no location has penalty >= 2"),
        (header_renamed, "V1", "crates header 'weight' renamed to 'kg'"),
    ]),
    ("40-04", [
        (window_500_minutes, "V2", "a window lasts 500 minutes (allowed 5..480)"),
        (lowercase_in_log, "V2", "radio log contains a lowercase symbol"),
        (cover_node_missing, "V3", "a cover node does not exist in the sensor graph"),
        (wave_too_large, "V4", "wave 1 has more than max(1, floor(E/4)) roads"),
        (edit_bound_too_large, "V5", "edit_bound larger than len(report_a) + len(report_b)"),
        (ration_flag_flipped, "V6", "planted rations no longer add up to rations_target"),
        (landslide_hq_five_roads, "V7", "Landslide signature broken: HQ gets 5 roads"),
        (sheets_swapped, "V1", "sheets 'sites' and 'tour' swapped"),
    ]),
    ("40-47", [
        (trap47_decoy_weakened, "V8", "trap 47 broken: the decoy crate loses its high value per kg"),
        (trap47_too_many_crates, "V8", "trap 47 broken: 67 crates (allowed 12..60)"),
        (tour_not_better_than_nn, "V6", "tier X tour longer than the nearest-neighbour tour"),
        (all_alarms_at_tick_0, "V2", "all alarms at tick 0 (alarms per tick far above 1.8)"),
        (too_few_safety_rules, "V2", "only 1 safety rule per switch (allowed 2.0..6.0)"),
    ]),
]


def main():
    source = os.path.join(PROJECT, "cases.xlsx")
    for name in os.listdir(HERE):
        if name.endswith(".xlsx"):
            os.remove(os.path.join(HERE, name))
    manifest = []

    # One broken copy of the whole workbook, for the cross-case (variety) rules.
    broken = read_case(source, None)
    windows_copied_between_cases(broken)
    file_name = "broken_full_01_windows_copied_between_cases.xlsx"
    write_case(broken, os.path.join(HERE, file_name))
    manifest.append({"file": file_name, "mode": "full", "expected": "V7",
                     "description": "full workbook; case 40-27 has the same windows as 40-21 (variety rule 4)"})

    for case_id, corruptions in TESTS:
        original = read_case(source, case_id)
        valid_name = "valid_%s.xlsx" % case_id
        write_case(original, os.path.join(HERE, valid_name))
        manifest.append({"file": valid_name, "mode": "subset", "expected": "ACCEPT",
                         "description": "unchanged copy of case %s" % case_id})
        number = 1
        for corrupt, expected, description in corruptions:
            broken = copy_case(original)
            corrupt(broken)
            file_name = "broken_%s_%02d_%s.xlsx" % (case_id, number, corrupt.__name__)
            write_case(broken, os.path.join(HERE, file_name))
            manifest.append({"file": file_name, "mode": "subset", "expected": expected,
                             "description": description})
            number += 1
    with open(os.path.join(HERE, "manifest.csv"), "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["file", "mode", "expected", "description"])
        writer.writeheader()
        writer.writerows(manifest)
    print("wrote %d test workbooks to %s" % (len(manifest), HERE))


if __name__ == "__main__":
    main()
