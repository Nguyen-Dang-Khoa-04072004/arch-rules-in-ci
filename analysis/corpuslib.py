"""Shared corpus contract for RQ1–RQ4.

The comparison sample is data/corpus.csv. It is written only after clones
finish. Exclusions live in data/corpus_excluded.csv and are never added to N.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RQ1 = DATA / "RQ1"
RQ2 = DATA / "RQ2"
RQ3 = DATA / "RQ3"
RQ4 = DATA / "RQ4"
FILES_JSONL = RQ2 / "files.jsonl"
FILES_HASH = "716d1de4055c364fe94952be509f514118679ef24328f42c9537f028572d4352"
CHECKPOINT_RQ2 = RQ2 / "checkpoints" / "files.jsonl"
FUNNEL = DATA / "funnel_pilot.csv"
ADOPTION = RQ1 / "adoption.csv"
CI = RQ1 / "ci.csv"
CORPUS = DATA / "corpus.csv"
EXCLUDED = DATA / "corpus_excluded.csv"
ATTRITION = DATA / "attrition.md"
TMP = Path("/mnt/data/tmp")

CLONES = RQ3 / "clones"
HISTORY_CHECKPOINT = RQ3 / "checkpoints" / "history.jsonl"
META_DIR = RQ3 / "meta"
RAW_DIR = RQ3 / "parts" / "raw"
CLASS_DIR = RQ3 / "parts" / "classified"
EDITS_RAW = RQ3 / "edits_raw.jsonl"
EDITS = RQ3 / "edits.jsonl"
GOLD = RQ3 / "gold_edits_sample.csv"
STATS_JSON = RQ3 / "stats.json"
CONCAT_MANIFEST = RQ3 / "concat_manifest.jsonl"

SEED = 20261018
BOOTSTRAP_DRAWS = 1000
DEV_LIMIT = 1000
STRUCTURAL = ("dependency", "layering")
H31_MONTHS = 24.0
H32_BASELINE = 0.738
TREATED_MIN = 150
TOOL_OF = {
    "MavenCrawler": "ArchUnit",
    "PypiCrawler": "import-linter",
    "NpmCrawler": "dependency-cruiser",
}
TOOLS = ("ArchUnit", "import-linter", "dependency-cruiser")
COHORTS = ("no_extend", "with_extend")
KEPT_UNAVAILABLE = (
    "sgajbi/lotus-core",
    "SJTU-Geek/Aixinwu-dashboard",
    "zhaochy1990/running",
    "lj860117/moneybag",
    "ChauDoan21165/MercyB",
    "leszavr/voxlibris",
)
EXCLUSION_FIELDS = [
    "repository_id",
    "repository_full_name",
    "tool",
    "strategy",
    "reason",
    "cohort",
    "exclusion_reason",
    "error",
    "rq1_adoption_status",
    "rq1_ci_status",
    "adoption_year",
    "n_files",
    "n_candidates",
]
CORPUS_FIELDS = [
    "repository_id",
    "repository_full_name",
    "tool",
    "strategy",
    "reason",
    "sample_index",
    "n_files",
    "n_candidates",
    "clone_dir",
    "head_sha",
]
COUNT_FIELDS = ["cohort", "tool", "n"]


def ensure_dirs() -> None:
    TMP.mkdir(parents=True, exist_ok=True)
    os.environ["TMPDIR"] = str(TMP)
    os.environ["GIT_PAGER"] = "cat"
    os.environ["PAGER"] = "cat"
    os.environ["GIT_TERMINAL_PROMPT"] = "0"
    os.environ["GIT_LFS_SKIP_SMUDGE"] = "1"
    for path in (
        CLONES,
        HISTORY_CHECKPOINT.parent,
        META_DIR,
        RAW_DIR,
        CLASS_DIR,
        RQ3 / "no_extend",
        RQ3 / "with_extend",
        RQ4 / "eligibility",
        RQ4 / "replay",
        RQ1 / "no_extend",
        RQ1 / "with_extend",
        RQ2 / "no_extend",
        RQ2 / "with_extend",
    ):
        path.mkdir(parents=True, exist_ok=True)


def assert_files_hash() -> None:
    digest = hashlib.sha256(FILES_JSONL.read_bytes()).hexdigest()
    if digest != FILES_HASH:
        raise SystemExit(f"refusing to continue: files.jsonl hash is {digest}")


def subject_key(repository_id: str, strategy: str) -> str:
    return f"{repository_id}|{strategy}"


def file_stem(repository_id: str, strategy: str) -> str:
    return f"{repository_id}__{strategy}"


def cohort_label(reason: str) -> str:
    if reason == "kept":
        return "no_extend|with_extend"
    return "with_extend"


def in_cohort(reason: str, cohort: str) -> bool:
    if cohort == "with_extend":
        return reason in ("kept", "extended")
    return reason == "kept"


def git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["TMPDIR"] = str(TMP)
    env["GIT_PAGER"] = "cat"
    env["PAGER"] = "cat"
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_LFS_SKIP_SMUDGE"] = "1"
    return env


def parse_dt(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def add_months(moment: datetime, months: int) -> datetime:
    year = moment.year + (moment.month - 1 + months) // 12
    month = (moment.month - 1 + months) % 12 + 1
    day = min(moment.day, _month_days(year, month))
    return moment.replace(year=year, month=month, day=day)


def _month_days(year: int, month: int) -> int:
    if month == 2:
        leap = year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
        return 29 if leap else 28
    return 30 if month in (4, 6, 9, 11) else 31


def months_between(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / 86400 / (365.25 / 12)


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def latest_by_key(path: Path, key_field: str = "key") -> dict[str, dict]:
    latest: dict[str, dict] = {}
    for row in load_jsonl(path):
        key = str(row.get(key_field) or "")
        if key:
            latest[key] = row
    return latest


def load_rq2_subjects() -> list[dict]:
    subjects = []
    for row in load_jsonl(CHECKPOINT_RQ2):
        subjects.append({
            "key": str(row.get("key") or subject_key(str(row["repository_id"]), row["strategy"])),
            "repository_id": str(row["repository_id"]),
            "repository_full_name": row.get("repository_full_name") or "",
            "strategy": row["strategy"],
            "tool": TOOL_OF.get(row["strategy"], ""),
            "reason": row.get("reason") or "",
            "sample_index": int(row.get("sample_index") or 0),
            "status": row.get("status") or "",
            "n_files": int(row.get("n_files") or 0),
            "n_candidates": int(row.get("n_candidates") or 0),
            "error": (row.get("error") or "").replace("\n", " ").strip(),
            "commit_sha": row.get("commit_sha") or "",
        })
    return subjects


def load_paths() -> dict[str, list[str]]:
    """Rule-file paths from files.jsonl. The file text is not retained."""
    paths: dict[str, list[str]] = defaultdict(list)
    with FILES_JSONL.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            key = subject_key(str(row["repository_id"]), row["strategy"])
            path = row.get("file") or ""
            if path and path not in paths[key]:
                paths[key].append(path)
    return paths


def _csv_index(path: Path) -> dict[str, dict]:
    index = {}
    if not path.exists():
        return index
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            index[subject_key(str(row["repository_id"]), row["strategy"])] = row
    return index


def load_adoption() -> dict[str, dict]:
    return _csv_index(ADOPTION)


def load_ci() -> dict[str, dict]:
    return _csv_index(CI)


def exclusion_row(subject: dict, exclusion_reason: str, error: str, adoption: dict, ci: dict) -> dict:
    key = subject["key"]
    adopted = adoption.get(key, {})
    scanned = ci.get(key, {})
    return {
        "repository_id": subject["repository_id"],
        "repository_full_name": subject["repository_full_name"],
        "tool": subject["tool"],
        "strategy": subject["strategy"],
        "reason": subject["reason"],
        "cohort": cohort_label(subject["reason"]),
        "exclusion_reason": exclusion_reason,
        "error": (error or "").replace("\n", " ").strip()[:500],
        "rq1_adoption_status": adopted.get("status") or "",
        "rq1_ci_status": scanned.get("ci") or "",
        "adoption_year": adopted.get("adoption_year") or "",
        "n_files": subject.get("n_files") or 0,
        "n_candidates": subject.get("n_candidates") or 0,
    }


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def prepare_exclusions() -> int:
    """Write unavailable and no_rule_file rows. Preserve clone_error rows already appended."""
    ensure_dirs()
    assert_files_hash()
    subjects = load_rq2_subjects()
    adoption = load_adoption()
    ci = load_ci()
    existing_clone_errors = [
        row for row in read_csv(EXCLUDED) if row.get("exclusion_reason") == "clone_error"
    ]
    seen = {subject_key(row["repository_id"], row["strategy"]) for row in existing_clone_errors}
    rows = []
    for subject in subjects:
        if subject["status"] not in ("unavailable", "no_rule_file"):
            continue
        if subject["key"] in seen:
            continue
        error = subject["error"]
        if subject["status"] == "no_rule_file" and not error:
            error = "no rule file"
        rows.append(exclusion_row(subject, subject["status"], error, adoption, ci))
    rows.extend(existing_clone_errors)
    rows.sort(key=lambda row: (row["exclusion_reason"], row["tool"], row["repository_full_name"]))
    write_csv(EXCLUDED, rows, EXCLUSION_FIELDS)
    write_attrition(rows)
    return len(rows)


def append_exclusion(row: dict) -> None:
    EXCLUDED.parent.mkdir(parents=True, exist_ok=True)
    new_file = not EXCLUDED.exists() or EXCLUDED.stat().st_size == 0
    with EXCLUDED.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXCLUSION_FIELDS, extrasaction="ignore")
        if new_file:
            writer.writeheader()
        writer.writerow(row)
        handle.flush()
        os.fsync(handle.fileno())


def write_attrition(rows: list[dict] | None = None) -> None:
    if rows is None:
        rows = read_csv(EXCLUDED)
    reasons = ("unavailable", "no_rule_file", "clone_error")
    counts: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for row in rows:
        cohorts = ["with_extend"]
        if row.get("reason") == "kept":
            cohorts.append("no_extend")
        for cohort in cohorts:
            counts[(cohort, row.get("tool") or "")][row.get("exclusion_reason") or ""] += 1
    lines = [
        "# Attrition",
        "",
        "Repositories listed here are out of the RQ1–RQ4 comparison sample.",
        "They are not added to comparison N.",
        "",
        f"Ledger: `{EXCLUDED.relative_to(ROOT)}` ({len(rows)} rows).",
        "",
        "## Counts by cohort and tool",
        "",
        "| cohort | tool | unavailable | no_rule_file | clone_error | total |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for cohort in COHORTS:
        for tool in TOOLS:
            bucket = counts[(cohort, tool)]
            total = sum(bucket[reason] for reason in reasons)
            lines.append(
                f"| {cohort} | {tool} | {bucket['unavailable']} | {bucket['no_rule_file']} | "
                f"{bucket['clone_error']} | {total} |"
            )
        overall = Counter()
        for tool in TOOLS:
            overall.update(counts[(cohort, tool)])
        lines.append(
            f"| {cohort} | all | {overall['unavailable']} | {overall['no_rule_file']} | "
            f"{overall['clone_error']} | {sum(overall[reason] for reason in reasons)} |"
        )
    kept_rows = [
        row for row in rows
        if row.get("exclusion_reason") == "unavailable" and row.get("reason") == "kept"
    ]
    lines.extend([
        "",
        "## Kept repositories among the unavailable set",
        "",
        "These six kept repositories are part of the 15 unavailable repositories.",
        "They count in both `no_extend` and `with_extend` attrition, and in neither comparison N.",
        "",
    ])
    found = {row["repository_full_name"] for row in kept_rows}
    for name in KEPT_UNAVAILABLE:
        mark = "present" if name in found else "MISSING"
        lines.append(f"- {name}: {mark}")
    extra = sorted(found - set(KEPT_UNAVAILABLE))
    for name in extra:
        lines.append(f"- {name}: present, not in the expected six")
    lines.append("")
    ATTRITION.write_text("\n".join(lines) + "\n", encoding="utf-8")


def history_status() -> dict[str, dict]:
    return latest_by_key(HISTORY_CHECKPOINT)


def load_corpus() -> list[dict]:
    return read_csv(CORPUS)


def counts_from_repos(repos: list[dict], archunit_only: bool = False) -> list[dict]:
    rows = []
    for cohort in COHORTS:
        cohort_rows = [row for row in repos if in_cohort(row.get("reason") or "", cohort)]
        tools = ("ArchUnit",) if archunit_only else TOOLS
        for tool in tools:
            rows.append({
                "cohort": cohort,
                "tool": tool,
                "n": sum(1 for row in cohort_rows if row.get("tool") == tool),
            })
        if not archunit_only:
            rows.append({"cohort": cohort, "tool": "__all__", "n": len(cohort_rows)})
    return rows


def write_counts(path: Path, repos: list[dict], archunit_only: bool = False) -> None:
    write_csv(path, counts_from_repos(repos, archunit_only=archunit_only), COUNT_FIELDS)


def read_counts(path: Path) -> dict[tuple[str, str], int]:
    found = {}
    for row in read_csv(path):
        found[(row["cohort"], row["tool"])] = int(row["n"])
    return found


def compare_counts() -> tuple[bool, list[str]]:
    paths = {
        "RQ1": RQ1 / "counts.csv",
        "RQ2": RQ2 / "counts.csv",
        "RQ3": RQ3 / "counts.csv",
        "RQ4": RQ4 / "counts.csv",
    }
    missing = [name for name, path in paths.items() if not path.exists()]
    if missing:
        return False, [f"missing count file: {', '.join(missing)}"]
    loaded = {name: read_counts(path) for name, path in paths.items()}
    problems = []
    for cohort in COHORTS:
        for tool in TOOLS:
            values = {name: loaded[name].get((cohort, tool)) for name in ("RQ1", "RQ2", "RQ3")}
            if tool != "ArchUnit":
                if len(set(values.values())) != 1 or None in values.values():
                    problems.append(f"{cohort} {tool}: {values}")
            else:
                quad = dict(values)
                quad["RQ4"] = loaded["RQ4"].get((cohort, tool))
                if len(set(quad.values())) != 1 or None in quad.values():
                    problems.append(f"{cohort} {tool}: {quad}")
        overall = {name: loaded[name].get((cohort, "__all__")) for name in ("RQ1", "RQ2", "RQ3")}
        if len(set(overall.values())) != 1 or None in overall.values():
            problems.append(f"{cohort} __all__: {overall}")
    return not problems, problems


def bootstrap(flags: list[bool]) -> tuple[float, float, float] | None:
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
    return point, stats[int(0.025 * (BOOTSTRAP_DRAWS - 1))], stats[int(0.975 * (BOOTSTRAP_DRAWS - 1))]


def clone_path(repository_id: str, strategy: str) -> Path:
    return CLONES / file_stem(repository_id, strategy)


def rel_clone(repository_id: str, strategy: str) -> str:
    return str(clone_path(repository_id, strategy).relative_to(ROOT))
