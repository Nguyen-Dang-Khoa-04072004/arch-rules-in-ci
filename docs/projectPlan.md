# projectPlan.md: Architecture Rules in the Wild (I26)

## Status
NOT STARTED, rank 5 of 5, final score 4.92.

Last updated: 2026-10-08

## Done
- [x] Plan written (plan.md)

## In progress
(empty)

## Next steps
1. [ ] Scaffold `archrules/` repo layout from plan.md section 5 and copy `tools/memguard.sh`; create `data/checkpoints/` and `cfg/`. (Oct 9, R1)
2. [ ] Write `pipeline/discover.py`: sharded `gh api search/code` queries (filename + size + path shards, 10 req/min backoff) for ArchUnit (`com.tngtech.archunit` in pom.xml/build.gradle(.kts)), import-linter (`[tool.importlinter]`, `.importlinter`), dependency-cruiser (`.dependency-cruiser.*`). Output `data/repos_raw.csv`. (Oct 9-10, R1)
3. [ ] Run discovery: `tools/memguard.sh -t 200 -p 4 -- python pipeline/discover.py --config cfg/discover.yaml`; checkpoint per shard to `data/checkpoints/discover.jsonl`. (Oct 10, R1)
4. [ ] Write `schema/canonical_rule.json` and `parsers/archunit/` (Java/Kotlin DSL subset: layeredArchitecture, noClasses/classes should..., slices cycles, FreezingArchRule, @ArchIgnore). (Oct 11, R2)
5. [ ] Write `parsers/importlinter/` (layers, forbidden, independence contracts, ignore_imports) and `parsers/depcruise/` (forbidden/allowed, exceptions, severity). (Oct 12, R2, R3)
6. [ ] Write `pipeline/funnel.py`: drop forks, archived, templates (JHipster TechnicalStructureTest.java, Spring Modulith starters, archunit-examples by hash/path), <2 contributors, <6 months activity, no release/tag. Output `data/repos.csv` plus funnel table `docs/funnel.md`. (Oct 13, R1)
7. [ ] Pilot on 300 repos (100 per tool): parser coverage report `docs/pilot.md`. Milestone M1. (Oct 14, all)
8. [ ] Write and run `pipeline/history.py` (`git log -p` on rule files, blob-less clones, batches of 100): `tools/memguard.sh -t 200 -p 16 -- python pipeline/history.py --config cfg/history.yaml`. Output `data/edits_raw.jsonl`. (Oct 15, R1)
9. [ ] Write `pipeline/classify.py`: automatic edit classes (add, tighten, loosen, exempt, disable, restructure) with per-tool exemption mapping. (Oct 16, R2)
10. [ ] Sample 300 stratified edits to `data/gold_edits_sample.csv`; R1 and R2 code independently; R3 computes kappa and resolves. Target kappa >= 0.75. (Oct 17-18)
11. [ ] Write `pipeline/ci.py`: GitHub Actions workflow parsing for tool execution; ADR/ARCHITECTURE.md co-occurrence. Output `data/ci.csv`. (Oct 19, R3)
12. [ ] Write `pipeline/match.py`: treated set (>=12 active months pre/post first ArchUnit commit), GHS/SEART Java controls, CEM + nearest-neighbour 2:1. Output `data/match.csv`. Then Milestone M2 decision on Oct 21: RQ5 keep/drop and NEMI trigger check. (Oct 20-21, R1)

## Blockers / open questions
- Does `gh` auth on this machine have code-search scope with enough quota for ~60 shards per tool? (verified 2026-10-08: 10 req/min, 1,000-result cap; confirm nothing changed before Oct 10.)
- ArchUnit retroactive execution requires compiling old snapshots; decide on Oct 22 whether the source-level translator fallback is the default for the dependency/layering subset.
- GHS/SEART catalog access and snapshot date for controls (download size, licence).
- AIDev dataset availability and PR-to-repo linkage for RQ5; threshold 200 PRs with check outcomes.
- Which ArchGuard/Arcan version to pin for the secondary outcome; Arcan licence for batch use.
- Coder availability: R1, R2, R3 placeholders need real assignment before Oct 17.

## How to resume in a new session
- Read `plan.md` in this folder first (design, schedule, memory plan).
- Read this file (`projectPlan.md`) to see Done / In progress / Next steps.
- Check `memguard.log` in the run directory for the last peak RAM and any restart events; keep the reduced parallelism if one occurred.
- Resume from the latest checkpoint in `data/checkpoints/` (every pipeline script honours `MEMGUARD_RESTART` > 0 and skips items already present).
- Update this file after every milestone (M1 Oct 14, M2 Oct 21, M3 Oct 28, M4 Oct 30, M5 Nov 4) and after any memory incident.

## Checkpoints
| What | Path | Last written |
|---|---|---|
| (none yet) | data/checkpoints/ | - |

## Memory incidents
| Time | Project RAM (GB) | Host RAM (GB) | Action taken | New parallelism |
|---|---|---|---|---|

## Decision log
| Date | Decision | Rationale |
|---|---|---|
| 2026-10-08 | Idea I26 selected as rank 5 of 5 (final score 4.92); plan written with hard downscope to 3 tools, 4-6K repos, Java-only DiD with rule archaeology, RQ5 exploratory | Verification feedback: novelty holds but original 10-tool/10K-repo/monthly-graph scope not deliverable by Nov 4; causal claim needs construct-valid outcome and sensitivity kit; NEMI fallback defined with explicit triggers |
| 2026-10-08 | Post-hoc clustering (ideas.md "Near-duplicate clusters", cluster 7) found I61 ("ArchRules-GT", rank 6) to be the same corpus as this idea. Decision: do NOT promote I61 separately; fold its Docker violation-replay harness, fix-vs-relax survival analysis and gold-labelled rule-edit corpus into this plan as the dataset contribution; keep its smell-validity AUC test as a secondary RQ or companion artifact paper (see ideas.md cluster 7 merge recipe). | Same ~10,000-repo executable-rule corpus and parsers; merging yields one stronger paper plus a citable artifact |
