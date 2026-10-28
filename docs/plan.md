# Plan: Architecture Rules in the Wild

## 1. Header

- **Working title:** Architecture Rules in the Wild: Prevalence, Rot, and Effect of Executable Architecture Conformance Checks in Open Source
- **Idea:** I26 / `architecture-rules-in-the-wild-a-longitu` (rank 5 of 5, final score 4.92)
- **Target track:** ICSA 2027 Research Papers (10 + 2 pages, double-anonymous; abstract Oct 30, paper Nov 4, 2026). **Fallback:** NEMI (5 pages, Dec 20, 2026).
- **CFP topics:** Architecture & Lifecycle (CI/CD & DevOps; continuous architecting; refactoring & evolution); Architecture Evaluation (conformance checking); Architecture Design (frameworks & ADLs, architecture-as-code); Architecture & Architects (state of practice).

**Abstract (draft).** Architecture-as-code tools such as ArchUnit, import-linter and dependency-cruiser let teams encode layering and dependency rules as tests that run in continuous integration. ICSA 2025 and 2026 proposed frameworks for this practice and a recent multiple-case study documented its use in industry, but there is no large-scale, longitudinal, repository-level evidence on what executable rules say, how they decay, and whether adopting them changes a system's structural trajectory. We mine 4,000-6,000 non-template GitHub repositories that ship executable architecture rules for three tools spanning JVM, Python and JavaScript/TypeScript, parse every rule into a tool-stratified canonical model, and reconstruct the edit history of each rule file. We introduce *rule rot*, operationalised through tool-native exemption mechanisms (frozen violation stores, ignore lists, exceptions, disabled rules), and validate a five-class edit taxonomy with two coders. For Java adopters with at least twelve months of history on each side of adoption, we replay the adopted dependency and layering rules retroactively over pre- and post-adoption snapshots ("rule archaeology") and separate teams that *ratify* existing structure from those that *reform* it. That series is a within-treated description: there is no matched non-adopter group and it is not an average treatment effect. We release ArchRules, a benchmark of real rules, gold-labelled rule edits and violation time series.

**Theme alignment.** The ICSA 2027 theme asks how architecture endures in an evolving landscape. Executable conformance rules are the mechanism by which architectural intent survives continuous delivery and, increasingly, agent-authored code. This paper supplies the first evidence on whether that mechanism is used, maintained and effective, with an exploratory look at whether rules moderate the structural impact of AI-agent pull requests.

## 2. Motivation and gap

**Problem.** Continuous architecting assumes rules are enforced continuously. Tooling makes this cheap, yet we do not know how common enforcement is, what rules teams write, whether rules are maintained or exempted away, and whether enforcement changes erosion. Without this, the "Architecture as Code" (ICSA 2025) and "CONTAaC" (ICSA 2026) proposals rest on assumption, and platform teams cannot justify or reject investment.

**Why now.** Three tool families have matured enough that GitHub code search returns about 20K manifest/rule hits (ArchUnit in pom/gradle about 12.9K, import-linter about 3.2K, dependency-cruiser about 3.4K; verified 2026-10-08). Coding agents now author a measurable share of PRs, making automated guardrails a live theme question. Recent DiD-on-architecture work (Larsen & Moghaddam, SEAA 2026) gives a template to extend.

**Closest prior work and delta.** Verification found no paper that mines executable architecture-rule files at scale, classifies their evolution, or estimates the effect of adopting them. Every overlapping work is addressed explicitly:

| Work | Overlap | Positioning |
|---|---|---|
| Pontillo et al., "Architecture as Code in Industry: A Multiple-Case Empirical Study", ICSA-C 2026 | First empirical AaC adoption evidence, qualitative | Gap narrowed to "no large-scale, longitudinal OSS evidence"; their themes interpret RQ2/RQ3 |
| de Lima Lucena, Alves, Brunet, "Can LLMs Turn Design Discussions into Architectural Tests?", ECSA 2026 | 10.5K NL design rules turned into ArchUnit tests | RQ2 is the first comparison of what *executable* rules encode vs. their NL taxonomy; ArchRules is the real-rule counterpart |
| Larsen & Moghaddam, "Mining Architectural Quality Under Agentic AI Adoption", SEAA 2026 | DiD + PSM on Arcan smells; different treatment | Methodological precedent for a causal design. This study does not estimate that ATT; RQ4 is the within-treated series. |
| Biazotto et al., "Investigating CI/CD-based Technical Debt Management...", arXiv 2604.10631 | CI pipeline parsing for TDM tools (Travis) | Method reused and extended to GitHub Actions and architecture tools |
| "A Few Pages of Markdown...", arXiv 2608.25241 | 73.8% of AI-config files never modified | Direct contrast for rule rot (H3.2) |
| "Rule Taxonomy and Evolution in AI IDEs", arXiv 2606.12231 | Rule-file taxonomy and evolution mining | Sharp distinction: agent instruction files vs. machine-checked rules |
| Zhang et al., "Domain-Driven Design in Practice", arXiv 2606.23984 | Longitudinal boundary-violation metrics | Framing reused; no conformance treatment there |
| Al-Asali & El-Ramly, SonarCloud adoption ITS, Research Square 2026 [verify] | Adoption-effect design | Precedent; workflow outcomes only |
| "Architecture in the Cradle: ... ArchGuard", ICSA 2026 | Decay metrics over history | One established decay indicator reused as secondary outcome |
| "Evaluating LLMs for Detecting Architectural Design Rules Violations", ICSA 2026 | Design rules as ground truth | ArchRules offered as the real-rule benchmark this line lacks |
| "Architecture Decision Records: Adoption, Impact...", ICSA 2026 | Mining adoption + impact; ADR co-occurrence | Methodological sibling; RQ2 reports co-occurrence with ADRs/ARCHITECTURE.md |
| MIPRO 2022 linter study; "Quieting the Static", arXiv 2311.07482 | Config evolution, alert suppression | Suppression-as-rot precedent for RQ3 |
| MSR 2026 agentic-PR cluster (test failures, how agents modify code, reverted changes, agent SATD) | Agent PR outcomes | RQ5 framed as a moderation extension, not a first |
| Knodel & Popescu (WICSA 2007); Pruijt et al. (SPE 2017); Maffort et al. (EMSE 2016); Brunet et al. (MSR 2014) | Tool accuracy, violation mining | Used for extraction validation and framing |

**Fix suggestions incorporated.** (1) Gap statement rewritten as above. (2) Rule rot is the headline construct with a per-tool exemption mapping: ArchUnit `FreezingArchRule` stores and `@ArchIgnore`; import-linter `ignore_imports` and contract removal; dependency-cruiser `exceptions`, `pathNot` and severity downgrades; commented-out or disabled rules in all three. (3) RQ4 originally followed Larsen & Moghaddam (Callaway-Sant'Anna, event-study plots, Goodman-Bacon, Rosenbaum/Oster). That estimator was not run; the reported question is the within-treated trajectory. (4) RQ5 reframed as moderation and demoted to exploratory. (5) Tools cut to three (ArchUnit incl. Kotlin, import-linter, dependency-cruiser), target 4-6K repos; other tools appear only in one RQ1 prevalence table. (6) CI detection follows Biazotto et al. on GitHub Actions; SWH and BigQuery cross-check claims are deleted and code-search survivorship bias is stated. (7) Endogeneity is not identified. Rule archaeology still shows the pre-adoption level and the ratifier/reformer split, and the threats section states that adoption bundled with refactoring is not separated from the rule change.

## 3. Research questions and hypotheses

- **RQ1 (prevalence, CI execution).** How prevalent are executable rules across the three ecosystems over 2017-2026, and what share run in a CI workflow? *Metric:* post-funnel repo counts, adoption-year histogram, share with a GitHub Actions workflow running the rule command, tool-stratified (ArchUnit runs under `mvn/gradle test` by construction, so the CI question is primarily for import-linter and dependency-cruiser). *H1.1:* under 50% of import-linter/dependency-cruiser repos wire the tool into CI.
- **RQ2 (what rules encode).** Which categories dominate (layering, allowed/forbidden dependency, cycle freedom, naming/stereotype, visibility, annotation constraint), how do they differ by tool, and how do they compare with the NL design-rule taxonomy of Lucena et al.? *Metric:* category counts dwith parser coverage; chi-square and Cramer's V on tool x category; co-occurrence with ADRs and ARCHITECTURE.md. *H2.1:* dependency/layering rules exceed 70% in every tool.
- **RQ3 (evolution and rot).** At what rates are rules added, tightened, loosened, exempted, disabled or restructured; what is the survival time to first loosening; which observable events (large-refactor commits, major-version bumps, dependency-upgrade PRs) precede additions? *Metric:* kappa-validated edit classes; Kaplan-Meier and Cox survival with covariates (contributor churn, release cadence, age); exemption count per rule over time. *H3.1:* at least 30% of rule files accumulate an exemption or disabled rule within 24 months. *H3.2:* the never-modified share is lower than the 73.8% reported for AI-config files.
- **RQ4 (within-treated trajectory, Java/ArchUnit).** Among ArchUnit repositories with at least twelve months of history on each side of the adoption commit, how do source-level dependency and layering violation counts move from before adoption to after, and what share of those repositories ratify an already-clean structure versus reform it at adoption? *Metric:* violation counts at t=-1, t=0 and t=12 on repositories with at least one evaluable rule, with repository bootstrap intervals; ratifier and reformer shares. No control group, matching, or ATT is estimated.
- **RQ4a (ratify vs. reform).** What share of eligible adopters had zero evaluable violations at t=-1 (ratifiers) versus a pre-adoption violation and zero at t=0 (reformers)? *Metric:* counts at t=-1 and t=0. These shares describe the treated set only.

RQ4 above replaces the matched difference-in-differences specified earlier in this plan. That estimator was not run.
- **RQ5 (exploratory).** In adopter repos, do executable rules moderate the architectural-quality effect of agent-authored PRs (AIDev linkage)? Kept only if at least 200 PRs with retrievable check outcomes exist; otherwise dropped. Dropped for this run: no agent-authored pull-request linkage is in the workspace, so the threshold was not evaluated.

## 4. Study design

**Data sources and selection.** `gh api search/code` with sharded queries (filename plus `size:` ranges plus `path:` prefixes to stay under the 1,000-result cap; 10 requests/min with backoff) for `com.tngtech.archunit` in `pom.xml`/`build.gradle(.kts)`, `[tool.importlinter]` in `pyproject.toml` and `.importlinter`, and `.dependency-cruiser.(js|cjs|mjs|json)`. Hits map to repositories and are deduplicated. **Inclusion funnel (reported as a table):** not a fork; not archived; not a template or scaffold (JHipster `TechnicalStructureTest.java`, Spring Modulith starters, `archunit-examples` derivatives, detected by file hash and path signature); at least 2 contributors; at least 6 months of activity; at least 1 release or tag. Expected retained sample: 4,000-6,000 repos for RQ1-3. Survivorship bias of default-branch code search is stated as a limitation. Other tools (Konsist, ArchUnitNET, deptrac, go-arch-lint, jQAssistant, eslint-boundaries, Nx) are reported by raw hit count in one RQ1 table.

**Subjects (RQ4).** Eligible repositories are Java/Kotlin projects whose first ArchUnit rule commit is preceded and followed by at least 12 months. The reported analysis replays the adopted dependency and layering subset on monthly snapshots of those repositories. A matched non-adopter panel was not built: the GHS/SEART control catalog was not obtainable, so there is no coarsened exact matching and no Callaway-Sant'Anna estimate.

**Variables.** Independent: adoption month on the treated series, tool, ecosystem, rule category, exemption mechanism. Dependent: RQ1 counts; RQ2 category distributions; RQ3 edit class, time to first loosening, exemption count; RQ4 source-level dependency and layering violation counts on the treated series. Covariates: age, LOC, contributors, commits/month, release cadence, churn.

**Ground truth.** Automatic edit classification validated on 300 stratified edits by two coders (R1, R2), Cohen's kappa target 0.75 or higher, disagreements resolved by R3. Rule categories are automatic. A 200-row sample was drawn for manual labels, but `gold_category` is empty, so Cohen's kappa and precision/recall for categories were not computed. Template detection validated on 100 repos.

**Rule archaeology.** For each treated repo, the rule set at adoption is replayed on 24 monthly snapshots (t=-12..+12): ArchUnit via a headless runner on compiled classes, with a source-level fallback (tree-sitter import graph plus a translator for the dependency/layering rule subset, coverage reported); import-linter and dependency-cruiser run natively on past trees.

**Baselines and metrics.** RQ4 reports the within-treated series. It does not use a matched-control trajectory, TWFE, or Callaway-Sant'Anna.

**Statistical analysis.** Bootstrap CIs; chi-square and Cramer's V; Kaplan-Meier and Cox hazard ratios. RQ4 intervals resample treated repositories. Callaway-Sant'Anna, placebo dates, negative controls and Rosenbaum/Oster bounds were not estimated, because there is no control group.

**Threats and mitigations.** Construct: generic erosion is not what rules govern, and the replay covers only the dependency and layering subset the source translator accepts. Internal: adoption is bundled with refactoring, and there is no control group, so the before-after series is not an effect of adoption. External: code-search survivorship and OSS-only sample, stated; template funnel reported. Conclusion: category comparisons use automatic labels. Reliability: rule categories have no gold labels and no Cohen's kappa; the file-selection predicates in `analysis/git_tree_sample.py` are not in the tree, so the stored file list cannot be regenerated; seeds for the validation draw and the bootstraps are pinned.

## 5. Artifact plan

**Contents:** `repos.csv` (id, ecosystem, tool, adoption date, funnel flags); `rules.jsonl` (subject, predicate, scope, exemptions, raw text, tool, file, commit); `edits.jsonl` with automatic and gold labels; `ci.csv`; `panels.parquet` (monthly violation and erosion series for treated and controls); three parsers and the canonical schema; R and Python analysis; codebook and funnel.

```
archrules/
  README.md LICENSE CITATION.cff Dockerfile uv.lock renv.lock Makefile
  parsers/{archunit,importlinter,depcruise}/  schema/canonical_rule.json
  pipeline/{discover,funnel,history,classify,ci,match,archaeology,panels}.py
  data/{repos.csv,rules.jsonl,edits.jsonl,ci.csv,panels.parquet}  data/checkpoints/
  analysis/{R,notebooks}/  docs/{codebook.md,funnel.md,pilot.md}
```

**Anonymization:** no names, affiliations, emails or institutional URLs; git history squashed; `CITATION.cff` placeholder; coders as R1/R2/R3; static snapshot on anonymous.4open.science; public GitHub identifiers only. **Reproducibility:** Python 3.11 via `uv.lock`, R via `renv.lock`, pinned ArchUnit 1.x, import-linter 2.x, dependency-cruiser 16.x, Docker image, fixed seeds for matching and bootstraps, Makefile stages that read checkpoints. **Licensing:** code MIT, data CC BY 4.0, rule text retained under source licences with an attribution file.

## 6. Work breakdown and schedule

| Date | Owner | Task | Output |
|---|---|---|---|
| Oct 9 | R1 | Scaffold repo, memguard wiring, sharded gh query script | `pipeline/discover.py` |
| Oct 10 | R1 | Run discovery for 3 tools; dedupe to repos | `data/repos_raw.csv` |
| Oct 11 | R2 | ArchUnit parser + canonical schema | `parsers/archunit/` |
| Oct 12 | R2, R3 | import-linter and dependency-cruiser parsers | `parsers/importlinter/`, `parsers/depcruise/` |
| Oct 13 | R1 | Inclusion funnel | `data/repos.csv`, `docs/funnel.md` |
| Oct 14 | all | **M1:** pilot on 300 repos, parser coverage report | `docs/pilot.md` |
| Oct 15 | R1 | Full history mining in batches | `data/edits_raw.jsonl` |
| Oct 16 | R2 | Automatic edit classifier + exemption mapping | `pipeline/classify.py` |
| Oct 17 | R1, R2 | Code 300 edits independently | `data/gold_edits.csv` |
| Oct 18 | R3 | Kappa, resolution; 200-rule category validation | kappa report |
| Oct 19 | R3 | CI detection on Actions workflows; ADR co-occurrence | `data/ci.csv` |
| Oct 20 | R1 | Treated-set selection, CEM + NN matching | `data/match.csv` |
| Oct 21 | all | **M2:** RQ1-3 tables, survival analysis; RQ5 keep/drop; NEMI trigger check | results v1 |
| Oct 22 | R1 | Rule archaeology runner on 20 repos | `pipeline/archaeology.py` |
| Oct 23 | R1 | Launch monthly panels under memguard | `data/panels.parquet` |
| Oct 24 | R2, R3 | Writing starts: Intro, Background, Method; RQ1-3 figures | sections 1-6 |
| Oct 25 | R1 | Panels continue; secondary outcome on sample | checkpoints |
| Oct 26 | R1 | Callaway-Sant'Anna, event study, placebo, bounds | `analysis/R/did.R` |
| Oct 27 | R1, R2 | RQ4 results, ratifier/reformer split; 90-day check-run snapshot (300 repos) | results v2 |
| Oct 28 | all | **M3: internal full draft** | `paper/draft1.pdf` |
| Oct 29 | R3 | Internal review; artifact packaging | artifact v1 |
| Oct 30 | R2 | **M4: abstract submitted** | EasyChair |
| Oct 31 | all | Revise; threats; related-work table | draft2 |
| Nov 1 | R3 | Anonymization check; anonymous.4open.science upload | artifact link |
| Nov 2 | all | Final figures, page budget, references | draft3 |
| Nov 3 | all | Proofread; double-anonymous compliance | final candidate |
| Nov 4 | R1 | **M5: submission** | EasyChair |

**NEMI fallback (Dec 20, 5 pages).** Trigger: at M2 (Oct 21) fewer than 150 eligible treated repos, or parser coverage below 70% of rules, or at Oct 27 fewer than 60% of panel snapshots complete. Then submit RQ1-3 as a NEMI paper ("Rule Rot: How Executable Architecture Rules Decay in Open Source"), hold RQ4 for a later full paper, and still submit the Oct 30 abstract to keep the research-track option open until Nov 4.

## 7. Compute and memory plan

**Estimates.** Discovery: hours, API-bound. History mining: 5K blob-less clones plus rule-file `log -p`, about 12 GB RAM at 16 workers, 60-100 GB transient disk. Panels: about 500 treated plus 1,000 controls x 24 snapshots = about 36K snapshot analyses; each worker holds one clone (median 50 MB, p95 1 GB) and a JVM at `-Xmx4g` or Node at `--max-old-space-size=3072`; peak project RAM 40-70 GB at 16 workers, well under the 200 GB ceiling; disk is binding (batches of 100 repos, clone-analyze-delete, 300 GB transient cap). No GPU. LLM API under $50 and optional; local `qwen2.5-coder:7b` via Ollama preferred with `-x llama-server`.

**Batching and checkpointing.** Each stage iterates over batches of 100 repos (history) or 50 (panels), appends to `data/checkpoints/<stage>.jsonl` after each batch and at least every 10 minutes, and skips items already present (idempotent per repo-snapshot). Rules and panels are streamed, never loaded whole.

**Command.**
```bash
tools/memguard.sh -t 200 -p 16 -x java -- python pipeline/panels.py --config cfg/panels.yaml
tools/memguard.sh -t 200 -p 4 -x llama-server -- python pipeline/classify.py --llm
```

**Environment variables.** Each script reads `MEMGUARD_PARALLEL` (default 8) to size its pool and `MEMGUARD_RESTART` (default 0); when greater than 0 it loads the latest checkpoint, logs the resume point and continues. Scripts run the `vm_stat` baseline check before starting.

**Restart slowly.** memguard kills the tree at 200 GB project RSS (or 470 GB host), waits until usage falls to 140 GB, halves `MEMGUARD_PARALLEL` (16 to 8 to 4), waits 30 s, and restarts from the checkpoint. Reduced parallelism is kept for the rest of the run and each incident is logged in `projectPlan.md`. Repos above 2 GB are routed to a single-worker queue, the most likely incident source.

## 8. Paper outline (10 pages + 2 references)

| Section | Pages | Content |
|---|---|---|
| 1 Introduction | 1.0 | Gap; contributions C1 map, C2 rot, C3 within-treated trajectory, C4 ArchRules |
| 2 Background and related work | 1.0 | Tools and exemption mechanisms; Table 1 positioning vs. closest works |
| 3 Study design | 1.5 | Fig. 1 pipeline; Table 2 funnel; canonical model; archaeology; within-treated replay |
| 4 RQ1 | 1.0 | Fig. 2 adoption over time by tool; Table 3 CI share (stratified) |
| 5 RQ2 | 1.0 | Fig. 3 categories by tool; Table 4 executable vs. NL taxonomy |
| 6 RQ3 | 1.5 | Table 5 edit classes with kappa; Fig. 4 survival; Fig. 5 exemption growth |
| 7 RQ4 | 1.5 | Within-treated violation trajectory; ratifier/reformer; no ATT |
| 8 Discussion (RQ5 sidebar, implications for AaC/CONTAaC, agents) | 1.0 | Implications table |
| 9 Threats to validity | 0.5 | |
| 10 Conclusion and artifact | 0.5 | ArchRules benchmark |
| References | 2.0 | separate budget |

## 9. Risks, mitigations, and pre-empted objections

| Risk | Likelihood | Mitigation |
|---|---|---|
| Code-search limits, 1,000 cap | High | Sharded queries; discovery on day 2; survivorship stated |
| Template/toy repos dominate | High | Hash/path detection; funnel reported; stricter-filter sensitivity |
| Treated set under 150 | Medium | NEMI trigger; power reported |
| Old snapshots fail to compile for ArchUnit | Medium | Source-level translator fallback; coverage reported |
| Panel pipeline overruns | Medium | One person full time from Oct 22; checkpoints; controls down to 1:1 |
| Canonical model lossy | Medium | Tool-stratified; raw text kept; coverage per tool |
| Memory incident on monorepos | Low | memguard, per-worker caps, single-worker queue |
| RQ5 underpowered | High | 200-PR threshold; sidebar or drop |

**Pre-empted reviewer-2 objections.**
1. *A before-after series is not an effect of adoption.* Agreed for this version. RQ4 states the within-treated trajectory and does not estimate an ATT. Adoption bundled with cleanup remains a confounder, and there is no control group to separate it.
2. *"10,000 repos, 10 tools" is not credible and the sample is toys.* Scope is three tools covering about 85% of hits, 4-6K retained repos after a published funnel, 200-600 treated; CI execution is tool-stratified; canonical coverage is reported per tool.
3. *RQ5 and "preceding events" are theme padding.* RQ5 is exploratory with a pre-set size threshold and framed as moderation of the Larsen & Moghaddam effect; preceding events are limited to observable signals; incidents and agent onboarding are removed.

## 10. Self-check against ICSA criteria

**Novelty.** Twenty-five literature queries found no mining study of executable architecture rules, their rot or their adoption effect; rule rot and rule archaeology are new constructs, and the paper positions itself against Pontillo et al., Lucena et al. and Larsen & Moghaddam rather than claiming an empty field.

**Relevance.** The study sits in CI/CD, continuous architecting and conformance checking, supplies the evidence base for two recent ICSA framework papers, and addresses the theme through the durability of rules under continuous and agent-assisted change.

**Rigor and soundness.** Published funnel and tool-stratified constructs. RQ2 categories are automatic and unvalidated. RQ4 is a within-treated description with bootstrap intervals and an explicit statement that no ATT was estimated.

**Verifiability and transparency.** ArchRules ships repo list, rules, gold edit labels, panels, parsers and analysis code with pinned environments and a Docker image on anonymous.4open.science; every number traces to a notebook cell.

**Presentation.** One pipeline figure, one positioning table, one event-study plot; each RQ in its own section within a 10-page budget; effect sizes with CIs; limitations stated up front.

## 11. References

1. Pontillo et al. Architecture as Code in Industry: A Multiple-Case Empirical Study. ICSA-C 2026. DOI 10.1109/icsa-c68850.2026.00017.
2. de Lima Lucena, Alves, Brunet. Can LLMs Turn Design Discussions into Architectural Tests? ECSA 2026. DOI 10.1007/978-3-032-39236-7_15.
3. Larsen, Moghaddam. Mining Architectural Quality Under Agentic AI Adoption: A Causal Study of Java Repositories. SEAA 2026. DOI 10.1007/978-3-032-36587-3_34.
4. Biazotto, Feitosa, Avgeriou, Nakagawa. Investigating CI/CD-based Technical Debt Management in Open-source Projects. arXiv 2604.10631, 2026.
5. A Few Pages of Markdown: Committed AI Configuration and Lower Quality Cost after Coding-Agent Adoption. arXiv 2608.25241, 2026.
6. Rule Taxonomy and Evolution in AI IDEs: A Mining and Survey Study. arXiv 2606.12231, 2026.
7. Zhang et al. Domain-Driven Design in Practice: A Mining Study of Maintenance and Evolution in Open-Source Repositories. arXiv 2606.23984, 2026.
8. Al-Asali, El-Ramly. Longitudinal Effects of Automated Static Analysis Adoption on GitHub Open Source Workflow Dynamics. Research Square 2026. [verify]
9. Architecture as Code. ICSA 2025. [verify authors]
10. CONTAaC: Continuous Architecting as Code. ICSA 2026. [verify authors]
11. Architecture in the Cradle: Early Warning of Architectural Decay with ArchGuard. ICSA 2026.
12. Evaluating LLMs for Detecting Architectural Design Rules Violations. ICSA 2026.
13. Architecture Decision Records: Adoption, Impact, and Developer Engagement in OSS. ICSA 2026.
14. Lifecycle of architecture technical debt (dependency approach). ICSA 2025.
15. Bakhtin, Esposito, Lenarduzzi, Taibi. Centrality Change Proneness. ECSA 2025.
16. Knodel, Popescu. A Comparison of Static Architecture Compliance Checking Approaches. WICSA 2007.
17. Pruijt et al. The accuracy of dependency analysis in static architecture compliance checking. SPE 2017.
18. Maffort et al. Mining architectural violations from version history. EMSE 2016.
19. Brunet et al. Do developers discuss design? MSR 2014.
20. Callaway, Sant'Anna. Difference-in-Differences with multiple time periods. J. Econometrics 2021.
21. Goodman-Bacon. Difference-in-differences with variation in treatment timing. J. Econometrics 2021.
22. Rosenbaum. Observational Studies, 2nd ed. Springer 2002.
23. Oster. Unobservable selection and coefficient stability: Theory and evidence. JBES 37(2), 2019.
24. Analyzing Linter Usage and Warnings Through Mining Software Repositories. MIPRO 2022. DOI 10.23919/mipro55190.2022.9803554.
25. Quieting the Static: A Study of Static Analysis Alert Suppressions. arXiv 2311.07482, 2023.
26. MSR 2026 agentic-PR studies: 10.1145/3793302.3793606, .3793603, .3793587, .3793588.
27. Vikhram. Beyond Code Smell: Measuring Architectural Conformance Drift in Long-Horizon Autonomous Coding Agent Sessions. Zenodo 2026. [verify]
28. AIDev dataset of agent-authored pull requests. [verify exact citation]
29. Dabic, Aghajani, Bavota. Sampling Projects in GitHub for MSR Studies (GHS). MSR 2021.
30. Arcan architectural smell detector, Fontana et al. [verify version]
