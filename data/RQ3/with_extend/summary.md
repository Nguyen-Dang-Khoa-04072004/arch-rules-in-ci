# RQ3 with_extend

Comparison sample: `data/corpus.csv`.
Repository x tool: 4321
Rule files: 11098
Edits: 86339

## Edit classes

- restructure: 69047 (80.0%)
- add: 8448 (9.8%)
- loosen: 3534 (4.1%)
- exempt: 3219 (3.7%)
- tighten: 1187 (1.4%)
- disable: 904 (1.0%)

## H3.1 exemption or disable within 24 months

- files: 11098
- Kaplan-Meier incidence: 0.263 (95% bootstrap CI 0.254–0.272)
- point estimate is at least 30%: no
- complete case (5122 files): 0.493 (95% CI 0.480–0.507)

## H3.2 never modified

- never modified: 5501 / 11098
- share: 0.496 (95% bootstrap CI 0.486–0.504)
- below 73.8%: yes
- interval lies entirely below 73.8%: yes

## Survival to first loosen or exempt

- Kaplan-Meier incidence at 24 months: 0.419 (95% bootstrap CI 0.409–0.430)
- Cox converged: True
- log_commits: HR 1.307 (95% CI 1.270–1.345)
- log_authors: HR 0.850 (95% CI 0.793–0.911)

## Exemption or disable by year

- 2012: 4
- 2015: 4
- 2016: 3
- 2017: 13
- 2018: 31
- 2019: 67
- 2020: 137
- 2021: 125
- 2022: 144
- 2023: 270
- 2024: 401
- 2025: 543
- 2026: 2381

## By tool

### ArchUnit
- files: 8579
- H3.1 at 24 months: 0.129 (95% CI 0.121–0.138)
- H3.2 never modified: 0.557 (95% CI 0.546–0.566)

### import-linter
- files: 1093
- H3.1 at 24 months: 0.581 (95% CI 0.540–0.623)
- H3.2 never modified: 0.139 (95% CI 0.121–0.159)

### dependency-cruiser
- files: 1426
- H3.1 at 24 months: 0.805 (95% CI 0.784–0.827)
- H3.2 never modified: 0.402 (95% CI 0.377–0.427)

## Validity

Edit classes are automatic. Cohen's kappa has not been computed.
Preceding events (large-refactor commits, major-version bumps, dependency-upgrade pull requests) were not measured.
`data/RQ3/gold_edits_sample.csv` has 300 rows (add 30, disable 3, exempt 11, loosen 12, restructure 240, tighten 4). gold_edit_class is non-empty on 0 of 300 rows. This pipeline does not fill that column.

