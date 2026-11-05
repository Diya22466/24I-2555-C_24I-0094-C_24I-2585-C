"""LIFELINE validator, group 40.

Usage (from the project folder):
    python validator/main.py                    validate cases.xlsx and every broken copy in
                                                validator/tests/, write validation_report.txt
    python validator/main.py FILE.xlsx          validate one workbook with all 50 cases
    python validator/main.py FILE.xlsx --subset validate a workbook holding only some cases
"""

import csv
import os
import sys
import zipfile

from openpyxl import load_workbook

import checks

CHECK_NAMES = {
    "V1": "20 sheets and headers, cell types, sort order, case ids, tier and scenario",
    "V2": "every size and value inside its range",
    "V3": "identifiers unique / consecutive, every reference exists",
    "V4": "network connected before closures, waves disjoint and within size limit",
    "V5": "pattern counts, edit_bound, log parts, tier-S claims",
    "V6": "planted tour and length, cover, safety assignment, ration selection",
    "V7": "signature rules of cases 0-45 and the variety rules",
    "V8": "trap rules of cases 46-49",
}

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = os.path.join(PROJECT, "validator", "tests")


def load_book(path):
    """Read every sheet. Rows become dicts keyed by the expected column names."""
    book = {"names": [], "headers": {}, "rows": {}, "file_problems": []}
    expected = dict(checks.SHEETS)
    workbook = load_workbook(path, read_only=True)
    book["names"] = list(workbook.sheetnames)
    for sheet in workbook.worksheets:
        values = sheet.iter_rows(values_only=True)
        header = list(next(values, ()))
        while header and header[-1] is None:
            header.pop()
        book["headers"][sheet.title] = header
        columns = expected.get(sheet.title, header)
        rows = []
        line = 1
        for cells in values:
            line += 1
            if all(cell is None for cell in cells):
                book["file_problems"].append("sheet %s row %d is empty" % (sheet.title, line))
                continue
            if any(cell is not None for cell in cells[len(columns):]):
                book["file_problems"].append("sheet %s row %d has extra cells" % (sheet.title, line))
            row = {}
            for i in range(len(columns)):
                row[columns[i]] = cells[i] if i < len(cells) else None
            rows.append(row)
        book["rows"][sheet.title] = rows
    workbook.close()

    # Formulas and merged cells are visible in the raw sheet XML.
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if name.startswith("xl/worksheets/sheet"):
                xml = archive.read(name).decode("utf-8")
                if "<f>" in xml or "<f " in xml:
                    book["file_problems"].append("%s contains formulas" % name)
                if "<mergeCell " in xml:
                    book["file_problems"].append("%s contains merged cells" % name)
    return book


def split_cases(book):
    cases = {}
    for row in book["rows"].get("cases", []):
        case = {}
        for name, header in checks.SHEETS:
            case[name] = []
        case["row"] = row
        cases[row["case_id"]] = case
    for name, header in checks.SHEETS[1:]:
        for row in book["rows"].get(name, []):
            if row["case_id"] in cases:
                cases[row["case_id"]][name].append(row)
    return cases


def run_check(errors, tag, function, *args):
    """Run one check; malformed data that makes it crash counts as a failure."""
    try:
        for message in function(*args):
            errors.append((tag, message))
    except Exception as problem:
        errors.append((tag, "could not be checked, data is malformed (%s: %s)"
                       % (type(problem).__name__, problem)))


def validate(path, full):
    """Returns the printed lines and True when the workbook is accepted."""
    book = load_book(path)
    lines = []
    book_errors = []
    run_check(book_errors, "V1", checks.check_book, book, full)

    cases = split_cases(book)
    case_errors = {}
    trap_cases_seen = False
    signature_cases_seen = False
    for case_id in sorted(cases):
        case = cases[case_id]
        errors = []
        run_check(errors, "V1", checks.check_v1_case, case, case_id)
        try:
            case_no = int(case_id.split("-")[1])
        except (IndexError, ValueError, AttributeError):
            case_errors[case_id] = errors
            continue
        tier = checks.expected_tier(case_no)
        scenario = case_no % 6 + 1
        run_check(errors, "V2", checks.check_v2, case, case_no, tier)
        run_check(errors, "V3", checks.check_v3, case)
        run_check(errors, "V4", checks.check_v4, case)
        run_check(errors, "V5", checks.check_v5, case, tier)
        run_check(errors, "V6", checks.check_v6, case, tier)
        if case_no <= 45:
            signature_cases_seen = True
            run_check(errors, "V7", checks.check_v7_signature, case, scenario, tier)
        else:
            trap_cases_seen = True
            run_check(errors, "V8", checks.check_v8, case, case_no)
        case_errors[case_id] = errors

    variety_errors = []
    variety_summary = ""
    if full:
        try:
            messages, variety_summary = checks.check_variety(cases)
            for message in messages:
                variety_errors.append(("V7", message))
        except Exception as problem:
            variety_errors.append(("V7", "variety could not be checked (%s)" % problem))

    # Summary per check.
    all_errors = book_errors + variety_errors
    for case_id in case_errors:
        all_errors += case_errors[case_id]
    failed = set(tag for tag, message in all_errors)
    lines.append("Workbook: %s" % os.path.relpath(path, PROJECT).replace(os.sep, "/"))
    lines.append("Mode: %s, %d case(s) found" % ("full (all 50 cases)" if full else "subset", len(cases)))
    for tag in sorted(CHECK_NAMES):
        if tag in failed:
            status = "FAIL"
        elif tag == "V8" and not trap_cases_seen:
            status = "N/A "
        else:
            status = "PASS"
        note = ""
        if tag == "V1" and not full:
            note = " (the 'exactly 50 cases' part: SKIP in subset mode)"
        if tag == "V7":
            if full:
                note = " [%s]" % variety_summary if variety_summary else ""
            elif signature_cases_seen:
                note = " (signatures checked; variety rules: SKIP in subset mode)"
            else:
                note = " (no case 0-45 in this file; variety rules: SKIP in subset mode)"
                if tag not in failed:
                    status = "N/A "
        if tag == "V8" and status == "N/A ":
            note = " (no trap case in this file)"
        lines.append("  %s %s  %s%s" % (status, tag, CHECK_NAMES[tag], note))

    for tag, message in book_errors + variety_errors:
        lines.append("  FAIL %s: %s" % (tag, message))
    lines.append("Per case:")
    for case_id in sorted(case_errors):
        errors = case_errors[case_id]
        if not errors:
            lines.append("  %s  PASS" % case_id)
        else:
            lines.append("  %s  FAIL" % case_id)
            for tag, message in errors[:8]:
                lines.append("        %s: %s" % (tag, message))
            if len(errors) > 8:
                lines.append("        ... %d more problems" % (len(errors) - 8))
    accepted = len(all_errors) == 0
    lines.append("RESULT: %s" % ("ACCEPTED" if accepted else "REJECTED (failed: %s)" % ", ".join(sorted(failed))))
    return lines, accepted, failed


def run_tests():
    """Validate every workbook listed in validator/tests/manifest.csv."""
    lines = []
    all_as_expected = True
    with open(os.path.join(TESTS, "manifest.csv"), newline="") as handle:
        tests = list(csv.DictReader(handle))
    for test in tests:
        path = os.path.join(TESTS, test["file"])
        result_lines, accepted, failed = validate(path, full=test["mode"] == "full")
        expected = test["expected"]
        if expected == "ACCEPT":
            ok = accepted
            verdict = "valid copy ACCEPTED as expected" if ok else "UNEXPECTED: valid copy rejected"
        else:
            ok = (not accepted) and expected in failed
            if ok:
                verdict = "broken copy REJECTED as expected (expected %s failure found)" % expected
            elif accepted:
                verdict = "UNEXPECTED: broken copy was accepted"
            else:
                verdict = "UNEXPECTED: rejected, but not by %s" % expected
        all_as_expected = all_as_expected and ok
        lines.append("-" * 78)
        lines.append("Test %s: %s" % (test["file"], test["description"]))
        lines.append(">> %s" % verdict)
        lines += result_lines
    return lines, all_as_expected, len(tests)


def main():
    arguments = [a for a in sys.argv[1:] if not a.startswith("--")]
    if arguments:
        lines, accepted, failed = validate(arguments[0], full="--subset" not in sys.argv)
        print("\n".join(lines))
        sys.exit(0 if accepted else 1)

    report = ["LIFELINE validation report - group %d" % checks.GROUP_SEED,
              "Generated by: python validator/main.py", "=" * 78,
              "PART 1. The submitted dataset", "=" * 78]
    lines, dataset_ok, failed = validate(os.path.join(PROJECT, "cases.xlsx"), full=True)
    report += lines
    report += ["", "=" * 78, "PART 2. Broken copies in validator/tests/ (each must be rejected)", "=" * 78]
    test_lines, tests_ok, n_tests = run_tests()
    report += test_lines
    report += ["=" * 78, "SUMMARY",
               "  Dataset cases.xlsx: %s" % ("PASS (all 50 cases accepted)" if dataset_ok else "FAIL"),
               "  Test workbooks: %d, all behaved as expected: %s" % (n_tests, "YES" if tests_ok else "NO")]
    text = "\n".join(report) + "\n"
    for target in (os.path.join(PROJECT, "validation_report.txt"),
                   os.path.join(PROJECT, "validator", "validation_report.txt")):
        with open(target, "w", newline="\n") as handle:
            handle.write(text)
    print(text)
    sys.exit(0 if dataset_ok and tests_ok else 1)


if __name__ == "__main__":
    main()
