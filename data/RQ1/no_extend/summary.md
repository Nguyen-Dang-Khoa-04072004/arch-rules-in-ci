# RQ1 no_extend

Comparison sample: `data/corpus.csv`.
Rows (repository x tool): 1718
Unique repositories: 1703

## Adoption year
### ArchUnit n=734 dated=617
- 2017: 2 (0.3% of tool)
- 2018: 9 (1.2% of tool)
- 2019: 31 (4.2% of tool)
- 2020: 43 (5.9% of tool)
- 2021: 40 (5.4% of tool)
- 2022: 54 (7.4% of tool)
- 2023: 47 (6.4% of tool)
- 2024: 60 (8.2% of tool)
- 2025: 80 (10.9% of tool)
- 2026: 251 (34.2% of tool)
- missing: 117 (15.9% of tool)

### import-linter n=472 dated=451
- 2019: 2 (0.4% of tool)
- 2020: 1 (0.2% of tool)
- 2021: 3 (0.6% of tool)
- 2022: 2 (0.4% of tool)
- 2023: 10 (2.1% of tool)
- 2024: 13 (2.8% of tool)
- 2025: 53 (11.2% of tool)
- 2026: 367 (77.8% of tool)
- missing: 21 (4.4% of tool)

### dependency-cruiser n=512 dated=511
- 2017: 2 (0.4% of tool)
- 2018: 5 (1.0% of tool)
- 2019: 7 (1.4% of tool)
- 2020: 8 (1.6% of tool)
- 2021: 6 (1.2% of tool)
- 2022: 26 (5.1% of tool)
- 2023: 27 (5.3% of tool)
- 2024: 46 (9.0% of tool)
- 2025: 70 (13.7% of tool)
- 2026: 314 (61.3% of tool)
- missing: 1 (0.2% of tool)

## CI share
### ArchUnit
- scanned with a result: 733 / 734 (unknown 1)
- share: 0.585 (95% bootstrap CI 0.553–0.623)

### import-linter
- scanned with a result: 472 / 472 (unknown 0)
- share: 0.439 (95% bootstrap CI 0.394–0.483)

### dependency-cruiser
- scanned with a result: 512 / 512 (unknown 0)
- share: 0.168 (95% bootstrap CI 0.137–0.199)

## H1.1
Denominator is import-linter and dependency-cruiser rows with a CI result. ArchUnit is descriptive only.
- import-linter: 0.439 (95% CI 0.394–0.483); interval lies entirely below 0.50: yes
- dependency-cruiser: 0.168 (95% CI 0.137–0.199); interval lies entirely below 0.50: yes
- pooled: 0.298 (95% CI 0.270–0.326); interval lies entirely below 0.50: yes
- pooled unique repositories: 0.299 (95% CI 0.270–0.325); interval lies entirely below 0.50: yes
