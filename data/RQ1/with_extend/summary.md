# RQ1 with_extend

Comparison sample: `data/corpus.csv`.
Rows (repository x tool): 4321
Unique repositories: 4300

## Adoption year
### ArchUnit n=2422 dated=2286
- pre-2017: 1 (0.0% of tool)
- 2017: 6 (0.2% of tool)
- 2018: 17 (0.7% of tool)
- 2019: 172 (7.1% of tool)
- 2020: 353 (14.6% of tool)
- 2021: 133 (5.5% of tool)
- 2022: 196 (8.1% of tool)
- 2023: 250 (10.3% of tool)
- 2024: 296 (12.2% of tool)
- 2025: 282 (11.6% of tool)
- 2026: 580 (23.9% of tool)
- missing: 136 (5.6% of tool)

### import-linter n=826 dated=798
- 2019: 3 (0.4% of tool)
- 2020: 1 (0.1% of tool)
- 2021: 3 (0.4% of tool)
- 2022: 6 (0.7% of tool)
- 2023: 15 (1.8% of tool)
- 2024: 37 (4.5% of tool)
- 2025: 99 (12.0% of tool)
- 2026: 634 (76.8% of tool)
- missing: 28 (3.4% of tool)

### dependency-cruiser n=1073 dated=1072
- 2017: 5 (0.5% of tool)
- 2018: 8 (0.7% of tool)
- 2019: 15 (1.4% of tool)
- 2020: 27 (2.5% of tool)
- 2021: 20 (1.9% of tool)
- 2022: 45 (4.2% of tool)
- 2023: 75 (7.0% of tool)
- 2024: 117 (10.9% of tool)
- 2025: 187 (17.4% of tool)
- 2026: 573 (53.4% of tool)
- missing: 1 (0.1% of tool)

## CI share
### ArchUnit
- scanned with a result: 2421 / 2422 (unknown 1)
- share: 0.359 (95% bootstrap CI 0.341–0.379)

### import-linter
- scanned with a result: 826 / 826 (unknown 0)
- share: 0.425 (95% bootstrap CI 0.393–0.458)

### dependency-cruiser
- scanned with a result: 1073 / 1073 (unknown 0)
- share: 0.116 (95% bootstrap CI 0.098–0.135)

## H1.1
Denominator is import-linter and dependency-cruiser rows with a CI result. ArchUnit is descriptive only.
- import-linter: 0.425 (95% CI 0.393–0.458); interval lies entirely below 0.50: yes
- dependency-cruiser: 0.116 (95% CI 0.098–0.135); interval lies entirely below 0.50: yes
- pooled: 0.251 (95% CI 0.231–0.271); interval lies entirely below 0.50: yes
- pooled unique repositories: 0.251 (95% CI 0.233–0.270); interval lies entirely below 0.50: yes
