# RQ2 no_extend

Comparison N is the frozen corpus. Category counts and H2.1 use held-out construct rows only.
The first 1000 kept+extended funnel rows stay out of H2.1. The structural family is dependency and layering.
Comparison repository x tool: 1718
Held-out constructs: 9781

## Coverage and categories
### ArchUnit
- coverage: 6351/7838 (81.0%)
- dependency: 3606 (56.8% of parsed)
- layering: 197 (3.1% of parsed)
- cycle: 205 (3.2% of parsed)
- naming: 1078 (17.0% of parsed)
- visibility: 282 (4.4% of parsed)
- annotation: 565 (8.9% of parsed)
- other: 418 (6.6% of parsed)
- unparsed: 1487

### import-linter
- coverage: 1139/1215 (93.7%)
- dependency: 908 (79.7% of parsed)
- layering: 202 (17.7% of parsed)
- cycle: 29 (2.5% of parsed)
- unparsed: 76

### dependency-cruiser
- coverage: 720/728 (98.9%)
- dependency: 417 (57.9% of parsed)
- cycle: 303 (42.1% of parsed)
- unparsed: 8

chi-square: 2759.871, df=12, p=0, Cramer's V=0.410

## H2.1 dependency and layering

- ArchUnit: 0.599 (95% CI 0.586–0.612); interval lies entirely above 0.70: no
- import-linter: 0.975 (95% CI 0.965–0.982); interval lies entirely above 0.70: yes
- dependency-cruiser: 0.579 (95% CI 0.542–0.617); interval lies entirely above 0.70: no

## Comparison

See data/RQ2/codebook.md. Categories without a Lucena counterpart stay separate.
