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

See data/RQ2/codebook.md. Lucena et al. category counts are not in this workspace, so no cell-by-cell comparison is reported.

## Documents

Names come from `git ls-tree -r HEAD`. A path counts as an architecture document when its basename is `architecture.md`, `architecture.adoc` or `architecture.rst` and its parent is at most five levels down, skipping VCS, dependency and build directories.
It counts as ADR material when a parent directory is named `adr`, `adrs`, `decisions` or `architecture-decision-records`, or the file is named `adr.md`, on the same path rule.

- architecture document: 452 / 1718 (26.3%)
- ADR directory or adr.md: 330 / 1718 (19.2%)
- both: 148 / 1718 (8.6%)

- ArchUnit: architecture 109/734, ADR 94/734, both 30/734
- import-linter: architecture 183/472, ADR 123/472, both 64/472
- dependency-cruiser: architecture 160/512, ADR 113/512, both 54/512

## Validity

Categories are an automatic map from parsed constructs to dependency, layering, cycle, naming, visibility, annotation and other, through data/RQ2/codebook_map.json and the parsers.
Cohen's kappa and precision/recall have not been computed for these categories.
data/RQ2/validation_sample.csv has 200 rows drawn with random.Random(20261018) from parsed constructs, without stratification. The draw is ArchUnit 160, import-linter 24, dependency-cruiser 16; dependency is 101 of 200. gold_category is non-empty on 0 of 200 rows. This pipeline does not fill that column.
File selection that remains readable is in analysis/rq2.py (`_collect_archunit` and `_collect_named`): list the git tree, read manifests to obtain test roots, select candidate sources, and keep ArchUnit files whose content matches; import-linter and dependency-cruiser use a filename filter.
The stored file list is the reproducible artifact: data/RQ2/files.jsonl, data/RQ2/checkpoints/files.jsonl, and data/RQ2/files_manifest.md (4743 subjects, 11136 files, 4336 complete).
The predicates lived in analysis/git_tree_sample.py (`select_archunit_sources`, `manifest_entries`, `content_transport`, and the related helpers). That module is not in the tree, so the file list cannot be regenerated to show that those predicates produced it.

