"""Freeze the shared corpus and publish comparison tables when the four counts match."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
import math
from collections import Counter, defaultdict

from analysis.corpuslib import (
    COHORTS,
    CORPUS,
    CORPUS_FIELDS,
    DATA,
    DEV_LIMIT,
    EXCLUDED,
    RQ1,
    RQ2,
    RQ3,
    RQ4,
    STATS_JSON,
    STRUCTURAL,
    TOOLS,
    TOOL_OF,
    append_exclusion,
    assert_files_hash,
    bootstrap,
    clone_path,
    compare_counts,
    counts_from_repos,
    ensure_dirs,
    exclusion_row,
    history_status,
    in_cohort,
    load_adoption,
    load_ci,
    load_corpus,
    load_rq2_subjects,
    read_csv,
    rel_clone,
    subject_key,
    write_attrition,
    write_counts,
    write_csv,
)

# H1.1 is import-linter and dependency-cruiser. ArchUnit is descriptive.
H11 = ("PypiCrawler", "NpmCrawler")
CATEGORIES = ["dependency", "layering", "cycle", "naming", "visibility", "annotation", "other", "unparsed"]
YEARS = ["pre-2017", *[str(year) for year in range(2017, 2027)], "missing"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True, choices=("corpus", "tables"))
    args = parser.parse_args()
    ensure_dirs()
    assert_files_hash()
    if args.phase == "corpus":
        freeze_corpus()
        return
    write_tables()


def freeze_corpus() -> None:
    latest = history_status()
    subjects = [row for row in load_rq2_subjects() if row["status"] == "complete"]
    if len(latest) < len(subjects):
        raise SystemExit(f"history is incomplete: {len(latest)} of {len(subjects)}")
    adoption = load_adoption()
    ci = load_ci()
    already = {subject_key(row["repository_id"], row["strategy"]) for row in read_csv(EXCLUDED)}
    rows = []
    for subject in subjects:
        status = latest.get(subject["key"])
        if not status:
            raise SystemExit(f"missing history checkpoint for {subject['repository_full_name']}")
        if status.get("status") != "complete":
            continue
        dest = clone_path(subject["repository_id"], subject["strategy"])
        if not dest.exists():
            if subject["key"] not in already:
                append_exclusion(exclusion_row(
                    subject, "clone_error", "clone directory missing after history", adoption, ci,
                ))
                already.add(subject["key"])
            continue
        rows.append({
            "repository_id": subject["repository_id"],
            "repository_full_name": subject["repository_full_name"],
            "tool": subject["tool"],
            "strategy": subject["strategy"],
            "reason": subject["reason"],
            "sample_index": subject["sample_index"],
            "n_files": subject["n_files"],
            "n_candidates": subject["n_candidates"],
            "clone_dir": rel_clone(subject["repository_id"], subject["strategy"]),
            "head_sha": status.get("head_sha") or "",
        })
    rows.sort(key=lambda row: (row["strategy"], int(row["repository_id"])))
    write_csv(CORPUS, rows, CORPUS_FIELDS)
    write_attrition()
    counts = counts_from_repos(rows)
    print(
        "corpus "
        + " ".join(f"{row['cohort']}:{row['tool']}={row['n']}" for row in counts),
        flush=True,
    )


def write_tables() -> None:
    corpus = load_corpus()
    if not corpus:
        raise SystemExit("data/corpus.csv is empty")
    _write_rq1_data(corpus)
    _write_rq2_data(corpus)
    if not (RQ3 / "counts.csv").exists() or not (RQ4 / "counts.csv").exists():
        raise SystemExit("RQ3 and RQ4 count files must exist before summaries")
    ok, problems = compare_counts()
    if not ok:
        print("count check failed", flush=True)
        for problem in problems:
            print(problem, flush=True)
        raise SystemExit(1)
    _write_rq1_summaries(corpus)
    _write_rq2_summaries(corpus)
    _write_rq3_summaries()
    _write_rq4_summary()
    _write_comparison_summary(corpus)
    assert_files_hash()
    print("comparison summaries written; four-way count check passed", flush=True)


def _write_rq1_data(corpus: list[dict]) -> None:
    adoption = load_adoption()
    ci = load_ci()
    joined = []
    for row in corpus:
        adopted = adoption.get(subject_key(row["repository_id"], row["strategy"]), {})
        scanned = ci.get(subject_key(row["repository_id"], row["strategy"]), {})
        date = adopted.get("adoption_date") or ""
        joined.append({
            **row,
            "adoption_date": date,
            "adoption_year": adopted.get("adoption_year") or (date[:4] if len(date) >= 4 else ""),
            "adoption_status": adopted.get("status") or "",
            "ci": scanned.get("ci") or "",
        })
    fields = [
        "repository_id", "repository_full_name", "strategy", "tool", "reason", "sample_index",
        "adoption_date", "adoption_year", "adoption_status", "ci",
    ]
    for cohort in COHORTS:
        rows = [row for row in joined if in_cohort(row["reason"], cohort)]
        write_csv(RQ1 / cohort / "repos.csv", rows, fields)
        _write_rq1_numeric(RQ1 / cohort, rows)
    write_counts(RQ1 / "counts.csv", corpus)


def _write_rq1_numeric(folder: Path, repos: list[dict]) -> None:
    hist_rows = []
    by_tool_year: dict[str, Counter] = defaultdict(Counter)
    for row in repos:
        year = row["adoption_year"]
        if not year:
            label = "missing"
        elif int(year) < 2017:
            label = "pre-2017"
        elif int(year) > 2026:
            label = "missing"
        else:
            label = year
        by_tool_year[row["strategy"]][label] += 1
    for strategy in TOOL_OF:
        total = sum(by_tool_year[strategy].values())
        dated = total - by_tool_year[strategy]["missing"]
        for label in YEARS:
            count = by_tool_year[strategy][label]
            share = count / total if total else 0
            dated_share = count / dated if dated and label != "missing" else 0
            hist_rows.append({
                "strategy": strategy,
                "tool": TOOL_OF[strategy],
                "year": label,
                "count": count,
                "share_of_tool": f"{share:.4f}",
                "share_of_dated": "" if label == "missing" else f"{dated_share:.4f}",
            })
    write_csv(folder / "adoption_hist.csv", hist_rows, [
        "strategy", "tool", "year", "count", "share_of_tool", "share_of_dated",
    ])
    ci_rows = []
    for strategy, tool in TOOL_OF.items():
        rows = [row for row in repos if row["strategy"] == strategy]
        known = [row for row in rows if row["ci"] in ("true", "false")]
        flags = [row["ci"] == "true" for row in known]
        estimate = bootstrap(flags)
        point = low = high = ""
        if estimate:
            point, low, high = (f"{estimate[0]:.4f}", f"{estimate[1]:.4f}", f"{estimate[2]:.4f}")
        ci_rows.append({
            "strategy": strategy,
            "tool": tool,
            "rows": len(rows),
            "known": len(known),
            "unknown": len(rows) - len(known),
            "ci_true": sum(flags),
            "share": point,
            "ci_low": low,
            "ci_high": high,
            "h11": "yes" if strategy in H11 else "no",
        })
    write_csv(folder / "ci_rates.csv", ci_rows, list(ci_rows[0].keys()))
    folder.joinpath("rates.json").write_text(json.dumps({
        "by_tool_year": {key: dict(value) for key, value in by_tool_year.items()},
        "ci_rows": ci_rows,
        "n": len(repos),
        "unique": len({row["repository_id"] for row in repos}),
    }) + "\n", encoding="utf-8")


def _write_rq1_summaries(corpus: list[dict]) -> None:
    for cohort in COHORTS:
        folder = RQ1 / cohort
        payload = json.loads((folder / "rates.json").read_text(encoding="utf-8"))
        repos = read_csv(folder / "repos.csv")
        lines = [
            f"# RQ1 {cohort}",
            "",
            "Comparison sample: `data/corpus.csv`.",
            f"Rows (repository x tool): {payload['n']}",
            f"Unique repositories: {payload['unique']}",
            "",
            "## Adoption year",
        ]
        by_tool_year: dict[str, Counter] = defaultdict(Counter)
        for key, value in payload["by_tool_year"].items():
            by_tool_year[key].update(value)
        for strategy in TOOL_OF:
            total = sum(by_tool_year[strategy].values())
            dated = total - by_tool_year[strategy]["missing"]
            lines.append(f"### {TOOL_OF[strategy]} n={total} dated={dated}")
            for label in YEARS:
                count = by_tool_year[strategy][label]
                if count:
                    lines.append(f"- {label}: {count} ({count / total:.1%} of tool)" if total else f"- {label}: {count}")
            lines.append("")
        lines.append("## CI share")
        h11_flags: list[bool] = []
        h11_by_strategy: dict[str, list[bool]] = {strategy: [] for strategy in H11}
        for strategy in TOOL_OF:
            rows = [row for row in repos if row["strategy"] == strategy]
            known = [row for row in rows if row["ci"] in ("true", "false")]
            flags = [row["ci"] == "true" for row in known]
            estimate = bootstrap(flags)
            lines.append(f"### {TOOL_OF[strategy]}")
            lines.append(f"- scanned with a result: {len(known)} / {len(rows)} (unknown {len(rows) - len(known)})")
            if estimate:
                point, low, high = estimate
                lines.append(f"- share: {point:.3f} (95% bootstrap CI {low:.3f}–{high:.3f})")
            if strategy in H11:
                h11_flags.extend(flags)
                h11_by_strategy[strategy] = flags
            lines.append("")
        lines.append("## H1.1")
        lines.append("Denominator is import-linter and dependency-cruiser rows with a CI result. ArchUnit is descriptive only.")
        for strategy in H11:
            lines.append(f"- {TOOL_OF[strategy]}: {_format_h11(bootstrap(h11_by_strategy[strategy]))}")
        lines.append(f"- pooled: {_format_h11(bootstrap(h11_flags))}")
        lines.append(f"- pooled unique repositories: {_format_h11(bootstrap(_deduped_h11(repos)))}")
        (folder / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        _write_histogram(folder / "adoption_year.svg", by_tool_year)
    del corpus


def _format_h11(estimate) -> str:
    if not estimate:
        return "no observations"
    point, low, high = estimate
    return (
        f"{point:.3f} (95% CI {low:.3f}–{high:.3f}); "
        f"interval lies entirely below 0.50: {'yes' if high < 0.50 else 'no'}"
    )


def _deduped_h11(repos: list[dict]) -> list[bool]:
    by_repo: dict[str, list[bool]] = defaultdict(list)
    for row in repos:
        if row["strategy"] not in H11 or row["ci"] not in ("true", "false"):
            continue
        by_repo[row["repository_id"]].append(row["ci"] == "true")
    return [any(flags) for flags in by_repo.values()]


def _write_histogram(path: Path, by_tool_year: dict[str, Counter]) -> None:
    tools = list(TOOL_OF)
    width, height = 960, 420
    margin_left, margin_bottom = 48, 70
    plot_width = width - margin_left - 20
    plot_height = height - margin_bottom - 20
    max_count = max((by_tool_year[tool][year] for tool in tools for year in YEARS), default=1) or 1
    group = plot_width / len(YEARS)
    bar = group / (len(tools) + 1)
    colors = {"MavenCrawler": "#4c78a8", "NpmCrawler": "#f58518", "PypiCrawler": "#54a24b"}
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="white"/>',
    ]
    for index, year in enumerate(YEARS):
        for tool_index, tool in enumerate(tools):
            count = by_tool_year[tool][year]
            bar_height = plot_height * count / max_count
            x = margin_left + index * group + tool_index * bar
            y = 20 + plot_height - bar_height
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar - 2:.1f}" height="{bar_height:.1f}" fill="{colors[tool]}"/>'
            )
        anchor = margin_left + index * group + group / 2
        parts.append(
            f'<text x="{anchor:.1f}" y="{height - 36}" font-size="11" text-anchor="end" '
            f'transform="rotate(-45 {anchor:.1f},{height - 36})">{year}</text>'
        )
    legend_x = margin_left
    for tool in tools:
        parts.append(f'<rect x="{legend_x}" y="{height - 18}" width="12" height="12" fill="{colors[tool]}"/>')
        parts.append(f'<text x="{legend_x + 16}" y="{height - 8}" font-size="12">{TOOL_OF[tool]}</text>')
        legend_x += 160
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def _write_rq2_data(corpus: list[dict]) -> None:
    keys = {subject_key(row["repository_id"], row["strategy"]) for row in corpus}
    held: dict[str, list[dict]] = {cohort: [] for cohort in COHORTS}
    with (RQ2 / "constructs_full.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if subject_key(str(row["repository_id"]), row["strategy"]) not in keys:
                continue
            sample_index = int(row.get("sample_index") or 0)
            if row.get("dev") or sample_index < DEV_LIMIT:
                continue
            if not row.get("category"):
                row = {**row, "category": "unparsed"}
            for cohort in COHORTS:
                if in_cohort(row.get("reason") or "", cohort):
                    held[cohort].append(row)
    fields = ["repository_id", "repository_full_name", "strategy", "tool", "reason", "sample_index"]
    for cohort in COHORTS:
        repos = [row for row in corpus if in_cohort(row["reason"], cohort)]
        write_csv(RQ2 / cohort / "repos.csv", repos, fields)
        _write_rules(RQ2 / cohort / "rules.jsonl", held[cohort])
        _write_category_csv(RQ2 / cohort / "category_counts.csv", held[cohort])
        (RQ2 / cohort / "h21.json").write_text(
            json.dumps(_h21_payload(held[cohort]), indent=2) + "\n",
            encoding="utf-8",
        )
    write_counts(RQ2 / "counts.csv", corpus)


def _write_rules(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps({
                "repository_id": row.get("repository_id"),
                "repository_full_name": row.get("repository_full_name"),
                "strategy": row.get("strategy"),
                "reason": row.get("reason"),
                "sample_index": row.get("sample_index"),
                "file": row.get("file"),
                "construct": row.get("construct"),
                "category": row.get("category"),
                "subtype": row.get("subtype") or "",
                "subject": row.get("subject") or "",
                "exemption": row.get("exemption"),
            }, ensure_ascii=False) + "\n")


def _write_category_csv(path: Path, rows: list[dict]) -> None:
    table = Counter((row["strategy"], row.get("category") or "unparsed") for row in rows)
    present = [cat for cat in CATEGORIES if any(table[(strategy, cat)] for strategy in TOOL_OF)]
    extra = sorted({cat for _, cat in table} - set(present))
    categories = present + extra
    out = []
    for strategy in TOOL_OF:
        for cat in categories:
            out.append({
                "strategy": strategy,
                "tool": TOOL_OF[strategy],
                "category": cat,
                "count": table[(strategy, cat)],
            })
    write_csv(path, out, ["strategy", "tool", "category", "count"])


def _h21_payload(rows: list[dict]) -> dict:
    table = Counter((row["strategy"], row.get("category") or "unparsed") for row in rows)
    flags = {}
    for strategy in TOOL_OF:
        values = []
        for (tool, cat), count in table.items():
            if tool != strategy or cat == "unparsed":
                continue
            values.extend([cat in STRUCTURAL] * count)
        flags[strategy] = values
    estimates = {strategy: _triple(bootstrap(flags[strategy])) for strategy in TOOL_OF}
    categories = [cat for cat in CATEGORIES if cat != "unparsed" and any(table[(s, cat)] for s in TOOL_OF)]
    chi2, dof, p_value, cramer = _cramer(table, list(TOOL_OF), categories)
    return {
        "constructs": len(rows),
        "table": {f"{strategy}|{cat}": table[(strategy, cat)] for strategy in TOOL_OF for cat in CATEGORIES},
        "h21": estimates,
        "chi2": chi2,
        "dof": dof,
        "p": p_value,
        "cramer": cramer,
    }


def _cramer(table: Counter, strategies: list[str], categories: list[str]) -> tuple[float, int, float, float]:
    if len(categories) < 2:
        return 0.0, 0, 1.0, 0.0
    observed = []
    for strategy in strategies:
        observed.append([table[(strategy, cat)] for cat in categories])
    row_sums = [sum(row) for row in observed]
    col_sums = [sum(observed[row][col] for row in range(len(strategies))) for col in range(len(categories))]
    total = sum(row_sums)
    if total == 0:
        return 0.0, 0, 1.0, 0.0
    chi2 = 0.0
    for row, row_sum in enumerate(row_sums):
        for col, col_sum in enumerate(col_sums):
            expected = row_sum * col_sum / total
            if expected:
                chi2 += (observed[row][col] - expected) ** 2 / expected
    dof = (len(strategies) - 1) * (len(categories) - 1)
    p_value = _chi2_sf(chi2, dof) if dof else 1.0
    cramer = math.sqrt(chi2 / (total * (min(len(strategies), len(categories)) - 1))) if total else 0.0
    return chi2, dof, p_value, cramer


def _chi2_sf(x: float, k: int) -> float:
    if k <= 0 or x <= 0:
        return 1.0
    return _gammaincc(k / 2, x / 2)


def _gammaincc(a: float, x: float) -> float:
    if x <= 0:
        return 1.0
    if x < a + 1:
        return 1 - _gammainc_series(a, x)
    return _gamma_cf(a, x)


def _gammainc_series(a: float, x: float) -> float:
    term = 1 / a
    total = term
    for n in range(1, 200):
        term *= x / (a + n)
        total += term
        if abs(term) < abs(total) * 1e-12:
            break
    return total * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _gamma_cf(a: float, x: float) -> float:
    tiny = 1e-30
    b = x + 1 - a
    c = 1 / tiny
    d = 1 / b
    h = d
    for i in range(1, 200):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1 / d
        delta = d * c
        h *= delta
        if abs(delta - 1) < 1e-12:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def _triple(estimate) -> dict | None:
    if estimate is None:
        return None
    point, low, high = estimate
    return {"point": point, "low": low, "high": high, "above_0.70": low > 0.70}


def _write_rq2_summaries(corpus: list[dict]) -> None:
    for cohort in COHORTS:
        payload = json.loads((RQ2 / cohort / "h21.json").read_text(encoding="utf-8"))
        repos = read_csv(RQ2 / cohort / "repos.csv")
        lines = [
            f"# RQ2 {cohort}",
            "",
            "Comparison N is the frozen corpus. Category counts and H2.1 use held-out construct rows only.",
            "The first 1000 kept+extended funnel rows stay out of H2.1. The structural family is dependency and layering.",
            f"Comparison repository x tool: {len(repos)}",
            f"Held-out constructs: {payload['constructs']}",
            "",
            "## Coverage and categories",
        ]
        table = payload["table"]
        for strategy in TOOL_OF:
            parsed = sum(table.get(f"{strategy}|{cat}", 0) for cat in CATEGORIES if cat != "unparsed")
            unparsed = table.get(f"{strategy}|unparsed", 0)
            seen = parsed + unparsed
            lines.append(f"### {TOOL_OF[strategy]}")
            lines.append(f"- coverage: {parsed}/{seen} ({(parsed / seen if seen else 0):.1%})")
            for cat in CATEGORIES:
                count = table.get(f"{strategy}|{cat}", 0)
                if not count:
                    continue
                if cat == "unparsed":
                    lines.append(f"- {cat}: {count}")
                else:
                    lines.append(f"- {cat}: {count} ({count / parsed:.1%} of parsed)" if parsed else f"- {cat}: {count}")
            lines.append("")
        lines.append(
            f"chi-square: {payload['chi2']:.3f}, df={payload['dof']}, p={payload['p']:.4g}, Cramer's V={payload['cramer']:.3f}"
        )
        lines.extend(["", "## H2.1 dependency and layering", ""])
        for strategy in TOOL_OF:
            estimate = payload["h21"].get(strategy)
            if not estimate:
                lines.append(f"- {TOOL_OF[strategy]}: no observations")
                continue
            lines.append(
                f"- {TOOL_OF[strategy]}: {estimate['point']:.3f} "
                f"(95% CI {estimate['low']:.3f}–{estimate['high']:.3f}); "
                f"interval lies entirely above 0.70: {'yes' if estimate['above_0.70'] else 'no'}"
            )
        lines.extend(["", "## Comparison", "", "See data/RQ2/codebook.md. Categories without a Lucena counterpart stay separate."])
        (RQ2 / cohort / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    del corpus


def _write_rq3_summaries() -> None:
    payload = json.loads(STATS_JSON.read_text(encoding="utf-8"))
    for cohort in COHORTS:
        block = payload[cohort]
        lines = [
            f"# RQ3 {cohort}",
            "",
            "Comparison sample: `data/corpus.csv`.",
            f"Repository x tool: {block['n_repos']}",
            f"Rule files: {block['n_files']}",
            f"Edits: {block['n_edits']}",
            "",
            "## Edit classes",
            "",
        ]
        for name, count in sorted(block["edit_classes"].items(), key=lambda item: -item[1]):
            share = block["edit_class_share"].get(name, 0)
            lines.append(f"- {name}: {count} ({share:.1%})")
        lines.extend(["", "## H3.1 exemption or disable within 24 months", ""])
        lines.extend(_h31_lines(block["h31"]))
        lines.extend(["", "## H3.2 never modified", ""])
        lines.extend(_h32_lines(block["h32"]))
        lines.extend(["", "## Survival to first loosen or exempt", ""])
        survival = block["survival_loosen_or_exempt"]
        km = survival.get("km_incidence_24")
        if km:
            lines.append(
                f"- Kaplan-Meier incidence at 24 months: {km['point']:.3f} "
                f"(95% bootstrap CI {km['low']:.3f}–{km['high']:.3f})"
            )
        cox = survival.get("cox") or {}
        lines.append(f"- Cox converged: {cox.get('converged')}")
        for estimate in cox.get("estimates") or []:
            lines.append(
                f"- {estimate['name']}: HR {estimate['hr']:.3f} "
                f"(95% CI {estimate.get('ci_low', float('nan')):.3f}–{estimate.get('ci_high', float('nan')):.3f})"
            )
        lines.extend(["", "## By tool", ""])
        for tool in TOOLS:
            tool_block = block["by_tool"][tool]
            lines.append(f"### {tool}")
            lines.append(f"- files: {tool_block['n_files']}")
            h31 = tool_block["h31"]["km_incidence_24"]
            h32 = tool_block["h32"]
            if h31:
                lines.append(f"- H3.1 at 24 months: {h31['point']:.3f} (95% CI {h31['low']:.3f}–{h31['high']:.3f})")
            if h32.get("point") is not None:
                lines.append(f"- H3.2 never modified: {h32['point']:.3f} (95% CI {h32['low']:.3f}–{h32['high']:.3f})")
            lines.append("")
        (RQ3 / cohort / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _h31_lines(block: dict) -> list[str]:
    km = block.get("km_incidence_24")
    lines = [f"- files: {block.get('n_files', 0)}"]
    if km:
        lines.append(
            f"- Kaplan-Meier incidence: {km['point']:.3f} "
            f"(95% bootstrap CI {km['low']:.3f}–{km['high']:.3f})"
        )
    lines.append(f"- point estimate is at least 30%: {'yes' if block.get('meets_30') else 'no'}")
    complete = block.get("complete_case")
    if complete:
        lines.append(
            f"- complete case ({complete['n']} files): {complete['point']:.3f} "
            f"(95% CI {complete['low']:.3f}–{complete['high']:.3f})"
        )
    return lines


def _h32_lines(block: dict) -> list[str]:
    if block.get("point") is None:
        return ["- no files"]
    return [
        f"- never modified: {block['n_never']} / {block['n_files']}",
        f"- share: {block['point']:.3f} (95% bootstrap CI {block['low']:.3f}–{block['high']:.3f})",
        f"- below 73.8%: {'yes' if block['below_0.738'] else 'no'}",
        f"- interval lies entirely below 73.8%: {'yes' if block['interval_entirely_below_0.738'] else 'no'}",
    ]


def _write_rq4_summary() -> None:
    summary = json.loads((RQ4 / "replay_summary.json").read_text(encoding="utf-8"))
    panel = read_csv(RQ4 / "panel_eligibility.csv")
    lines = [
        "# RQ4",
        "",
        "ArchUnit rows of `data/corpus.csv`. Adoption is the first RQ3 commit that introduces an ArchUnit rule.",
        "Ineligible repositories stay in the sample. The 12-month window only labels the treated subset.",
        f"ArchUnit N: {len(panel)}",
        f"Treated: {summary.get('treated')}",
        f"Panel ran: {summary.get('panel_ran')}",
        "",
        summary.get("reason") or "",
        "",
    ]
    if summary.get("panel_ran"):
        lines.extend([
            "## Ratify and reform",
            "",
            f"- replayed: {summary.get('replayed')}",
            f"- classified (t=-1 and t=0 observed): {summary.get('classified')}",
            f"- ratifier (violations at t=-1 are 0): {summary.get('ratifier_n')} ({_pct(summary.get('ratifier_share'))})",
            f"- reformer (a pre-adoption violation and 0 at t=0): {summary.get('reformer_n')} ({_pct(summary.get('reformer_share'))})",
            f"- both: {summary.get('both_n')}",
            f"- mean dependency/layering coverage: {_pct(summary.get('mean_family_coverage'))}",
            f"- mean evaluable coverage: {_pct(summary.get('mean_evaluable_coverage'))}",
            "",
        ])
    did = summary.get("did") or {}
    lines.extend([
        "## Difference in differences",
        "",
        f"- ran: {did.get('ran')}",
        f"- {did.get('reason')}",
        "",
    ])
    pilot_path = RQ4 / "compile_pilot.json"
    if pilot_path.exists():
        pilot = json.loads(pilot_path.read_text(encoding="utf-8"))
        lines.extend([
            "## Compile pilot",
            "",
            f"- compiled: {pilot.get('compiled')} / {pilot.get('n')} ({_pct(pilot.get('share'))})",
            "",
            "The pilot is not the panel result.",
            "",
        ])
    (RQ4 / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_comparison_summary(corpus: list[dict]) -> None:
    ok, problems = compare_counts()
    counts = counts_from_repos(corpus)
    excluded = read_csv(EXCLUDED)
    failures = [row for row in excluded if row.get("exclusion_reason") == "clone_error"]
    history = Counter(row.get("status") or "" for row in history_status().values())
    stats = json.loads(STATS_JSON.read_text(encoding="utf-8")) if STATS_JSON.exists() else {}
    replay = json.loads((RQ4 / "replay_summary.json").read_text(encoding="utf-8"))
    lines = [
        "# Comparison summary",
        "",
        f"Four-way count check: {'passed' if ok else 'FAILED'}.",
        "",
        "## Corpus N",
        "",
    ]
    for row in counts:
        lines.append(f"- {row['cohort']} {row['tool']}: {row['n']}")
    lines.extend(["", "## Exclusions", ""])
    bucket = Counter((row["exclusion_reason"], row["tool"]) for row in excluded)
    for reason in ("unavailable", "no_rule_file", "clone_error"):
        for tool in TOOLS:
            lines.append(f"- {reason} {tool}: {bucket[(reason, tool)]}")
    lines.extend([
        "",
        "## History",
        "",
        f"- complete: {history['complete']}",
        f"- excluded: {history['excluded']}",
        f"- checkpoints: {sum(history.values())}",
        "",
        "Clones: `data/RQ3/clones/<repository_id>__<strategy>`.",
        "",
        "## H3",
        "",
    ])
    for cohort in COHORTS:
        block = stats.get(cohort) or {}
        h31 = (block.get("h31") or {}).get("km_incidence_24") or {}
        h32 = block.get("h32") or {}
        lines.append(
            f"- {cohort} H3.1: {h31.get('point')} (CI {h31.get('low')}–{h31.get('high')}); "
            f"H3.2: {h32.get('point')} (CI {h32.get('low')}–{h32.get('high')})"
        )
    lines.extend([
        "",
        "## RQ4",
        "",
        f"- treated: {replay.get('treated')}",
        f"- panel ran: {replay.get('panel_ran')}",
        f"- DiD ran: {(replay.get('did') or {}).get('ran')}",
        f"- {(replay.get('did') or {}).get('reason')}",
        "",
        "## Clone failures",
        "",
    ])
    if not failures:
        lines.append("- none")
    for row in failures:
        lines.append(f"- {row['repository_full_name']} ({row['tool']}, {row['reason']}): {row['error']}")
    if problems:
        lines.extend(["", "## Count mismatches", ""])
        lines.extend(f"- {problem}" for problem in problems)
    (DATA / "comparison_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _pct(value) -> str:
    if not isinstance(value, (int, float)):
        return "n/a"
    return f"{value:.1%}"


if __name__ == "__main__":
    main()
