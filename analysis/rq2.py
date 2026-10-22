"""RQ2 construct extraction and held-out rates.

The first 1000 kept+extended funnel rows are the development set.
H2.1 uses only later rows, after data/RQ2/codebook_map.json is frozen.
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from analysis.git_tree_sample import (  # noqa: E402
    contains_archunit,
    content_transport,
    importlinter_mode,
    is_depcruise,
    manifest_entries,
    pyproject_has_importlinter,
    select_archunit_sources,
    test_roots_from_manifest,
)
from github.client import GithubClient, RateLimiter  # noqa: E402
from parsers.archunit import extract as extract_archunit  # noqa: E402
from parsers.depcruise import extract as extract_depcruise  # noqa: E402
from parsers.importlinter import extract as extract_importlinter  # noqa: E402

OUT = ROOT / "data" / "RQ2"
CHECKPOINT = OUT / "checkpoints" / "subjects.jsonl"
CONSTRUCTS = OUT / "constructs.jsonl"
FILES = OUT / "files.jsonl"
FILES_CHECKPOINT = OUT / "checkpoints" / "files.jsonl"
FILES_MANIFEST = OUT / "files_manifest.md"
CONSTRUCTS_FULL = OUT / "constructs_full.jsonl"
# A finished repository stays finished. error and truncated are retried.
# unavailable is a closed 404 and is not fetched again.
FILES_SKIP_STATUS = {"complete", "no_rule_file", "unavailable"}
NOT_CATEGORIES = {"FreezingArchRule", "@ArchIgnore"}
DEV_LIMIT = 1000
SEED = 20261018
BOOTSTRAP_DRAWS = 1000
SOURCE_SUFFIXES = (".java", ".kt", ".kts")
CANDIDATE_CAP = 80
_GRADLE_KTS_NAMES = {"build.gradle.kts", "settings.gradle.kts"}
TOOL_OF = {
    "MavenCrawler": "ArchUnit",
    "PypiCrawler": "import-linter",
    "NpmCrawler": "dependency-cruiser",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--phase",
        choices=("fetch", "files", "codebook", "parse", "stats", "report"),
        default="fetch",
    )
    parser.add_argument("--limit", type=int, default=0, help="If set, only the first N union rows")
    parser.add_argument("--offset", type=int, default=0)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.phase == "codebook":
        freeze_codebook()
        return
    if args.phase == "parse":
        parse_rules()
        return
    if args.phase == "stats":
        stats()
        return
    subjects = load_subjects()
    if args.phase == "files":
        collect_files(subjects)
        return
    if args.phase == "fetch":
        window = subjects[args.offset: args.offset + args.limit if args.limit else None]
        fetch(window)
        return
    report(subjects)


def load_subjects() -> list[dict]:
    paths: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    with (ROOT / "data" / "repos_raw.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            key = (row["repository_id"], row["strategy"])
            path = row.get("path") or ""
            if path and (path, row.get("sha") or "") not in paths[key]:
                paths[key].append((path, row.get("sha") or ""))
    subjects = []
    with (ROOT / "data" / "funnel_pilot.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("reason") not in ("kept", "extended"):
                continue
            key = (row["repository_id"], row["strategy"])
            subjects.append({
                "sample_index": len(subjects),
                "repository_id": row["repository_id"],
                "repository_full_name": row["repository_full_name"],
                "strategy": row["strategy"],
                "reason": row["reason"],
                "paths": paths.get(key, []),
            })
    return subjects


def fetch(subjects: list[dict]) -> None:
    done = _load_jsonl(CHECKPOINT)
    client = GithubClient(min_interval=6.5, repo_limiter=RateLimiter(0.8))
    # truncated and no_source_rule came from search-only discovery; retry them.
    pending = [row for row in subjects if done.get(_key(row), {}).get("status") not in {"ok", "no_path"}]
    print(f"fetch: {len(subjects) - len(pending)} done, {len(pending)} pending", flush=True)
    for index, subject in enumerate(pending, start=1):
        status, constructs, error = _fetch_one(client, subject)
        if constructs:
            _append_jsonl(CONSTRUCTS, constructs)
        record = {
            "key": _key(subject),
            "sample_index": subject["sample_index"],
            "repository_full_name": subject["repository_full_name"],
            "strategy": subject["strategy"],
            "status": status,
            "n_constructs": len(constructs),
            "error": error,
        }
        _append_jsonl(CHECKPOINT, [record])
        if index % 10 == 0 or index == len(pending):
            print(
                f"fetch {index}/{len(pending)} {subject['repository_full_name']} "
                f"{status} constructs={len(constructs)}",
                flush=True,
            )
    _write_construct_counts()
    print("fetch phase finished", flush=True)


def _fetch_one(client: GithubClient, subject: dict) -> tuple[str, list[dict], str]:
    full_name = subject["repository_full_name"]
    if not full_name:
        return "no_path", [], "missing repository_full_name"
    try:
        if subject["strategy"] == "MavenCrawler":
            files, status = _archunit_files(client, full_name)
            if status != "ok":
                return status, [], ""
        else:
            files = [(path, sha, None) for path, sha in subject["paths"]]
            if not files:
                return "no_path", [], ""
            status = "ok"
        constructs = []
        errors = []
        for path, sha, known_text in files:
            text = known_text
            if text is None:
                text, err = _download(client, full_name, path, sha)
                if text is None:
                    errors.append(f"{path}: {err}")
                    continue
            constructs.extend(_parse_file(subject, path, text))
        if not constructs and errors:
            return "error", [], "; ".join(errors)[:300]
        if subject["strategy"] == "MavenCrawler" and not constructs and not errors:
            return "no_source_rule", [], ""
        if not constructs:
            return "ok", [_row(subject, subject["paths"][0][0] if subject["paths"] else "", {
                "construct": "unparsed",
                "exemption": False,
                "raw_text": "",
            })], ""
        return "ok", constructs, "; ".join(errors)[:300]
    except (RuntimeError, ValueError) as exc:
        return "error", [], str(exc)[:300]


def _archunit_files(client: GithubClient, full_name: str) -> tuple[list[tuple[str, str, str | None]], str]:
    repo = client.get_repo(full_name)
    if not isinstance(repo, dict):
        return [], "no_path"
    branch = repo.get("default_branch") or "HEAD"
    ref = client._get(f"/repos/{full_name}/branches/{quote(branch, safe='')}")
    if not isinstance(ref, dict):
        return [], "no_path"
    commit = ref.get("commit")
    tree_sha = commit.get("sha") if isinstance(commit, dict) else ""
    tree = (
        client._get(
            f"/repos/{full_name}/git/trees/{tree_sha}",
            params={"recursive": "1"},
        )
        if tree_sha
        else None
    )
    if isinstance(tree, dict) and not tree.get("truncated"):
        candidates = _cap_archunit_candidates(full_name, _archunit_tree_candidates(tree))
        kept: list[tuple[str, str, str | None]] = []
        for path, sha in candidates:
            text, _err = _download(client, full_name, path, sha)
            if text and _contains_archunit(text):
                kept.append((path, sha, text))
        return kept, "ok"
    found = _search_archunit_paths(client, full_name)
    if found:
        return [(path, sha, None) for path, sha in found.items()], "ok"
    if isinstance(tree, dict) and tree.get("truncated"):
        return [], "truncated"
    return [], "error"


def _archunit_tree_candidates(tree: dict) -> list[tuple[str, str]]:
    candidates = []
    for entry in tree.get("tree") or []:
        if entry.get("type") != "blob":
            continue
        path = entry.get("path") or ""
        if _archunit_candidate(path):
            candidates.append((path, entry.get("sha") or ""))
    return candidates


def _archunit_candidate(path: str) -> bool:
    lower = path.replace("\\", "/").lower()
    if not lower.endswith(SOURCE_SUFFIXES):
        return False
    name = lower.rsplit("/", 1)[-1]
    if lower.endswith(".kts") and "archunit" not in lower:
        parents = lower.split("/")[:-1]
        if name in _GRADLE_KTS_NAMES or "gradle" in parents:
            return False
    return (
        "/test/" in lower
        or lower.startswith("test/")
        or "archunit" in lower
        or "architecture" in lower
        or "arch" in name
    )


def _cap_archunit_candidates(full_name: str, candidates: list[tuple[str, str]]) -> list[tuple[str, str]]:
    if len(candidates) <= CANDIDATE_CAP:
        return candidates
    preferred = [
        item for item in candidates
        if "arch" in item[0].lower().rsplit("/", 1)[-1] or "archunit" in item[0].lower()
    ]
    chosen = preferred if preferred else candidates[:CANDIDATE_CAP]
    if len(chosen) < len(candidates):
        how = "arch-named" if preferred else "first 80 test paths"
        print(
            f"capping {full_name}: {len(candidates)} path candidates -> {len(chosen)} ({how})",
            flush=True,
        )
    return chosen


def _contains_archunit(text: str) -> bool:
    return "com.tngtech.archunit" in text or "org.archunit" in text


def _search_archunit_paths(client: GithubClient, full_name: str) -> dict[str, str]:
    found: dict[str, str] = {}
    # GitHub code search rejects parentheses and OR in this qualifier form.
    queries = (
        f"repo:{full_name} com.tngtech.archunit",
        f"repo:{full_name} org.archunit",
    )
    for query in queries:
        page = 1
        while page <= 10:
            payload = client.search_code(query, page=page, per_page=100)
            items = payload.get("items") or []
            for item in items:
                path = item.get("path") or ""
                if path.lower().endswith(SOURCE_SUFFIXES):
                    found[path] = item.get("sha") or ""
            if len(items) < 100:
                break
            page += 1
    return found


def _download(client: GithubClient, full_name: str, path: str, sha: str) -> tuple[str | None, str]:
    if sha:
        payload = client._get(f"/repos/{full_name}/git/blobs/{sha}")
        text = _decode_content(payload)
        if text is not None:
            return text, ""
    payload = client._get(f"/repos/{full_name}/contents/{quote(path, safe='/')}")
    text = _decode_content(payload)
    if text is None:
        return None, "empty blob"
    return text, ""


def _decode_content(payload) -> str | None:
    """Decode a GitHub blob or contents payload.

    A zero-byte file is valid: the API sends ``encoding=base64`` with an empty
    ``content`` string, or omits ``content`` and sets ``size`` to 0. A missing
    payload or a blob that is too large to include stays a failure.
    """
    if not isinstance(payload, dict) or payload.get("encoding") != "base64":
        return None
    content = payload.get("content")
    if content is None:
        if payload.get("size") == 0:
            return ""
        return None
    return base64.b64decode(content).decode("utf-8", errors="replace")


def _parse_file(subject: dict, path: str, text: str) -> list[dict]:
    if subject["strategy"] == "MavenCrawler":
        extracted = extract_archunit(text)
    elif subject["strategy"] == "PypiCrawler":
        extracted = extract_importlinter(text, path)
    else:
        extracted = extract_depcruise(text, path)
    if not extracted:
        extracted = [{"construct": "unparsed", "exemption": False, "raw_text": text[:500].strip()}]
    return [_row(subject, path, item) for item in extracted]


def _row(subject: dict, path: str, item: dict) -> dict:
    return {
        "sample_index": subject["sample_index"],
        "repository_id": subject["repository_id"],
        "repository_full_name": subject["repository_full_name"],
        "strategy": subject["strategy"],
        "reason": subject["reason"],
        "file": path,
        "construct": item["construct"],
        "exemption": bool(item["exemption"]),
        "raw_text": item["raw_text"],
        "dev": subject["sample_index"] < DEV_LIMIT,
    }


def _write_construct_counts() -> None:
    counts: Counter = Counter()
    for row in _iter_constructs():
        counts[(row["strategy"], row["construct"], bool(row.get("dev")))] += 1
    path = OUT / "construct_counts.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["strategy", "construct", "dev", "count"])
        for (strategy, construct, dev), count in sorted(counts.items()):
            writer.writerow([strategy, construct, str(dev).lower(), count])


def report(subjects: list[dict]) -> None:
    codebook = json.loads((OUT / "codebook_map.json").read_text(encoding="utf-8"))
    mapping = codebook["map"]
    family = set(codebook["structural_family"])
    held_out = [row for row in _iter_constructs() if not row.get("dev")]
    labeled = []
    for row in held_out:
        category, subtype, subject = _label(mapping, row["construct"])
        labeled.append({**row, "category": category, "subtype": subtype, "subject": subject})
    dev_keys = {_key(row) for row in subjects if row["sample_index"] < DEV_LIMIT}
    cohorts = {
        "no_extend": [row for row in labeled if row["reason"] == "kept"],
        "with_extend": labeled,
    }
    for name, rows in cohorts.items():
        _write_cohort(name, rows, family)
    _write_validation_sample(labeled)
    print(f"report held_out_constructs={len(labeled)} dev_repos={len(dev_keys)}", flush=True)


def _write_cohort(name: str, rows: list[dict], family: set[str]) -> None:
    folder = OUT / name
    folder.mkdir(parents=True, exist_ok=True)
    _write_jsonl(folder / "rules.jsonl", rows)
    repos = {}
    for row in rows:
        repos.setdefault((row["repository_id"], row["strategy"]), row)
    with (folder / "repos.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "repository_id", "repository_full_name", "strategy", "reason",
        ])
        writer.writeheader()
        for row in repos.values():
            writer.writerow({key: row[key] for key in writer.fieldnames})
    table = Counter((row["strategy"], row["category"] or "unparsed") for row in rows)
    order = ["dependency", "layering", "cycle", "naming", "visibility", "annotation", "other", "unparsed"]
    categories = sorted(
        {cat for _, cat in table},
        key=lambda cat: (order.index(cat) if cat in order else len(order), cat),
    )
    strategies = list(TOOL_OF)
    chi2, dof, p_value, cramer = _cramer(table, strategies, [cat for cat in categories if cat != "unparsed"])
    lines = [
        f"# RQ2 {name}",
        "",
        "Held-out rows only. The first 1000 kept+extended funnel rows developed the codebook and are excluded.",
        f"Constructs: {len(rows)}",
        f"Repository x tool: {len(repos)}",
        "",
        "## Coverage and categories",
    ]
    h11_lines = ["## H2.1 dependency and layering", ""]
    for strategy in strategies:
        parsed = sum(count for (tool, cat), count in table.items() if tool == strategy and cat != "unparsed")
        unparsed = table[(strategy, "unparsed")]
        seen = parsed + unparsed
        coverage = parsed / seen if seen else 0
        lines.append(f"### {TOOL_OF[strategy]}")
        lines.append(f"- coverage: {parsed}/{seen} ({coverage:.1%})")
        flags = []
        for cat in categories:
            count = table[(strategy, cat)]
            if not count:
                continue
            share = count / parsed if parsed and cat != "unparsed" else 0
            lines.append(f"- {cat}: {count}" + (f" ({share:.1%} of parsed)" if cat != "unparsed" else ""))
            if cat in family:
                flags.extend([True] * count)
            elif cat != "unparsed":
                flags.extend([False] * count)
        estimate = _bootstrap(flags)
        if estimate:
            point, low, high = estimate
            h11_lines.append(
                f"- {TOOL_OF[strategy]}: {point:.3f} (95% CI {low:.3f}–{high:.3f}); "
                f"interval lies entirely above 0.70: {'yes' if low > 0.70 else 'no'}"
            )
        lines.append("")
        subtypes = Counter(
            row.get("subtype") or ""
            for row in rows
            if row["strategy"] == strategy and row.get("category") == "dependency" and row.get("subtype")
        )
        if subtypes:
            lines.append("Dependency subtypes:")
            for subtype, count in sorted(subtypes.items()):
                lines.append(f"- {subtype}: {count}")
            lines.append("")
        subjects = Counter(
            row.get("subject") or ""
            for row in rows
            if row["strategy"] == strategy and row.get("subject")
        )
        if subjects:
            lines.append("Subjects:")
            for subject, count in sorted(subjects.items()):
                lines.append(f"- {subject}: {count}")
            lines.append("")
    lines.append(f"chi-square: {chi2:.3f}, df={dof}, p={p_value:.4g}, Cramer's V={cramer:.3f}")
    lines.extend(["", *h11_lines, "", "## Comparison", ""])
    lines.append("See data/RQ2/codebook.md. Categories without a Lucena counterpart stay separate.")
    (folder / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with (folder / "category_counts.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["strategy", "tool", "category", "count"])
        for strategy in strategies:
            for cat in categories:
                writer.writerow([strategy, TOOL_OF[strategy], cat, table[(strategy, cat)]])


def _write_validation_sample(rows: list[dict]) -> None:
    rng = random.Random(SEED)
    pool = [row for row in rows if row["category"]]
    rng.shuffle(pool)
    picked = pool[:200]
    path = OUT / "validation_sample.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[
            "repository_full_name", "strategy", "file", "construct", "category", "subtype", "subject",
            "raw_text", "gold_category",
        ])
        writer.writeheader()
        for row in picked:
            writer.writerow({
                "repository_full_name": row["repository_full_name"],
                "strategy": row["strategy"],
                "file": row["file"],
                "construct": row["construct"],
                "category": row["category"],
                "subtype": row.get("subtype") or "",
                "subject": row.get("subject") or "",
                "raw_text": row["raw_text"],
                "gold_category": "",
            })


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
    return point, stats[int(0.025 * (BOOTSTRAP_DRAWS - 1))], stats[int(0.975 * (BOOTSTRAP_DRAWS - 1))]


def _iter_constructs() -> list[dict]:
    latest = {}
    if not CONSTRUCTS.exists():
        return []
    with CONSTRUCTS.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            identity = (row["repository_id"], row["strategy"], row["file"], row["construct"], row.get("raw_text", ""))
            latest[identity] = row
    return list(latest.values())


def _key(subject: dict) -> str:
    return f"{subject['repository_id']}|{subject['strategy']}"


def _load_jsonl(path: Path) -> dict[str, dict]:
    latest = {}
    if not path.exists():
        return latest
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if row.get("key"):
                latest[row["key"]] = row
    return latest


def _append_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def collect_files(subjects: list[dict]) -> None:
    """Download full rule files. Does not parse rules."""
    FILES_CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    done = _load_jsonl(FILES_CHECKPOINT)
    pending = [
        subject for subject in subjects
        if done.get(_key(subject), {}).get("status") not in FILES_SKIP_STATUS
    ]
    print(
        f"files: {len(subjects) - len(pending)} skipped, {len(pending)} pending, "
        f"{len(subjects)} subjects",
        flush=True,
    )
    client = GithubClient(min_interval=6.5, repo_limiter=RateLimiter(0.8))
    try:
        for index, subject in enumerate(pending, start=1):
            prior = done.get(_key(subject), {}).get("status")
            try:
                record, rows = _collect_subject(client, subject)
            except Exception as exc:  # noqa: BLE001 — one repo must not stop the corpus
                record = _file_checkpoint(subject, status="error", error=str(exc)[:500])
                rows = []
            if prior in {"error", "truncated"}:
                _drop_subject_files(subject)
            if rows:
                _append_jsonl(FILES, rows)
            _append_jsonl(FILES_CHECKPOINT, [record])
            done[_key(subject)] = record
            print(
                f"files {index}/{len(pending)} {subject['repository_full_name']} "
                f"{subject['strategy']} {record['status']} files={record['n_files']} "
                f"candidates={record['n_candidates']} truncated={str(record['truncated']).lower()} "
                f"transport={record.get('transport') or '-'}",
                flush=True,
            )
    finally:
        _write_files_manifest(subjects)
    print("files phase finished", flush=True)


def _collect_subject(client: GithubClient, subject: dict) -> tuple[dict, list[dict]]:
    full_name = subject["repository_full_name"]
    if not full_name:
        return _file_checkpoint(subject, status="error", error="missing repository_full_name"), []
    clone: dict = {"dest": None, "rev": ""}
    try:
        try:
            commit_sha, blobs, api_truncated = _default_blobs(client, full_name)
        except LookupError as exc:
            message = str(exc)[:500]
            status = "unavailable" if message == "repository not found" else "error"
            return _file_checkpoint(subject, status=status, error=message), []
        if api_truncated:
            try:
                dest, rev = _clone_repository(full_name, commit_sha)
                clone = {"dest": dest, "rev": rev}
                blobs = _list_clone_blobs(dest, rev)
                commit_sha = rev or commit_sha
            except (RuntimeError, subprocess.TimeoutExpired, OSError) as exc:
                return _file_checkpoint(
                    subject,
                    status="truncated",
                    truncated=True,
                    error=f"partial clone failed: {exc}"[:500],
                    commit_sha=commit_sha,
                ), []
        if subject["strategy"] == "MavenCrawler":
            return _collect_archunit(client, subject, commit_sha, blobs, api_truncated, clone)
        return _collect_named(client, subject, commit_sha, blobs, api_truncated)
    finally:
        if clone["dest"] is not None:
            shutil.rmtree(clone["dest"], ignore_errors=True)


def _collect_archunit(
    client: GithubClient,
    subject: dict,
    commit_sha: str,
    blobs: list[tuple[str, str]],
    api_truncated: bool,
    clone: dict,
) -> tuple[dict, list[dict]]:
    full_name = subject["repository_full_name"]
    failed: list[dict] = []
    roots: list[str] = []
    manifests = manifest_entries(blobs)
    if content_transport(False, len(manifests)) == "sparse":
        manifest_files, manifest_failed = _sparse_download(full_name, commit_sha, manifests, clone)
        failed.extend(manifest_failed)
    else:
        manifest_files = []
        for path, sha in manifests:
            text, err = _download(client, full_name, path, sha)
            if text is None:
                failed.append({"path": path, "error": err or "empty blob"})
                continue
            manifest_files.append((path, sha, text))
    for path, _sha, text in manifest_files:
        roots.extend(test_roots_from_manifest(path, text))
    sources = select_archunit_sources(blobs, roots)
    transport = content_transport(api_truncated, len(sources))
    if transport == "sparse":
        downloaded, sparse_failed = _sparse_download(full_name, commit_sha, sources, clone)
        failed.extend(sparse_failed)
    else:
        downloaded = []
        for path, sha in sources:
            text, err = _download(client, full_name, path, sha)
            if text is None:
                failed.append({"path": path, "error": err or "empty blob"})
                continue
            downloaded.append((path, sha, text))
    rows = [
        _file_row(subject, path, sha, text)
        for path, sha, text in downloaded
        if contains_archunit(text)
    ]
    return _finish_checkpoint(
        subject,
        rows=rows,
        n_candidates=len(sources),
        truncated=api_truncated,
        failed=failed,
        commit_sha=commit_sha,
        transport=transport,
    ), rows


def _collect_named(
    client: GithubClient,
    subject: dict,
    commit_sha: str,
    blobs: list[tuple[str, str]],
    api_truncated: bool,
) -> tuple[dict, list[dict]]:
    """import-linter and dependency-cruiser: filename filter, blob download, no checkout."""
    full_name = subject["repository_full_name"]
    chosen: list[tuple[str, str, str]] = []
    for path, sha in blobs:
        if subject["strategy"] == "PypiCrawler":
            mode = importlinter_mode(path)
            if mode:
                chosen.append((path, sha, mode))
        elif is_depcruise(path):
            chosen.append((path, sha, "filename"))
    failed: list[dict] = []
    rows: list[dict] = []
    for path, sha, mode in chosen:
        text, err = _download(client, full_name, path, sha)
        if text is None:
            failed.append({"path": path, "error": err or "empty blob"})
            continue
        if mode == "content" and not pyproject_has_importlinter(text):
            continue
        rows.append(_file_row(subject, path, sha, text))
    return _finish_checkpoint(
        subject,
        rows=rows,
        n_candidates=len(chosen),
        truncated=api_truncated,
        failed=failed,
        commit_sha=commit_sha,
        transport="blob",
    ), rows


def _finish_checkpoint(
    subject: dict,
    rows: list[dict],
    n_candidates: int,
    truncated: bool,
    failed: list[dict],
    commit_sha: str,
    transport: str,
) -> dict:
    if failed:
        status = "error"
        error = f"failed to download {len(failed)} paths"
    elif rows:
        status = "complete"
        error = ""
    else:
        status = "no_rule_file"
        error = ""
    return _file_checkpoint(
        subject,
        status=status,
        n_files=len(rows),
        n_candidates=n_candidates,
        truncated=truncated,
        error=error,
        failed_paths=failed,
        commit_sha=commit_sha,
        transport=transport,
    )


def _file_checkpoint(
    subject: dict,
    status: str,
    n_files: int = 0,
    n_candidates: int = 0,
    truncated: bool = False,
    error: str = "",
    failed_paths: list[dict] | None = None,
    commit_sha: str = "",
    transport: str = "",
) -> dict:
    return {
        "key": _key(subject),
        "sample_index": subject["sample_index"],
        "repository_id": subject["repository_id"],
        "repository_full_name": subject["repository_full_name"],
        "strategy": subject["strategy"],
        "reason": subject["reason"],
        "commit_sha": commit_sha,
        "status": status,
        "n_files": n_files,
        "n_candidates": n_candidates,
        "truncated": bool(truncated),
        "error": error,
        "failed_paths": failed_paths or [],
        "transport": transport,
    }


def _file_row(subject: dict, path: str, sha: str, text: str) -> dict:
    return {
        "repository_id": subject["repository_id"],
        "repository_full_name": subject["repository_full_name"],
        "strategy": subject["strategy"],
        "reason": subject["reason"],
        "sample_index": subject["sample_index"],
        "file": path,
        "sha": sha,
        "text": text,
    }


def _default_blobs(client: GithubClient, full_name: str) -> tuple[str, list[tuple[str, str]], bool]:
    repo = client.get_repo(full_name)
    if not isinstance(repo, dict):
        raise LookupError("repository not found")
    branch = repo.get("default_branch") or "HEAD"
    ref = client._get(f"/repos/{full_name}/branches/{quote(branch, safe='')}")
    if not isinstance(ref, dict):
        raise LookupError("default branch not found")
    commit = ref.get("commit") if isinstance(ref.get("commit"), dict) else {}
    commit_sha = commit.get("sha") or ""
    if not commit_sha:
        raise LookupError("missing commit sha")
    tree = client._get(
        f"/repos/{full_name}/git/trees/{commit_sha}",
        params={"recursive": "1"},
    )
    if not isinstance(tree, dict):
        raise LookupError("git tree missing")
    blobs = []
    for entry in tree.get("tree") or []:
        if entry.get("type") != "blob":
            continue
        path = entry.get("path") or ""
        if path:
            blobs.append((path, entry.get("sha") or ""))
    return commit_sha, blobs, bool(tree.get("truncated"))


def _clone_repository(full_name: str, commit_sha: str) -> tuple[Path, str]:
    dest = Path(tempfile.mkdtemp(prefix="rq2-sparse-"))
    try:
        url = f"https://github.com/{full_name}.git"
        _git(
            ["git", "clone", "--filter=blob:none", "--depth=1", "--no-checkout", url, str(dest)],
            timeout=600,
        )
        head = _git(["git", "rev-parse", "HEAD"], cwd=dest).strip()
        rev = head
        if commit_sha and commit_sha != head:
            try:
                _git(
                    ["git", "fetch", "--filter=blob:none", "--depth=1", "origin", commit_sha],
                    cwd=dest,
                    timeout=600,
                )
                rev = commit_sha
            except (RuntimeError, subprocess.TimeoutExpired):
                rev = head
        return dest, rev
    except Exception:
        shutil.rmtree(dest, ignore_errors=True)
        raise


def _list_clone_blobs(dest: Path, rev: str) -> list[tuple[str, str]]:
    listing = _git(["git", "ls-tree", "-r", "-z", rev], cwd=dest, timeout=180)
    entries = []
    for record in listing.split("\0"):
        if not record or "\t" not in record:
            continue
        meta, path = record.split("\t", 1)
        parts = meta.split()
        if len(parts) >= 3 and parts[1] == "blob" and path:
            entries.append((path, parts[2]))
    return entries


def _sparse_pattern(path: str) -> str:
    """One no-cone sparse-checkout pattern. Glob metacharacters stay literal."""
    escaped = "".join(f"\\{char}" if char in "\\*?[]" else char for char in path)
    return f"/{escaped}"


def _sparse_download(
    full_name: str,
    commit_sha: str,
    sources: list[tuple[str, str]],
    clone: dict,
) -> tuple[list[tuple[str, str, str]], list[dict]]:
    if not sources:
        return [], []
    dest = clone.get("dest")
    rev = clone.get("rev") or commit_sha
    if dest is None:
        dest, rev = _clone_repository(full_name, commit_sha)
        clone["dest"] = dest
        clone["rev"] = rev
    patterns = "".join(f"{_sparse_pattern(path)}\n" for path, _sha in sources)
    _git(
        ["git", "sparse-checkout", "set", "--no-cone", "--stdin", "--skip-checks"],
        cwd=dest,
        input_text=patterns,
        timeout=180,
    )
    _git(["git", "checkout", rev or "HEAD"], cwd=dest, timeout=900)
    downloaded = []
    failed = []
    for path, sha in sources:
        file = dest / path
        if not file.is_file():
            failed.append({"path": path, "error": "missing after sparse checkout"})
            continue
        try:
            text = file.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            failed.append({"path": path, "error": str(exc)[:300]})
            continue
        downloaded.append((path, sha, text))
    return downloaded, failed


def _git(args: list[str], cwd: Path | None = None, timeout: int = 180, input_text: str | None = None) -> str:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    result = subprocess.run(
        args,
        cwd=cwd,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        env=env,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "git failed").strip()
        raise RuntimeError(detail[-500:])
    return result.stdout


def _drop_subject_files(subject: dict) -> None:
    """Remove one repository's rows so a retry does not duplicate them."""
    if not FILES.exists():
        return
    repository_id = subject["repository_id"]
    strategy = subject["strategy"]
    kept: list[str] = []
    found = False
    with FILES.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                row = json.loads(stripped)
            except json.JSONDecodeError:
                kept.append(line if line.endswith("\n") else line + "\n")
                continue
            if row.get("repository_id") == repository_id and row.get("strategy") == strategy:
                found = True
                continue
            kept.append(line if line.endswith("\n") else line + "\n")
    if not found:
        return
    temporary = FILES.with_suffix(".jsonl.tmp")
    temporary.write_text("".join(kept), encoding="utf-8")
    temporary.replace(FILES)


def _write_files_manifest(subjects: list[dict]) -> None:
    latest = _load_jsonl(FILES_CHECKPOINT)
    by_status: Counter = Counter()
    for subject in subjects:
        by_status[latest.get(_key(subject), {}).get("status") or "pending"] += 1
    file_counts: Counter = Counter()
    n_lines = 0
    if FILES.exists():
        with FILES.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                n_lines += 1
                file_counts[row.get("strategy") or ""] += 1
    zero = []
    truncated_rows = []
    error_rows = []
    unavailable_rows = []
    recovered = 0
    for subject in subjects:
        record = latest.get(_key(subject), {})
        status = record.get("status")
        if status == "no_rule_file":
            zero.append(subject)
        elif status == "truncated":
            truncated_rows.append((subject, record))
        elif status == "error":
            error_rows.append((subject, record))
        elif status == "unavailable":
            unavailable_rows.append((subject, record))
        elif record.get("truncated") and status in FILES_SKIP_STATUS:
            recovered += 1
    lines = [
        "# RQ2 file collection",
        "",
        f"Subjects (kept + extended): {len(subjects)}",
        f"Files stored: {n_lines}",
        f"Recovered after a truncated git tree: {recovered}",
        "",
        "## Status",
        "",
    ]
    for status in ("complete", "no_rule_file", "truncated", "error", "unavailable", "pending"):
        lines.append(f"- {status}: {by_status[status]}")
    lines.extend(["", "## Files by tool", ""])
    for strategy, tool in TOOL_OF.items():
        repos = sum(
            1
            for subject in subjects
            if subject["strategy"] == strategy and latest.get(_key(subject), {}).get("n_files", 0)
        )
        lines.append(f"- {tool}: {file_counts[strategy]} files across {repos} repositories")
    lines.extend(["", "## Zero-file repositories", ""])
    if zero:
        for subject in zero:
            lines.append(f"- {subject['repository_full_name']} ({TOOL_OF.get(subject['strategy'], subject['strategy'])})")
    else:
        lines.append("None.")
    lines.extend(["", "## Truncated", ""])
    if truncated_rows:
        for subject, record in truncated_rows:
            lines.append(
                f"- {subject['repository_full_name']} ({subject['strategy']}): {record.get('error') or 'tree truncated'}"
            )
    else:
        lines.append("None.")
    lines.extend(["", "## Error", ""])
    if error_rows:
        for subject, record in error_rows:
            lines.append(
                f"- {subject['repository_full_name']} ({subject['strategy']}): {record.get('error') or 'error'}"
            )
    else:
        lines.append("None.")
    lines.extend(["", "## Unavailable", ""])
    if unavailable_rows:
        for subject, record in unavailable_rows:
            lines.append(
                f"- {subject['repository_full_name']} ({subject['strategy']}): {record.get('error') or 'repository not found'}"
            )
    else:
        lines.append("None.")
    lines.append("")
    FILES_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    FILES_MANIFEST.write_text("\n".join(lines), encoding="utf-8")


def promote_repository_not_found() -> None:
    """Close 404 repositories. Does not read or write files.jsonl."""
    latest = _load_jsonl(FILES_CHECKPOINT)
    subjects = load_subjects()
    rows = []
    for subject in subjects:
        record = latest.get(_key(subject), {})
        if record.get("status") != "error" or record.get("error") != "repository not found":
            continue
        rows.append(_file_checkpoint(
            subject,
            status="unavailable",
            n_files=int(record.get("n_files") or 0),
            n_candidates=int(record.get("n_candidates") or 0),
            truncated=bool(record.get("truncated")),
            error="repository not found",
            failed_paths=record.get("failed_paths") or [],
            commit_sha=record.get("commit_sha") or "",
            transport=record.get("transport") or "",
        ))
    if len(rows) != 15:
        raise SystemExit(f"expected 15 repository-not-found rows, found {len(rows)}")
    _append_jsonl(FILES_CHECKPOINT, rows)
    _write_files_manifest(subjects)
    print(f"unavailable={len(rows)}", flush=True)


def _assert_files_ready() -> None:
    if not FILES_MANIFEST.exists():
        raise SystemExit("files_manifest.md is missing; file collection has not finished")
    latest = _load_jsonl(FILES_CHECKPOINT)
    blocked = 0
    unfinished = 0
    for subject in load_subjects():
        status = latest.get(_key(subject), {}).get("status")
        if status in {"error", "truncated"}:
            blocked += 1
        elif status not in FILES_SKIP_STATUS:
            unfinished += 1
    if blocked or unfinished:
        raise SystemExit(
            f"file collection is not finished ({blocked} error or truncated, {unfinished} not checkpointed); not continuing"
        )


def freeze_codebook() -> None:
    """Freeze the dev-set map. Does not compute H2.1 and does not write codebook.md."""
    from analysis.rq2_dev_classify import DETAIL, STRUCTURAL, TAXONOMY, _detail_record

    if not FILES.exists():
        raise SystemExit(f"missing {FILES}")
    unknown: set[str] = set()
    seen_files = 0
    with FILES.open(encoding="utf-8") as source:
        for line in source:
            line = line.strip()
            if not line:
                continue
            try:
                file_row = json.loads(line)
            except json.JSONDecodeError:
                continue
            sample_index = int(file_row.get("sample_index") or 0)
            if sample_index >= DEV_LIMIT:
                continue
            seen_files += 1
            for item in _extract_file(file_row):
                construct = item.get("construct") or "unparsed"
                if construct not in DETAIL:
                    unknown.add(construct)
    mapping = {construct: _detail_record(construct) for construct in sorted(DETAIL)}
    (OUT / "codebook_map.json").write_text(
        json.dumps(
            {"taxonomy": TAXONOMY, "structural_family": list(STRUCTURAL), "map": mapping},
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    unknown_path = OUT / "dev_unknown_constructs.txt"
    unknown_path.write_text(
        "".join(f"{construct}\n" for construct in sorted(unknown)),
        encoding="utf-8",
    )
    print(
        f"codebook dev_files={seen_files} mapped={len(mapping)} unknown={len(unknown)}",
        flush=True,
    )


def parse_rules() -> None:
    """Parse full file text. Does not compute H2.1 and does not write the codebook."""
    _assert_files_ready()
    codebook_path = OUT / "codebook_map.json"
    if not codebook_path.exists():
        raise SystemExit(f"missing {codebook_path}")
    codebook = json.loads(codebook_path.read_text(encoding="utf-8"))
    mapping = codebook.get("map") or {}
    if not FILES.exists():
        CONSTRUCTS_FULL.write_text("", encoding="utf-8")
        print("parse constructs=0", flush=True)
        return
    temporary = CONSTRUCTS_FULL.with_suffix(".jsonl.tmp")
    written = 0
    with FILES.open(encoding="utf-8") as source, temporary.open("w", encoding="utf-8") as handle:
        for line in source:
            line = line.strip()
            if not line:
                continue
            try:
                file_row = json.loads(line)
            except json.JSONDecodeError:
                continue
            for item in _extract_file(file_row):
                handle.write(json.dumps(_construct_row(file_row, item, mapping), ensure_ascii=False) + "\n")
                written += 1
    temporary.replace(CONSTRUCTS_FULL)
    print(f"parse constructs={written}", flush=True)


def _extract_file(file_row: dict) -> list[dict]:
    text = file_row.get("text") or ""
    path = file_row.get("file") or ""
    strategy = file_row.get("strategy")
    if strategy == "MavenCrawler":
        extracted = extract_archunit(text)
    elif strategy == "PypiCrawler":
        extracted = extract_importlinter(text, path)
    else:
        extracted = extract_depcruise(text, path)
    if not extracted:
        return [{"construct": "unparsed", "exemption": False, "raw_text": text}]
    return extracted


def _label(mapping: dict, construct: str) -> tuple[str, str, str]:
    """Return category, dependency subtype, and subject. Missing maps stay unparsed."""
    mapped = mapping.get(construct)
    if construct in NOT_CATEGORIES or not mapped:
        return "unparsed", "", ""
    if isinstance(mapped, dict):
        category = mapped.get("category") or ""
        if not category:
            return "unparsed", "", ""
        return category, mapped.get("subtype") or "", mapped.get("subject") or ""
    return str(mapped), "", ""


def _construct_row(file_row: dict, item: dict, mapping: dict) -> dict:
    construct = item.get("construct") or "unparsed"
    category, subtype, subject = _label(mapping, construct)
    sample_index = int(file_row.get("sample_index") or 0)
    exemption = bool(item.get("exemption")) or construct in NOT_CATEGORIES
    return {
        "sample_index": sample_index,
        "repository_id": file_row.get("repository_id"),
        "repository_full_name": file_row.get("repository_full_name"),
        "strategy": file_row.get("strategy"),
        "reason": file_row.get("reason"),
        "file": file_row.get("file") or "",
        "construct": construct,
        "category": category,
        "subtype": subtype,
        "subject": subject,
        "exemption": exemption,
        "raw_text": item.get("raw_text") or "",
        "dev": sample_index < DEV_LIMIT,
    }


def stats() -> None:
    """Held-out coverage, association, and H2.1. Dev rows stay out."""
    _assert_files_ready()
    if not CONSTRUCTS_FULL.exists():
        raise SystemExit(f"missing {CONSTRUCTS_FULL}")
    codebook = json.loads((OUT / "codebook_map.json").read_text(encoding="utf-8"))
    family = set(codebook.get("structural_family") or [])
    held_out = []
    with CONSTRUCTS_FULL.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            sample_index = int(row.get("sample_index") or 0)
            if row.get("dev") or sample_index < DEV_LIMIT:
                continue
            if not row.get("category"):
                row = {**row, "category": "unparsed"}
            held_out.append(row)
    cohorts = {
        "no_extend": [row for row in held_out if row.get("reason") == "kept"],
        "with_extend": held_out,
    }
    for name, rows in cohorts.items():
        _write_cohort(name, rows, family)
    _write_validation_sample([row for row in held_out if row.get("category") not in {"", "unparsed"}])
    print(f"stats held_out_constructs={len(held_out)}", flush=True)


if __name__ == "__main__":
    main()
