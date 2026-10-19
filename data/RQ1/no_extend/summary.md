# RQ1 no_extend

Rows (repository x tool): 1864
Unique repositories: 1849

## Adoption year
### ArchUnit n=863 dated=726
- 2017: 2 (0.2% of tool)
- 2018: 9 (1.0% of tool)
- 2019: 49 (5.7% of tool)
- 2020: 51 (5.9% of tool)
- 2021: 45 (5.2% of tool)
- 2022: 59 (6.8% of tool)
- 2023: 64 (7.4% of tool)
- 2024: 79 (9.2% of tool)
- 2025: 100 (11.6% of tool)
- 2026: 268 (31.1% of tool)
- missing: 137 (15.9% of tool)

### import-linter n=482 dated=457
- 2019: 2 (0.4% of tool)
- 2020: 1 (0.2% of tool)
- 2021: 3 (0.6% of tool)
- 2022: 2 (0.4% of tool)
- 2023: 10 (2.1% of tool)
- 2024: 14 (2.9% of tool)
- 2025: 54 (11.2% of tool)
- 2026: 371 (77.0% of tool)
- missing: 25 (5.2% of tool)

### dependency-cruiser n=519 dated=515
- 2017: 2 (0.4% of tool)
- 2018: 5 (1.0% of tool)
- 2019: 7 (1.3% of tool)
- 2020: 8 (1.5% of tool)
- 2021: 6 (1.2% of tool)
- 2022: 26 (5.0% of tool)
- 2023: 27 (5.2% of tool)
- 2024: 46 (8.9% of tool)
- 2025: 70 (13.5% of tool)
- 2026: 318 (61.3% of tool)
- missing: 4 (0.8% of tool)

## CI share
### ArchUnit
- scanned with a result: 862 / 863 (unknown 1)
- share: 0.555 (95% bootstrap CI 0.522–0.585)

### import-linter
- scanned with a result: 480 / 482 (unknown 2)
- share: 0.433 (95% bootstrap CI 0.390–0.475)

### dependency-cruiser
- scanned with a result: 516 / 519 (unknown 3)
- share: 0.171 (95% bootstrap CI 0.138–0.202)

## H1.1
Denominator is import-linter and dependency-cruiser rows with a CI result. ArchUnit is descriptive only.
- import-linter: 0.433 (95% CI 0.390–0.475); interval lies entirely below 0.50: yes
- dependency-cruiser: 0.171 (95% CI 0.138–0.202); interval lies entirely below 0.50: yes
- pooled: 0.297 (95% CI 0.269–0.326); interval lies entirely below 0.50: yes
- pooled unique repositories: 0.298 (95% CI 0.271–0.326); interval lies entirely below 0.50: yes
