# RQ3 no_extend

Comparison sample: `data/corpus.csv`.
Repository x tool: 1718
Rule files: 5165
Edits: 61062

## Edit classes

- restructure: 52041 (85.2%)
- add: 4171 (6.8%)
- exempt: 1882 (3.1%)
- loosen: 1727 (2.8%)
- tighten: 708 (1.2%)
- disable: 533 (0.9%)

## H3.1 exemption or disable within 24 months

- files: 5165
- Kaplan-Meier incidence: 0.285 (95% bootstrap CI 0.272–0.298)
- point estimate is at least 30%: no
- complete case (3064 files): 0.436 (95% CI 0.420–0.453)

## H3.2 never modified

- never modified: 1991 / 5165
- share: 0.385 (95% bootstrap CI 0.372–0.399)
- below 73.8%: yes
- interval lies entirely below 73.8%: yes

## Survival to first loosen or exempt

- Kaplan-Meier incidence at 24 months: 0.413 (95% bootstrap CI 0.398–0.427)
- Cox converged: True
- log_commits: HR 1.331 (95% CI 1.281–1.383)
- log_authors: HR 0.856 (95% CI 0.787–0.931)

## Exemption or disable by year

- 2012: 2
- 2015: 2
- 2016: 2
- 2017: 8
- 2018: 20
- 2019: 45
- 2020: 54
- 2021: 62
- 2022: 84
- 2023: 143
- 2024: 171
- 2025: 278
- 2026: 1544

## By tool

### ArchUnit
- files: 3805
- H3.1 at 24 months: 0.147 (95% CI 0.135–0.159)
- H3.2 never modified: 0.454 (95% CI 0.438–0.470)

### import-linter
- files: 643
- H3.1 at 24 months: 0.581 (95% CI 0.529–0.629)
- H3.2 never modified: 0.087 (95% CI 0.067–0.110)

### dependency-cruiser
- files: 717
- H3.1 at 24 months: 0.760 (95% CI 0.725–0.796)
- H3.2 never modified: 0.291 (95% CI 0.259–0.326)

## Validity

Edit classes are automatic. Cohen's kappa has not been computed.
Preceding events (large-refactor commits, major-version bumps, dependency-upgrade pull requests) were not measured.
`data/RQ3/gold_edits_sample.csv` has 300 rows (add 30, disable 3, exempt 11, loosen 12, restructure 240, tighten 4). gold_edit_class is non-empty on 0 of 300 rows. This pipeline does not fill that column.

