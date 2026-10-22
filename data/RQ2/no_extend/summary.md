# RQ2 no_extend

Held-out rows only. The first 1000 kept+extended funnel rows developed the codebook and are excluded.
Constructs: 9823
Repository x tool: 1247

## Coverage and categories
### ArchUnit
- coverage: 6372/7870 (81.0%)
- dependency: 3614 (56.7% of parsed)
- layering: 197 (3.1% of parsed)
- cycle: 214 (3.4% of parsed)
- naming: 1079 (16.9% of parsed)
- visibility: 282 (4.4% of parsed)
- annotation: 565 (8.9% of parsed)
- other: 421 (6.6% of parsed)
- unparsed: 1498

Dependency subtypes:
- allowed: 369
- forbidden: 3188
- required: 57

Subjects:
- field_injection: 28
- generic_exceptions: 63
- java_util_logging: 74
- joda_time: 27
- plantuml: 9
- standard_streams: 61

### import-linter
- coverage: 1149/1225 (93.8%)
- dependency: 917 (79.8% of parsed)
- layering: 203 (17.7% of parsed)
- cycle: 29 (2.5% of parsed)
- unparsed: 76

Dependency subtypes:
- allowed: 44
- forbidden: 873

### dependency-cruiser
- coverage: 720/728 (98.9%)
- dependency: 417 (57.9% of parsed)
- cycle: 303 (42.1% of parsed)
- unparsed: 8

Dependency subtypes:
- allowed: 2
- forbidden: 415

chi-square: 2737.969, df=12, p=0, Cramer's V=0.408

## H2.1 dependency and layering

- ArchUnit: 0.598 (95% CI 0.586–0.610); interval lies entirely above 0.70: no
- import-linter: 0.975 (95% CI 0.964–0.983); interval lies entirely above 0.70: yes
- dependency-cruiser: 0.579 (95% CI 0.544–0.617); interval lies entirely above 0.70: no

## Comparison

See data/RQ2/codebook.md. Categories without a Lucena counterpart stay separate.
