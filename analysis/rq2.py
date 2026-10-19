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
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from github.client import GithubClient, RateLimiter  # noqa: E402
from parsers.archunit import extract as extract_archunit  # noqa: E402
from parsers.depcruise import extract as extract_depcruise  # noqa: E402
from parsers.importlinter import extract as extract_importlinter  # noqa: E402

OUT = ROOT / "data" / "RQ2"
CHECKPOINT = OUT / "checkpoints" / "subjects.jsonl"
CONSTRUCTS = OUT / "constructs.jsonl"
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
    parser.add_argument("--phase", choices=("fetch", "report"), default="fetch")
    parser.add_argument("--limit", type=int, default=0, help="If set, only the first N union rows")
    parser.add_argument("--offset", type=int, default=0)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    subjects = load_subjects()
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
    if not isinstance(payload, dict):
        return None
    content = payload.get("content")
    if payload.get("encoding") == "base64" and content:
        return base64.b64decode(content).decode("utf-8", errors="replace")
    return None


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
        category = mapping.get(row["construct"])
        labeled.append({**row, "category": category or ""})
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
    categories = sorted({cat for _, cat in table})
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
    h11_lines = ["## H2.1 structural family", ""]
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
            "repository_full_name", "strategy", "file", "construct", "category", "raw_text", "gold_category",
        ])
        writer.writeheader()
        for row in picked:
            writer.writerow({
                "repository_full_name": row["repository_full_name"],
                "strategy": row["strategy"],
                "file": row["file"],
                "construct": row["construct"],
                "category": row["category"],
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


if __name__ == "__main__":
    main()
