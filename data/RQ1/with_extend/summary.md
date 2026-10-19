# RQ1 with_extend

Rows (repository x tool): 4743
Unique repositories: 4718

## Adoption year
### ArchUnit n=2812 dated=2645
- pre-2017: 1 (0.0% of tool)
- 2017: 6 (0.2% of tool)
- 2018: 18 (0.6% of tool)
- 2019: 196 (7.0% of tool)
- 2020: 372 (13.2% of tool)
- 2021: 156 (5.5% of tool)
- 2022: 232 (8.3% of tool)
- 2023: 298 (10.6% of tool)
- 2024: 366 (13.0% of tool)
- 2025: 363 (12.9% of tool)
- 2026: 637 (22.7% of tool)
- missing: 167 (5.9% of tool)

### import-linter n=845 dated=811
- 2019: 3 (0.4% of tool)
- 2020: 1 (0.1% of tool)
- 2021: 3 (0.4% of tool)
- 2022: 6 (0.7% of tool)
- 2023: 15 (1.8% of tool)
- 2024: 38 (4.5% of tool)
- 2025: 103 (12.2% of tool)
- 2026: 642 (76.0% of tool)
- missing: 34 (4.0% of tool)

### dependency-cruiser n=1086 dated=1081
- 2017: 5 (0.5% of tool)
- 2018: 8 (0.7% of tool)
- 2019: 15 (1.4% of tool)
- 2020: 27 (2.5% of tool)
- 2021: 20 (1.8% of tool)
- 2022: 45 (4.1% of tool)
- 2023: 76 (7.0% of tool)
- 2024: 117 (10.8% of tool)
- 2025: 187 (17.2% of tool)
- 2026: 581 (53.5% of tool)
- missing: 5 (0.5% of tool)

## CI share
### ArchUnit
- scanned with a result: 2810 / 2812 (unknown 2)
- share: 0.342 (95% bootstrap CI 0.323–0.362)

### import-linter
- scanned with a result: 842 / 845 (unknown 3)
- share: 0.418 (95% bootstrap CI 0.386–0.449)

### dependency-cruiser
- scanned with a result: 1082 / 1086 (unknown 4)
- share: 0.117 (95% bootstrap CI 0.098–0.137)

## H1.1
Denominator is import-linter and dependency-cruiser rows with a CI result. ArchUnit is descriptive only.
- import-linter: 0.418 (95% CI 0.386–0.449); interval lies entirely below 0.50: yes
- dependency-cruiser: 0.117 (95% CI 0.098–0.137); interval lies entirely below 0.50: yes
- pooled: 0.249 (95% CI 0.230–0.269); interval lies entirely below 0.50: yes
- pooled unique repositories: 0.250 (95% CI 0.229–0.267); interval lies entirely below 0.50: yes
