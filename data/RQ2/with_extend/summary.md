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

See data/RQ2/codebook.md. Lucena et al. category counts are not in this workspace, so no cell-by-cell comparison is reported.

## Documents

Names come from `git ls-tree -r HEAD`. A path counts as an architecture document when its basename is `architecture.md`, `architecture.adoc` or `architecture.rst` and its parent is at most five levels down, skipping VCS, dependency and build directories.
It counts as ADR material when a parent directory is named `adr`, `adrs`, `decisions` or `architecture-decision-records`, or the file is named `adr.md`, on the same path rule.

- architecture document: 703 / 4321 (16.3%)
- ADR directory or adr.md: 583 / 4321 (13.5%)
- both: 230 / 4321 (5.3%)

- ArchUnit: architecture 191/2422, ADR 193/2422, both 51/2422
- import-linter: architecture 269/826, ADR 203/826, both 91/826
- dependency-cruiser: architecture 243/1073, ADR 187/1073, both 88/1073

## Validity

Categories are an automatic map from parsed constructs to dependency, layering, cycle, naming, visibility, annotation and other, through data/RQ2/codebook_map.json and the parsers.
Cohen's kappa and precision/recall have not been computed for these categories.
data/RQ2/validation_sample.csv has 200 rows drawn with random.Random(20261018) from parsed constructs, without stratification. The draw is ArchUnit 160, import-linter 24, dependency-cruiser 16; dependency is 101 of 200. gold_category is non-empty on 0 of 200 rows. This pipeline does not fill that column.
File selection that remains readable is in analysis/rq2.py (`_collect_archunit` and `_collect_named`): list the git tree, read manifests to obtain test roots, select candidate sources, and keep ArchUnit files whose content matches; import-linter and dependency-cruiser use a filename filter.
The stored file list is the reproducible artifact: data/RQ2/files.jsonl, data/RQ2/checkpoints/files.jsonl, and data/RQ2/files_manifest.md (4743 subjects, 11136 files, 4336 complete).
The predicates lived in analysis/git_tree_sample.py (`select_archunit_sources`, `manifest_entries`, `content_transport`, and the related helpers). That module is not in the tree, so the file list cannot be regenerated to show that those predicates produced it.

