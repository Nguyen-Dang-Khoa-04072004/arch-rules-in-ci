"""RQ1 on the locked corpus.

Checks kept and extended repositories once, then writes rates for two sets:
data/RQ1/no_extend (kept only) and data/RQ1/with_extend (kept + extended).
"""

from __future__ import annotations

import base64
import csv
import json
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from github.client import GithubClient, RateLimiter  # noqa: E402

OUT = ROOT / "data" / "RQ1"
CHECKPOINT = OUT / "checkpoints"
SEED = 20261018
BOOTSTRAP_DRAWS = 1000

TOOL_OF = {
    "MavenCrawler": "ArchUnit",
    "PypiCrawler": "import-linter",
    "NpmCrawler": "dependency-cruiser",
}
H11_STRATEGIES = ("PypiCrawler", "NpmCrawler")

PATTERNS = {
    "MavenCrawler": re.compile(
        r"(?:^|[\s;&|])(?:\./)?(?:mvnw?|gradlew?)\b[^\n]*\b(?:test|verify|check|build)\b",
        re.IGNORECASE,
    ),
    "PypiCrawler": re.compile(
        r"\b(?:lint-imports|import-linter|importlinter)\b",
        re.IGNORECASE,
    ),
    "NpmCrawler": re.compile(
        r"\b(?:depcruise|dependency-cruiser)\b",
        re.IGNORECASE,
    ),
}

OTHER_TOOLS = [
    ("Konsist", '"com.lemonappdev:konsist"'),
    ("ArchUnitNET", "TngTech.ArchUnitNET"),
    ("deptrac", '"deptrac" filename:deptrac.yaml'),
    ("go-arch-lint", '"version" filename:.go-arch-lint.yml'),
    ("jQAssistant", '"jqassistant" filename:pom.xml'),
    ("eslint-plugin-boundaries", '"eslint-plugin-boundaries"'),
    ("Nx", '"@nx/enforce-module-boundaries"'),
]

_checkpoint_lock = threading.Lock()


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    subjects = load_subjects()
    kept = sum(1 for row in subjects if row["reason"] == "kept")
    extended = sum(1 for row in subjects if row["reason"] == "extended")
    print(f"subjects kept={kept} extended={extended} union={len(subjects)}", flush=True)

    client = GithubClient(
        min_interval=6.5,
        repo_limiter=RateLimiter(0.8),
    )
    run_other_tools(client)
    run_ci(client, subjects)
    run_adoption(subjects)
    write_funnel()
    write_cohort("no_extend", [row for row in subjects if row["reason"] == "kept"])
    write_cohort("with_extend", subjects)
    print("RQ1 outputs written under data/RQ1", flush=True)


def load_subjects() -> list[dict]:
    paths: dict[tuple[str, str], list[str]] = defaultdict(list)
    with (ROOT / "data" / "repos_raw.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            key = (row["repository_id"], row["strategy"])
            path = row.get("path") or ""
            if path and path not in paths[key]:
                paths[key].append(path)

    subjects = []
    with (ROOT / "data" / "funnel_pilot.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("reason") not in ("kept", "extended"):
                continue
            key = (row["repository_id"], row["strategy"])
            subjects.append({
                "repository_id": row["repository_id"],
                "repository_full_name": row["repository_full_name"],
                "strategy": row["strategy"],
                "reason": row["reason"],
                "paths": paths.get(key, []),
            })
    return subjects


def run_other_tools(client: GithubClient) -> None:
    path = CHECKPOINT / "other_tools.jsonl"
    done = _load_checkpoint(path)
    finished = {row["tool"] for row in done.values() if row.get("tool")}
    for tool, query in OTHER_TOOLS:
        if tool in finished:
            print(f"other-tools: skip {tool}", flush=True)
            continue
        print(f"other-tools: {tool} {query}", flush=True)
        try:
            payload = client.search_code(query, page=1, per_page=1)
            row = {
                "tool": tool,
                "query": query,
                "total_count": int(payload.get("total_count") or 0),
                "incomplete_results": bool(payload.get("incomplete_results")),
                "error": "",
            }
        except (ValueError, RuntimeError) as exc:
            row = {
                "tool": tool,
                "query": query,
                "total_count": "",
                "incomplete_results": "",
                "error": str(exc)[:300],
            }
        _append_checkpoint(path, row)
        done[tool] = row
    _write_csv(
        OUT / "other_tools.csv",
        [
            {
                "tool": tool,
                "query": done[tool].get("query", query),
                "total_count": done[tool].get("total_count", ""),
                "incomplete_results": done[tool].get("incomplete_results", ""),
                "error": done[tool].get("error", ""),
            }
            for tool, query in OTHER_TOOLS
            if tool in done
        ],
        ["tool", "query", "total_count", "incomplete_results", "error"],
    )


def run_ci(client: GithubClient, subjects: list[dict]) -> None:
    path = CHECKPOINT / "ci.jsonl"
    done = _load_checkpoint(path)
    pending = [row for row in subjects if _subject_key(row) not in done or done[_subject_key(row)].get("status") == "error"]
    print(f"ci: {len(subjects) - len(pending)} done, {len(pending)} to scan", flush=True)
    for index, subject in enumerate(pending, start=1):
        result = _scan_ci(client, subject)
        _append_checkpoint(path, result)
        done[_subject_key(subject)] = result
        if index % 25 == 0 or index == len(pending):
            print(f"ci: {index}/{len(pending)} {subject['repository_full_name']} ci={result['ci']}", flush=True)
    _write_joined_csv(OUT / "ci.csv", subjects, done, [
        "repository_id", "repository_full_name", "strategy", "reason",
        "tool", "ci", "workflows", "error",
    ])


def _scan_ci(client: GithubClient, subject: dict) -> dict:
    base = {
        "key": _subject_key(subject),
        "repository_id": subject["repository_id"],
        "repository_full_name": subject["repository_full_name"],
        "strategy": subject["strategy"],
        "reason": subject["reason"],
        "tool": TOOL_OF.get(subject["strategy"], ""),
        "status": "ok",
        "ci": "",
        "workflows": "",
        "error": "",
    }
    full_name = subject["repository_full_name"]
    if not full_name:
        base["status"] = "error"
        base["error"] = "missing repository_full_name"
        return base
    try:
        listing = client._get(f"/repos/{full_name}/contents/.github/workflows")
    except RuntimeError as exc:
        base["status"] = "error"
        base["error"] = str(exc)[:300]
        return base
    if not isinstance(listing, list):
        info = client.get_repo(full_name)
        if not isinstance(info, dict):
            base["status"] = "error"
            base["error"] = "repository not found"
            return base
        base["ci"] = "false"
        return base

    pattern = PATTERNS[subject["strategy"]]
    matched_files = []
    errors = []
    for item in listing:
        name = item.get("name") or ""
        if not name.lower().endswith((".yml", ".yaml")):
            continue
        path = item.get("path") or f".github/workflows/{name}"
        try:
            text = _workflow_text(client, full_name, path)
        except RuntimeError as exc:
            errors.append(f"{path}: {exc}")
            continue
        if text is None:
            errors.append(f"{path}: empty")
            continue
        if _workflow_matches(text, pattern):
            matched_files.append(path)
    if errors and not matched_files and len(errors) == sum(
        1 for item in listing if (item.get("name") or "").lower().endswith((".yml", ".yaml"))
    ):
        base["status"] = "error"
        base["error"] = "; ".join(errors)[:300]
        return base
    base["ci"] = "true" if matched_files else "false"
    base["workflows"] = ";".join(matched_files)
    if errors:
        base["error"] = "; ".join(errors)[:300]
    return base


def _workflow_text(client: GithubClient, full_name: str, path: str) -> str | None:
    payload = client._get(f"/repos/{full_name}/contents/{quote(path, safe='/')}")
    if not isinstance(payload, dict):
        return None
    content = payload.get("content")
    if payload.get("encoding") == "base64" and content:
        return base64.b64decode(content).decode("utf-8", errors="replace")
    return None


def _workflow_matches(text: str, pattern: re.Pattern) -> bool:
    commands = []
    try:
        document = yaml.safe_load(text) or {}
    except yaml.YAMLError:
        document = None
    if document is not None:
        _collect_runs(document, commands)
    else:
        commands.append(text)
    return any(pattern.search(command) for command in commands)


def _collect_runs(value, commands: list[str]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "run" and isinstance(child, str):
                commands.append(child)
            else:
                _collect_runs(child, commands)
    elif isinstance(value, list):
        for item in value:
            _collect_runs(item, commands)


def run_adoption(subjects: list[dict]) -> None:
    path = CHECKPOINT / "adoption.jsonl"
    done = _load_checkpoint(path)
    pending = [
        row for row in subjects
        if done.get(_subject_key(row), {}).get("status") not in ("ok", "no_needle", "clone_error", "no_path")
    ]
    print(f"adoption: {len(subjects) - len(pending)} done, {len(pending)} to clone", flush=True)
    if not pending:
        _write_adoption_csv(subjects, done)
        return

    from concurrent.futures import ThreadPoolExecutor, as_completed

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(_adoption_one, subject) for subject in pending]
        for index, future in enumerate(as_completed(futures), start=1):
            result = future.result()
            _append_checkpoint(path, result)
            done[result["key"]] = result
            if index % 25 == 0 or index == len(pending):
                print(
                    f"adoption: {index}/{len(pending)} {result['repository_full_name']} "
                    f"{result['status']} {result.get('adoption_date', '')}",
                    flush=True,
                )
    _write_adoption_csv(subjects, done)


def _adoption_one(subject: dict) -> dict:
    base = {
        "key": _subject_key(subject),
        "repository_id": subject["repository_id"],
        "repository_full_name": subject["repository_full_name"],
        "strategy": subject["strategy"],
        "reason": subject["reason"],
        "status": "ok",
        "adoption_date": "",
        "error": "",
    }
    if not subject["paths"]:
        base["status"] = "no_path"
        return base
    if not subject["repository_full_name"]:
        base["status"] = "clone_error"
        base["error"] = "missing repository_full_name"
        return base

    dest = Path(tempfile.mkdtemp(prefix="rq1-"))
    try:
        url = f"https://github.com/{subject['repository_full_name']}.git"
        clone_error = _run_git(
            ["git", "clone", "--filter=blob:none", "--quiet", url, str(dest)],
            timeout=300,
        )
        if clone_error:
            base["status"] = "clone_error"
            base["error"] = clone_error
            return base
        dates = []
        for spec in _log_specs(subject):
            proc = _run_git_capture(["git", "-C", str(dest), *spec], timeout=120)
            if proc is None:
                continue
            lines = [line.strip() for line in proc.splitlines() if line.strip()]
            if lines:
                dates.append(lines[-1])
        if not dates:
            base["status"] = "no_needle"
            return base
        base["adoption_date"] = min(dates)
        return base
    except Exception as exc:  # noqa: BLE001 - one repo must not stop the batch
        base["status"] = "clone_error"
        base["error"] = str(exc)[:300]
        return base
    finally:
        shutil.rmtree(dest, ignore_errors=True)


def _log_specs(subject: dict) -> list[list[str]]:
    specs = []
    for path in subject["paths"]:
        if subject["strategy"] == "MavenCrawler":
            specs.append(["log", "-S", "com.tngtech.archunit", "--format=%aI", "--", path])
        elif subject["strategy"] == "PypiCrawler" and path.endswith("pyproject.toml"):
            specs.append(["log", "-S", "importlinter", "--format=%aI", "--", path])
        else:
            specs.append(["log", "--diff-filter=A", "--format=%aI", "--", path])
    return specs


def _run_git(args: list[str], timeout: int) -> str:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        start_new_session=True,
    )
    try:
        _, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        return f"timeout {timeout}s"
    if proc.returncode != 0:
        return (err or "git failed")[:300]
    return ""


def _run_git_capture(args: list[str], timeout: int) -> str | None:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        start_new_session=True,
    )
    try:
        out, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        return None
    if proc.returncode != 0:
        return None
    return out


def write_funnel() -> None:
    with (ROOT / "data" / "funnel_pilot.csv").open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    counts = Counter((row["strategy"], row["reason"]) for row in rows)
    strategies = ["MavenCrawler", "NpmCrawler", "PypiCrawler"]
    reasons = ["kept", "extended", "short_lived", "template", "missing", "fork", "archived", "contributors"]
    lines = ["# Funnel (locked corpus)", ""]
    for strategy in strategies:
        lines.append(f"## {strategy} / {TOOL_OF[strategy]}")
        total = sum(counts[(strategy, reason)] for reason in {key[1] for key in counts if key[0] == strategy})
        lines.append(f"- repos: {total}")
        for reason in reasons:
            value = counts[(strategy, reason)]
            if value:
                lines.append(f"- {reason}: {value}")
        lines.append("")
    lines.append("Analysis sets: `no_extend` = kept. `with_extend` = kept + extended.")
    (OUT / "funnel.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_cohort(name: str, subjects: list[dict]) -> None:
    folder = OUT / name
    folder.mkdir(parents=True, exist_ok=True)
    adoption = _load_checkpoint(CHECKPOINT / "adoption.jsonl")
    ci = _load_checkpoint(CHECKPOINT / "ci.jsonl")
    repos = []
    for subject in subjects:
        key = _subject_key(subject)
        adopted = adoption.get(key, {})
        scanned = ci.get(key, {})
        date = adopted.get("adoption_date") or ""
        repos.append({
            "repository_id": subject["repository_id"],
            "repository_full_name": subject["repository_full_name"],
            "strategy": subject["strategy"],
            "tool": TOOL_OF.get(subject["strategy"], ""),
            "reason": subject["reason"],
            "adoption_date": date,
            "adoption_year": date[:4] if len(date) >= 4 else "",
            "adoption_status": adopted.get("status", ""),
            "ci": scanned.get("ci", ""),
            "ci_workflows": scanned.get("workflows", ""),
            "ci_error": scanned.get("error", ""),
        })
    fields = list(repos[0].keys()) if repos else [
        "repository_id", "repository_full_name", "strategy", "tool", "reason",
        "adoption_date", "adoption_year", "adoption_status", "ci", "ci_workflows", "ci_error",
    ]
    _write_csv(folder / "repos.csv", repos, fields)
    _write_rates(folder, repos)


def _write_rates(folder: Path, repos: list[dict]) -> None:
    hist_rows = []
    ci_rows = []
    lines = [f"# RQ1 {folder.name}", "", f"Rows (repository x tool): {len(repos)}"]
    unique_ids = {row["repository_id"] for row in repos}
    lines.append(f"Unique repositories: {len(unique_ids)}")
    lines.append("")

    years = ["pre-2017", *[str(year) for year in range(2017, 2027)], "missing"]
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
    lines.append("## Adoption year")
    for strategy in TOOL_OF:
        total = sum(by_tool_year[strategy].values())
        dated = total - by_tool_year[strategy]["missing"]
        lines.append(f"### {TOOL_OF[strategy]} n={total} dated={dated}")
        for label in years:
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
            if count:
                lines.append(f"- {label}: {count} ({share:.1%} of tool)")
        lines.append("")
    _write_csv(
        folder / "adoption_hist.csv",
        hist_rows,
        ["strategy", "tool", "year", "count", "share_of_tool", "share_of_dated"],
    )
    _write_histogram(folder / "adoption_year.svg", by_tool_year, years)

    lines.append("## CI share")
    h11_flags: list[bool] = []
    h11_by_strategy: dict[str, list[bool]] = {strategy: [] for strategy in H11_STRATEGIES}
    for strategy, tool in TOOL_OF.items():
        rows = [row for row in repos if row["strategy"] == strategy]
        known = [row for row in rows if row["ci"] in ("true", "false")]
        flags = [row["ci"] == "true" for row in known]
        unknown = len(rows) - len(known)
        estimate = _bootstrap(flags)
        ci_rows.append(_ci_row(strategy, tool, len(rows), len(known), unknown, flags, estimate))
        lines.append(f"### {tool}")
        lines.append(f"- scanned with a result: {len(known)} / {len(rows)} (unknown {unknown})")
        if estimate:
            point, low, high = estimate
            lines.append(f"- share: {point:.3f} (95% bootstrap CI {low:.3f}–{high:.3f})")
        if strategy in H11_STRATEGIES:
            h11_flags.extend(flags)
            h11_by_strategy[strategy] = flags
        lines.append("")

    lines.append("## H1.1")
    lines.append("Denominator is import-linter and dependency-cruiser rows with a CI result. ArchUnit is descriptive only.")
    for strategy in H11_STRATEGIES:
        estimate = _bootstrap(h11_by_strategy[strategy])
        lines.append(f"- {TOOL_OF[strategy]}: {_format_h11(estimate)}")
    lines.append(f"- pooled: {_format_h11(_bootstrap(h11_flags))}")
    deduped = _deduped_h11(repos)
    lines.append(f"- pooled unique repositories: {_format_h11(_bootstrap(deduped))}")
    (folder / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    _write_csv(
        folder / "ci_rates.csv",
        ci_rows,
        ["strategy", "tool", "rows", "known", "unknown", "ci_true", "share", "ci_low", "ci_high", "h11"],
    )


def _ci_row(strategy, tool, rows, known, unknown, flags, estimate) -> dict:
    point = low = high = ""
    if estimate:
        point, low, high = (f"{estimate[0]:.4f}", f"{estimate[1]:.4f}", f"{estimate[2]:.4f}")
    return {
        "strategy": strategy,
        "tool": tool,
        "rows": rows,
        "known": known,
        "unknown": unknown,
        "ci_true": sum(flags),
        "share": point,
        "ci_low": low,
        "ci_high": high,
        "h11": "yes" if strategy in H11_STRATEGIES else "no",
    }


def _deduped_h11(repos: list[dict]) -> list[bool]:
    by_repo: dict[str, list[bool]] = defaultdict(list)
    for row in repos:
        if row["strategy"] not in H11_STRATEGIES or row["ci"] not in ("true", "false"):
            continue
        by_repo[row["repository_id"]].append(row["ci"] == "true")
    return [any(flags) for flags in by_repo.values()]


def _format_h11(estimate) -> str:
    if not estimate:
        return "no observations"
    point, low, high = estimate
    below = high < 0.50
    return (
        f"{point:.3f} (95% CI {low:.3f}–{high:.3f}); "
        f"interval lies entirely below 0.50: {'yes' if below else 'no'}"
    )


def _bootstrap(flags: list[bool]) -> tuple[float, float, float] | None:
    if not flags:
        return None
    point = sum(flags) / len(flags)
    rng = random.Random(SEED)
    size = len(flags)
    stats = []
    for _ in range(BOOTSTRAP_DRAWS):
        draw = sum(flags[rng.randrange(size)] for _ in range(size))
        stats.append(draw / size)
    stats.sort()
    low = stats[int(0.025 * (BOOTSTRAP_DRAWS - 1))]
    high = stats[int(0.975 * (BOOTSTRAP_DRAWS - 1))]
    return point, low, high


def _write_histogram(path: Path, by_tool_year: dict[str, Counter], years: list[str]) -> None:
    tools = list(TOOL_OF)
    width, height = 960, 420
    margin_left, margin_bottom = 48, 70
    plot_width = width - margin_left - 20
    plot_height = height - margin_bottom - 20
    max_count = max((by_tool_year[tool][year] for tool in tools for year in years), default=1) or 1
    group = plot_width / len(years)
    bar = group / (len(tools) + 1)
    colors = {"MavenCrawler": "#4c78a8", "NpmCrawler": "#f58518", "PypiCrawler": "#54a24b"}
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
        '<rect width="100%" height="100%" fill="white"/>',
    ]
    for index, year in enumerate(years):
        for tool_index, tool in enumerate(tools):
            count = by_tool_year[tool][year]
            bar_height = 0 if max_count == 0 else plot_height * count / max_count
            x = margin_left + index * group + tool_index * bar
            y = 20 + plot_height - bar_height
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar - 2:.1f}" height="{bar_height:.1f}" fill="{colors[tool]}"/>'
            )
        parts.append(
            f'<text x="{margin_left + index * group + group / 2:.1f}" y="{height - 36}" '
            f'font-size="11" text-anchor="end" transform="rotate(-45 {margin_left + index * group + group / 2:.1f},{height - 36})">{year}</text>'
        )
    legend_x = margin_left
    for tool in tools:
        parts.append(f'<rect x="{legend_x}" y="{height - 18}" width="12" height="12" fill="{colors[tool]}"/>')
        parts.append(f'<text x="{legend_x + 16}" y="{height - 8}" font-size="12">{TOOL_OF[tool]}</text>')
        legend_x += 140
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def _write_adoption_csv(subjects: list[dict], done: dict[str, dict]) -> None:
    rows = []
    for subject in subjects:
        row = done.get(_subject_key(subject), {})
        date = row.get("adoption_date") or ""
        rows.append({
            "repository_id": subject["repository_id"],
            "repository_full_name": subject["repository_full_name"],
            "strategy": subject["strategy"],
            "reason": subject["reason"],
            "adoption_date": date,
            "adoption_year": date[:4] if len(date) >= 4 else "",
            "status": row.get("status", ""),
            "error": row.get("error", ""),
        })
    _write_csv(
        OUT / "adoption.csv",
        rows,
        ["repository_id", "repository_full_name", "strategy", "reason", "adoption_date", "adoption_year", "status", "error"],
    )


def _write_joined_csv(path: Path, subjects: list[dict], done: dict[str, dict], fields: list[str]) -> None:
    rows = []
    for subject in subjects:
        row = done.get(_subject_key(subject), {})
        rows.append({field: row.get(field, subject.get(field, "")) for field in fields})
    _write_csv(path, rows, fields)


def _subject_key(subject: dict) -> str:
    return f"{subject['repository_id']}|{subject['strategy']}"


def _load_checkpoint(path: Path) -> dict[str, dict]:
    latest = {}
    if not path.exists():
        return latest
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = row.get("key") or row.get("tool") or ""
            if key:
                latest[key] = row
    return latest


def _append_checkpoint(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _checkpoint_lock:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())


def _write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
