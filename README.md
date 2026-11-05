# LIFELINE - Algorithmic Relief-Command Engine
## Iteration 1: data generation, validation and algorithm selection (Group 40)

| Member | Roll number |
|---|---|
| Hassan Tariq | 24i-2555 |
| Noah Faraz | 24i-2585 |
| Diya Hurmat | 24i-0094 |

Group seed: **40** (case ids `40-00` .. `40-49`).

## What is in this folder

```
cases.xlsx                 the dataset: 50 cases, 20 sheets (written by the generator, never edited)
generator/                 the generator (README.md has the one command)
validator/                 the validator: main.py, checks.py (V1-V8), validation_report.txt
validator/tests/           3 valid single-case copies, 25 broken copies, 1 broken full copy,
                           manifest.csv, make_broken.py (builds them from cases.xlsx)
validation_report.txt      output of the validator (same file as validator/validation_report.txt)
approach_note.pdf          approach note, 2 pages (approach.md has the same text)
proposal.pdf               algorithm-selection report, 2 pages
reports/                   source of the two reports (content.py = text, build_reports.py = layout)
docs/                      requirements checklist and our interpretation of open points
members.txt, repository.txt, requirements.txt, make_zip.py
```

## Setup

Python 3.9 or newer, then

```
pip install -r requirements.txt
```

## Commands (run from this folder)

```
python generator/main.py                 # writes cases.xlsx                       (~10 s)
python validator/tests/make_broken.py    # rebuilds the test workbooks             (~60 s)
python validator/main.py                 # validates everything, writes validation_report.txt (~40 s)
python reports/build_reports.py          # rebuilds both PDFs, approach.md, members.txt
python make_zip.py                       # packs the submission ZIP
```

`python validator/main.py some.xlsx` validates one 50-case workbook;
add `--subset` for a workbook that holds only some cases.

## How it works, in short

**Generator.** Each case is built module by module (crates, network, radio,
windows, alarms, sites/tour, pipeline, drum, sensors, safety, rations). Each
(case, module) pair has its own random stream `random.Random("40-k-module")`,
so the dataset is reproducible and modules do not influence each other. Sizes
are drawn from the tier ranges of the PDF; the story of each case study
decides the shape (for example a highway for the landslide, a street grid for
the city). Planted objects (tour, cover, safety assignment, rations) are built
so they are valid by construction, and tier-S claims are found by exhaustive
search. The four trap cases are built by dedicated functions.

**Validator.** It reads `cases.xlsx` with its own copy of the rules (it does not
import the generator) and recomputes everything: ranges, ids, references,
connectivity, pattern counts by scanning, edit distance by DP, every tier-S claim
with a different algorithm than the generator (knapsack DP, earliest-finish
greedy, weighted-interval DP, rod-cutting DP, Held-Karp, bounded search tree),
the planted objects, the six signatures, the four traps and the four variety
rules. It prints PASS or the broken rules for every case. The broken copies in
`validator/tests/` show that each check really rejects bad data.

## Libraries used

| Library | Used for | Not used for |
|---|---|---|
| openpyxl | reading and writing .xlsx files | any computation |
| reportlab | laying out the two PDF reports | - |
| Python standard library | `random` (seeded streams), `itertools` (enumerating possibilities in the exhaustive claims), `heapq`, `deque`, `bisect`, `fractions` (exact value per kg), `zipfile`, `csv` | - |

No NetworkX, SciPy, NumPy or solver library is used. Iteration 1 does **not**
implement the Iteration-2 decision modules; the graph and DP routines in this
folder only generate and verify data.

## Interpretations

Where the PDF leaves a point open we took the strictest reasonable reading;
see `docs/design_decisions.md`. `docs/requirements_checklist.md` maps every
requirement to the code and the validator check that covers it.

## References

1. T. H. Cormen, C. E. Leiserson, R. L. Rivest, C. Stein. *Introduction to Algorithms*, 3rd ed. MIT Press, 2009 (heaps, dynamic programming, greedy algorithms and Huffman codes, BFS, MST, shortest paths, string matching, closest pair, NP-completeness and approximation).
2. J. Kleinberg, E. Tardos. *Algorithm Design*. Pearson, 2006 (interval scheduling, weighted interval scheduling, subset sum and knapsack, sequence alignment, vertex cover for small k, closest pair, integer multiplication).
3. D. E. Knuth, J. H. Morris, V. R. Pratt. Fast pattern matching in strings. *SIAM Journal on Computing* 6(2), 1977.
4. D. A. Huffman. A method for the construction of minimum-redundancy codes. *Proceedings of the IRE* 40(9), 1952.
5. R. A. Wagner, M. J. Fischer. The string-to-string correction problem. *Journal of the ACM* 21(1), 1974.
6. D. S. Hirschberg. A linear space algorithm for computing maximal common subsequences. *Communications of the ACM* 18(6), 1975.
7. M. Held, R. M. Karp. A dynamic programming approach to sequencing problems. *Journal of SIAM* 10(1), 1962.
8. G. A. Croes. A method for solving traveling-salesman problems. *Operations Research* 6(6), 1958 (2-opt).
9. A. Karatsuba, Yu. Ofman. Multiplication of multidigit numbers on automata. *Soviet Physics Doklady* 7, 1963.
10. M. Davis, G. Logemann, D. Loveland. A machine program for theorem-proving. *Communications of the ACM* 5(7), 1962.
11. D. Mitchell, B. Selman, H. Levesque. Hard and easy distributions of SAT problems. *AAAI* 1992; J. M. Crawford, L. D. Auton. Experimental results on the crossover point in random 3-SAT. *Artificial Intelligence* 81, 1996.
12. J. F. Buss, J. Goldsmith. Nondeterminism within P. *SIAM Journal on Computing* 22(3), 1993 (kernel for vertex cover).
