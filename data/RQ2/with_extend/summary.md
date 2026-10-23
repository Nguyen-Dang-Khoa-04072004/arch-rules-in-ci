# RQ2 with_extend

Comparison N is the frozen corpus. Category counts and H2.1 use held-out construct rows only.
The first 1000 kept+extended funnel rows stay out of H2.1. The structural family is dependency and layering.
Comparison repository x tool: 4321
Held-out constructs: 21713

## Coverage and categories
### ArchUnit
- coverage: 15173/17907 (84.7%)
- dependency: 7970 (52.5% of parsed)
- layering: 909 (6.0% of parsed)
- cycle: 465 (3.1% of parsed)
- naming: 2805 (18.5% of parsed)
- visibility: 661 (4.4% of parsed)
- annotation: 1281 (8.4% of parsed)
- other: 1082 (7.1% of parsed)
- unparsed: 2734

### import-linter
- coverage: 2136/2265 (94.3%)
- dependency: 1685 (78.9% of parsed)
- layering: 410 (19.2% of parsed)
- cycle: 41 (1.9% of parsed)
- unparsed: 129

### dependency-cruiser
- coverage: 1503/1541 (97.5%)
- dependency: 854 (56.8% of parsed)
- cycle: 649 (43.2% of parsed)
- unparsed: 38

chi-square: 5865.559, df=12, p=0, Cramer's V=0.395

## H2.1 dependency and layering

- ArchUnit: 0.585 (95% CI 0.578–0.593); interval lies entirely above 0.70: no
- import-linter: 0.981 (95% CI 0.975–0.986); interval lies entirely above 0.70: yes
- dependency-cruiser: 0.568 (95% CI 0.544–0.591); interval lies entirely above 0.70: no

## Comparison

See data/RQ2/codebook.md. Categories without a Lucena counterpart stay separate.
