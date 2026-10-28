# Results

The comparison sample is `data/corpus.csv`. `with_extend` is kept plus extended. `no_extend` is kept only.
Category labels and edit classes are automatic. RQ4 is a within-treated description and is not an average treatment effect. RQ5 is dropped.

## RQ1

Executable rules in the comparison sample, and the share whose repository runs the tool in GitHub Actions.

### no_extend
- repository x tool: 1718; unique repositories: 1703
- ArchUnit in CI: 429 / 733 (0.585, 95% CI 0.552–0.624)
- import-linter in CI: 207 / 472 (0.439, 95% CI 0.394–0.483)
- dependency-cruiser in CI: 86 / 512 (0.168, 95% CI 0.137–0.199)

### with_extend
- repository x tool: 4321; unique repositories: 4300
- ArchUnit in CI: 869 / 2421 (0.359, 95% CI 0.341–0.379)
- import-linter in CI: 351 / 826 (0.425, 95% CI 0.394–0.458)
- dependency-cruiser in CI: 125 / 1073 (0.117, 95% CI 0.098–0.135)

H1.1, that under half of import-linter and dependency-cruiser repositories wire the tool into CI, holds in both cohorts: each tool interval and the pooled interval lie entirely below 0.50.
ArchUnit is outside that hypothesis. Other-tool hit counts and the inclusion funnel are in the RQ1 summaries.
Detail: `data/RQ1/with_extend/summary.md` and `data/RQ1/no_extend/summary.md`.

## RQ2

What parsed constructs encode, on held-out rows.

### no_extend
- held-out constructs: 9781
- ArchUnit dependency or layering: 0.599 (95% CI 0.586–0.612); entirely above 0.70: no
- import-linter dependency or layering: 0.975 (95% CI 0.965–0.982); entirely above 0.70: yes
- dependency-cruiser dependency or layering: 0.579 (95% CI 0.542–0.617); entirely above 0.70: no

### with_extend
- held-out constructs: 21713
- ArchUnit dependency or layering: 0.585 (95% CI 0.578–0.593); entirely above 0.70: no
- import-linter dependency or layering: 0.981 (95% CI 0.975–0.986); entirely above 0.70: yes
- dependency-cruiser dependency or layering: 0.568 (95% CI 0.544–0.591); entirely above 0.70: no

On the with_extend clones scanned (4321), 703 have an architecture document and 583 have ADR material; 230 have both.
H2.1, that dependency and layering exceed 70% in every tool, holds for import-linter only. It does not hold for ArchUnit or dependency-cruiser.
Labels are automatic: the 200-row validation sample has an empty gold column, and Cohen's kappa was not computed. The file-selection predicates in `analysis/git_tree_sample.py` are not in the tree.
Lucena et al. counts are not in this workspace, so there is no cell-by-cell comparison. The construct map is `data/RQ2/codebook.md`.
Detail: `data/RQ2/with_extend/summary.md` and `data/RQ2/no_extend/summary.md`.

## RQ3

How rule files change after they appear. Classes are automatic.

### no_extend
- files: 5165; edits: 61062
- largest class: restructure 52041 (85.2%)
- H3.1 at 24 months: 0.285 (95% CI 0.272–0.298); point at least 0.30: no
- H3.2 never modified: 0.385 (95% CI 0.372–0.399); entirely below 0.738: yes

### with_extend
- files: 11098; edits: 86339
- largest class: restructure 69047 (80.0%)
- H3.1 at 24 months: 0.263 (95% CI 0.254–0.272); point at least 0.30: no
- H3.2 never modified: 0.496 (95% CI 0.486–0.504); entirely below 0.738: yes

H3.1, that at least 30% of rule files gain an exemption or a disabled rule within 24 months, does not hold on the Kaplan-Meier estimate in either cohort. The complete-case share among files followed for 24 months is higher and is reported in the RQ3 summaries.
H3.2, that the never-modified share is below the 73.8% reported for AI-config files, holds in both cohorts.
The 300-row edit sample has an empty gold column, so Cohen's kappa was not computed. Commits that precede an addition were not classified.
Detail: `data/RQ3/with_extend/summary.md` and `data/RQ3/no_extend/summary.md`.

## RQ4

How source-level dependency and layering violations move across the twelve months before and after the first ArchUnit rule commit, on repositories with history on both sides.
This is not an effect of adoption. There is no control group and no ATT.

- eligible repositories: 317; replayed: 317
- ratifier: 240 of 298 with t=-1 and t=0 observed (80.5%)
- reformer: 7 (2.3%)
- evaluable repositories with t=-1, t=0 and t=12: 141 of 148 with at least one translated rule
- zero at t=-1 in that subset: 83
- t=12 versus t=-1: decreased 18, unchanged 86, increased 37

On the evaluable subset the median count is 0 at t=-1, t=0 and t=12. The mean is higher and the interval is wide. Most series do not fall. Detail: `data/RQ4/summary.md`.

## RQ5

Dropped. No agent-authored pull-request linkage is available, so the 200-pull-request threshold was not evaluated.
Detail: `data/RQ5/summary.md`.

