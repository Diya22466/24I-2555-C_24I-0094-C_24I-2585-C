# Generator (group 40)

## The one command

Run from the project folder (the folder that contains `generator/`):

```
python generator/main.py
```

It writes `cases.xlsx` (50 cases, 20 sheets) in the project folder in about 10 seconds.
The group seed is 40. Running it again gives exactly the same workbook
(checked cell by cell: 155,174 identical rows).

To write the file somewhere else: `python generator/main.py path/to/file.xlsx`.

## Files

| File | What it generates |
|---|---|
| `config.py` | seed 40, the 20 sheet headers, tier ranges, `tier_of`, `scenario_of`, `make_rng` |
| `main.py` | builds each case (calls the modules below) and writes the workbook |
| `crates.py` | crates and capacity (module A); traps 46 and 47 |
| `network.py` | locations, roads, closure waves, targets (modules B, F); trap 48 |
| `radio.py` | radio log, patterns, report pair and edit_bound (module E); trap 49 |
| `scheduling.py` | rescue windows (C) and alarms (D) |
| `planning.py` | sites and planted tour, pipeline, drum prices, sensor graph and planted cover, safety rules and planted assignment, rations and planted selection (G, H, I) |
| `claims.py` | exhaustive-search optima for the tier S claims sheet |

## How the randomness works

`make_rng(case_no, module)` returns `random.Random("40-<case_no>-<module>")`.
Every case and every module has its own stream, so changing one module (or one
case) never changes the numbers of any other. Retry loops (for example "redraw
the crates until greedy is not optimal") use the same stream, so they are
deterministic too.

## Libraries

Only the Python standard library and `openpyxl` (to write the .xlsx file).
`itertools.permutations` / `combinations` are used only to enumerate
possibilities in the exhaustive tier-S claims; `heapq` and `deque` are used
inside the small route checks that steer generation (variety rule 2). None of
this is an Iteration-2 decision module.
