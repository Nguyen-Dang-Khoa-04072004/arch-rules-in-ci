# Attrition

Repositories listed here are out of the RQ1–RQ4 comparison sample.
They are not added to comparison N.

Ledger: `data/corpus_excluded.csv` (422 rows).

## Counts by cohort and tool

| cohort | tool | unavailable | no_rule_file | clone_error | total |
| --- | --- | ---: | ---: | ---: | ---: |
| no_extend | ArchUnit | 0 | 128 | 1 | 129 |
| no_extend | import-linter | 3 | 4 | 3 | 10 |
| no_extend | dependency-cruiser | 3 | 4 | 0 | 7 |
| no_extend | all | 6 | 136 | 4 | 146 |
| with_extend | ArchUnit | 5 | 377 | 8 | 390 |
| with_extend | import-linter | 4 | 10 | 5 | 19 |
| with_extend | dependency-cruiser | 6 | 5 | 2 | 13 |
| with_extend | all | 15 | 392 | 15 | 422 |

## Kept repositories among the unavailable set

These six kept repositories are part of the 15 unavailable repositories.
They count in both `no_extend` and `with_extend` attrition, and in neither comparison N.

- sgajbi/lotus-core: present
- SJTU-Geek/Aixinwu-dashboard: present
- zhaochy1990/running: present
- lj860117/moneybag: present
- ChauDoan21165/MercyB: present
- leszavr/voxlibris: present

