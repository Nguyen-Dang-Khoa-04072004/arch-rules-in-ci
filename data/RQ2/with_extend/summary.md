# RQ2 with_extend

Held-out rows only. The first 1000 kept+extended funnel rows developed the codebook and are excluded.
Constructs: 21811
Repository x tool: 3386

## Coverage and categories
### ArchUnit
- coverage: 15231/17981 (84.7%)
- dependency: 7995 (52.5% of parsed)
- layering: 911 (6.0% of parsed)
- cycle: 474 (3.1% of parsed)
- naming: 2812 (18.5% of parsed)
- visibility: 664 (4.4% of parsed)
- annotation: 1287 (8.4% of parsed)
- other: 1088 (7.1% of parsed)
- unparsed: 2750

Dependency subtypes:
- allowed: 938
- forbidden: 6889
- required: 168

Subjects:
- field_injection: 97
- generic_exceptions: 154
- java_util_logging: 160
- joda_time: 81
- plantuml: 20
- standard_streams: 164

### import-linter
- coverage: 2156/2285 (94.4%)
- dependency: 1704 (79.0% of parsed)
- layering: 411 (19.1% of parsed)
- cycle: 41 (1.9% of parsed)
- unparsed: 129

Dependency subtypes:
- allowed: 65
- forbidden: 1639

### dependency-cruiser
- coverage: 1507/1545 (97.5%)
- dependency: 858 (56.9% of parsed)
- cycle: 649 (43.1% of parsed)
- unparsed: 38

Dependency subtypes:
- allowed: 4
- forbidden: 853
- required: 1

chi-square: 5847.018, df=12, p=0, Cramer's V=0.393

## H2.1 dependency and layering

- ArchUnit: 0.585 (95% CI 0.577–0.592); interval lies entirely above 0.70: no
- import-linter: 0.981 (95% CI 0.975–0.987); interval lies entirely above 0.70: yes
- dependency-cruiser: 0.569 (95% CI 0.545–0.593); interval lies entirely above 0.70: no

## Comparison

See data/RQ2/codebook.md. Categories without a Lucena counterpart stay separate.
