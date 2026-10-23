"""RQ3 history, classification, and survival.

History clones each RQ2-complete repository once, keeps the clone, and runs
git log -p on the rule paths stored in data/RQ2/files.jsonl. A clone or
history failure excludes that repository and does not stop the batch.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import json
import os
import random
import shutil
import signal
import subprocess
import time
from collections import Counter, defaultdict

from analysis.corpuslib import (
    CLASS_DIR,
    COHORTS,
    CONCAT_MANIFEST,
    DATA,
    EDITS,
    EDITS_RAW,
    GOLD,
    HISTORY_CHECKPOINT,
    META_DIR,
    RAW_DIR,
    RQ3,
    SEED,
    STATS_JSON,
    TOOLS,
    assert_files_hash,
    bootstrap,
    clone_path,
    ensure_dirs,
    file_stem,
    git_env,
    history_status,
    in_cohort,
    load_adoption,
    load_ci,
    load_corpus,
    load_paths,
    load_rq2_subjects,
    months_between,
    parse_dt,
    prepare_exclusions,
    rel_clone,
    append_exclusion,
    exclusion_row,
    write_attrition,
    write_counts,
    write_csv,
)
from analysis.editclass import classify_edit
from analysis.survival import bootstrap_incidence, cox_ph

H31_EVENT = {"exempt", "disable"}
SURVIVAL_EVENT = {"loosen", "exempt"}
ZERO_SHA = "0" * 40


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True, choices=("prepare", "history", "stats"))
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--only", default="", help="Comma-separated repository_full_name values")
    args = parser.parse_args()
    ensure_dirs()
    if args.phase == "prepare":
        count = prepare_exclusions()
        print(f"exclusions written: {count}", flush=True)
        return
    if args.phase == "history":
        run_history(args.workers, args.limit, args.only)
        return
    run_stats()


def run_history(workers: int, limit: int, only: str = "") -> None:
    assert_files_hash()
    prepare_exclusions()
    subjects = [row for row in load_rq2_subjects() if row["status"] == "complete"]
    paths = load_paths()
    missing = [row["key"] for row in subjects if not paths.get(row["key"])]
    if missing:
        raise SystemExit(f"{len(missing)} complete repos have no paths in files.jsonl")
    done = history_status()
    pending = [row for row in subjects if row["key"] not in done]
    if only:
        wanted = {name.strip() for name in only.split(",") if name.strip()}
        pending = [row for row in pending if row["repository_full_name"] in wanted]
    if limit:
        pending = pending[:limit]
    total = len(subjects)
    print(
        f"history total={total} checkpointed={len(done)} pending={len(pending)} workers={workers}",
        flush=True,
    )
    adoption = load_adoption()
    ci = load_ci()
    from concurrent.futures import ThreadPoolExecutor, as_completed

    finished = len(done)
    complete = sum(1 for row in done.values() if row.get("status") == "complete")
    excluded = sum(1 for row in done.values() if row.get("status") == "excluded")
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {
            pool.submit(_history_one, subject, paths[subject["key"]]): subject
            for subject in pending
        }
        for future in as_completed(futures):
            subject = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # one repository must not stop the batch
                _discard_clone(subject)
                result = {"status": "excluded", "error": str(exc)[:500], "n_edits": 0, "head_sha": ""}
            finished += 1
            if result["status"] == "complete":
                complete += 1
                _checkpoint(subject, "complete", "", result.get("n_edits") or 0, result.get("head_sha") or "")
            else:
                excluded += 1
                _discard_clone(subject)
                _drop_parts(subject)
                reason = result.get("error") or "clone failed"
                append_exclusion(exclusion_row(subject, "clone_error", reason, adoption, ci))
                _checkpoint(subject, "excluded", reason, 0, "")
            free = shutil.disk_usage(DATA).free / 1e9
            print(
                f"history {finished}/{total} {result['status']} edits={result.get('n_edits') or 0} "
                f"complete={complete} excluded={excluded} free_gb={free:.1f} {subject['repository_full_name']}",
                flush=True,
            )
            if finished % 10 == 0 or finished == total:
                _write_progress(finished, total, complete, excluded, free)
    if not limit and finished >= total and len(history_status()) >= total:
        concat_parts()
        (RQ3 / "history_done.json").write_text(
            json.dumps(_status_payload(), indent=2) + "\n",
            encoding="utf-8",
        )
        write_attrition()
        assert_files_hash()
        print("history finished", flush=True)


def _history_one(subject: dict, paths: list[str]) -> dict:
    dest = clone_path(subject["repository_id"], subject["strategy"])
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = f"https://github.com/{subject['repository_full_name']}.git"
    _run(
        [
            "git", "-c", "http.version=HTTP/1.1", "-c", "advice.detachedHead=false",
            "clone", "--filter=blob:none", "--single-branch", "--no-tags", "--no-checkout",
            "--quiet", url, str(dest),
        ],
        timeout=1200,
    )
    if not (dest / ".git").exists():
        raise RuntimeError("clone produced no .git directory")
    head = _run(["git", "--no-pager", "-C", str(dest), "rev-parse", "HEAD"], timeout=60).strip()
    first, last = _repo_dates(dest)
    edits, files = _log_paths(dest, subject, paths)
    meta = {
        "repository_id": subject["repository_id"],
        "repository_full_name": subject["repository_full_name"],
        "strategy": subject["strategy"],
        "tool": subject["tool"],
        "reason": subject["reason"],
        "sample_index": subject["sample_index"],
        "status": "complete",
        "n_files": len(files),
        "n_edits": len(edits["raw"]),
        "head_sha": head,
        "first_commit_date": first,
        "last_commit_date": last,
        "paths": paths,
        "files": files,
        "clone_dir": rel_clone(subject["repository_id"], subject["strategy"]),
    }
    meta.update(_adoption(subject, files))
    stem = file_stem(subject["repository_id"], subject["strategy"])
    _write_json(META_DIR / f"{stem}.json", meta)
    _write_jsonl(RAW_DIR / f"{stem}.jsonl", edits["raw"])
    _write_jsonl(CLASS_DIR / f"{stem}.jsonl", edits["classified"])
    return {"status": "complete", "n_edits": len(edits["raw"]), "head_sha": head}


def _log_paths(dest: Path, subject: dict, paths: list[str]) -> tuple[dict, list[dict]]:
    raw_rows: list[dict] = []
    classified_rows: list[dict] = []
    file_events: list[dict] = []
    timeout = 3600 if len(paths) > 25 else 1200
    if len(paths) > 25:
        grouped = _commits_for(dest, paths, follow=False, timeout=timeout)
    else:
        grouped = {}
        for path in paths:
            found = _commits_for(dest, [path], follow=True, timeout=timeout)
            for name, commits in found.items():
                grouped.setdefault(name, []).extend(commits)
    if not grouped and paths:
        raise RuntimeError("git log returned no commits for rule paths")
    for path in paths:
        commits = grouped.get(path) or []
        deduped = {commit["commit"]: commit for commit in commits}
        commits = sorted(deduped.values(), key=lambda item: item["date"])
        blobs = _blobs(dest, [sha for commit in commits for sha in (commit["before_sha"], commit["after_sha"])])
        events = []
        for commit in commits:
            before = blobs.get(commit["before_sha"], "")
            after = blobs.get(commit["after_sha"], "")
            if not before and not after:
                continue
            classified = classify_edit(subject["strategy"], path, before, after)
            identity = {
                "repository_id": subject["repository_id"],
                "repository_full_name": subject["repository_full_name"],
                "strategy": subject["strategy"],
                "tool": subject["tool"],
                "reason": subject["reason"],
                "sample_index": subject["sample_index"],
                "commit": commit["commit"],
                "date": commit["date"],
                "author": commit["author"],
                "path": path,
            }
            raw_rows.append({**identity, "text_before": before, "text_after": after})
            classified_rows.append({**identity, **classified})
            events.append({
                "commit": commit["commit"],
                "date": commit["date"],
                "author": commit["author"],
                "edit_class": classified["edit_class"],
                "classes": classified["classes"],
                "introduces_rule": classified["introduces_rule"],
                "path_at_commit": commit.get("path_at_commit") or path,
            })
        if events:
            file_events.append({"path": path, "commits": events})
    if not file_events:
        raise RuntimeError("rule paths produced no textual edits")
    return {"raw": raw_rows, "classified": classified_rows}, file_events


def _commits_for(dest: Path, paths: list[str], follow: bool, timeout: int) -> dict[str, list[dict]]:
    command = [
        "git", "-c", "http.version=HTTP/1.1", "-c", "core.abbrev=40",
        "--no-pager", "-C", str(dest),
        "log", "-p", "-U0", "--raw", "--no-color",
    ]
    assign_follow = follow and len(paths) == 1
    if assign_follow:
        command.append("--follow")
    else:
        command.extend(["--first-parent", "-m"])
    command.extend(["--format=%x1e%H%x1f%aI%x1f%aN", "--", *paths])
    grouped: dict[str, list[dict]] = defaultdict(list)
    asked = set(paths)
    header = None
    deadline = time.monotonic() + timeout
    code = 1
    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        errors="replace",
        start_new_session=True,
        env=git_env(),
    )
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            if time.monotonic() > deadline:
                raise TimeoutError(f"git log exceeded {timeout}s for {paths[0]}")
            if line.startswith("\x1e"):
                parts = line[1:].rstrip("\n").split("\x1f")
                header = {
                    "commit": parts[0],
                    "date": parts[1] if len(parts) > 1 else "",
                    "author": parts[2] if len(parts) > 2 else "",
                }
                continue
            if header is None or not line.startswith(":") or not line[1:2].isdigit():
                continue
            meta, _, path_field = line[1:].rstrip("\n").partition("\t")
            bits = meta.split()
            if len(bits) < 5 or not path_field:
                continue
            changed = path_field.split("\t")
            historical = changed[-1]
            if assign_follow:
                key = paths[0]
            elif historical in asked:
                key = historical
            elif changed[0] in asked:
                key = changed[0]
            else:
                continue
            grouped[key].append({
                "commit": header["commit"],
                "date": header["date"],
                "author": header["author"],
                "before_sha": bits[2],
                "after_sha": bits[3],
                "path_at_commit": historical,
            })
        code = proc.wait(timeout=120)
    finally:
        if proc.poll() is None:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=30)
    if code != 0 and not grouped:
        raise RuntimeError(f"git log failed with status {code}")
    return grouped


def _blobs(dest: Path, shas: list[str]) -> dict[str, str]:
    unique = []
    seen = set()
    for sha in shas:
        if not sha or set(sha) == {"0"} or sha in seen:
            continue
        seen.add(sha)
        unique.append(sha)
    found: dict[str, str] = {}
    if not unique:
        return found
    proc = subprocess.Popen(
        ["git", "--no-pager", "-C", str(dest), "cat-file", "--batch"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=git_env(),
    )
    assert proc.stdin is not None and proc.stdout is not None
    proc.stdin.write(("\n".join(unique) + "\n").encode())
    proc.stdin.close()
    while True:
        header = proc.stdout.readline()
        if not header:
            break
        parts = header.decode("utf-8", errors="replace").split()
        if len(parts) < 3 or parts[1] != "blob":
            continue
        data = proc.stdout.read(int(parts[2]))
        proc.stdout.read(1)
        text = data.decode("utf-8", errors="replace")
        found[parts[0]] = "" if "\x00" in text else text
    proc.wait(timeout=300)
    return found


def _repo_dates(dest: Path) -> tuple[str, str]:
    last = _run(["git", "--no-pager", "-C", str(dest), "log", "-1", "--format=%aI"], timeout=180).strip()
    roots = _run(
        ["git", "--no-pager", "-C", str(dest), "rev-list", "--max-parents=0", "HEAD"],
        timeout=300,
    ).split()
    dates = []
    for root in roots[:30]:
        dates.append(_run(
            ["git", "--no-pager", "-C", str(dest), "log", "-1", "--format=%aI", root],
            timeout=60,
        ).strip())
    parsed = [(parse_dt(value), value) for value in dates if parse_dt(value)]
    first = min(parsed, key=lambda item: item[0])[1] if parsed else last
    return first, last


def _adoption(subject: dict, files: list[dict]) -> dict:
    if subject["strategy"] != "MavenCrawler":
        return {"adoption_commit": "", "adoption_date": ""}
    found = []
    for file_row in files:
        for commit in file_row["commits"]:
            if commit.get("introduces_rule"):
                moment = parse_dt(commit["date"])
                if moment:
                    found.append((moment, commit["commit"], commit["date"]))
    if not found:
        return {"adoption_commit": "", "adoption_date": ""}
    moment, commit, date = min(found, key=lambda item: item[0])
    return {"adoption_commit": commit, "adoption_date": date}


def _run(args: list[str], timeout: int) -> str:
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        start_new_session=True,
        env=git_env(),
    )
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        raise TimeoutError(f"timeout {' '.join(args[:6])}")
    if proc.returncode != 0:
        detail = (err or out or "git failed").strip().replace("\n", " ")
        raise RuntimeError(detail[-500:])
    return out


def _checkpoint(subject: dict, status: str, error: str, n_edits: int, head_sha: str) -> None:
    row = {
        "key": subject["key"],
        "repository_id": subject["repository_id"],
        "repository_full_name": subject["repository_full_name"],
        "strategy": subject["strategy"],
        "tool": subject["tool"],
        "reason": subject["reason"],
        "sample_index": subject["sample_index"],
        "status": status,
        "error": error[:500],
        "n_edits": n_edits,
        "head_sha": head_sha,
        "clone_dir": rel_clone(subject["repository_id"], subject["strategy"]) if status == "complete" else "",
    }
    HISTORY_CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_CHECKPOINT.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def _discard_clone(subject: dict) -> None:
    dest = clone_path(subject["repository_id"], subject["strategy"])
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)


def _drop_parts(subject: dict) -> None:
    stem = file_stem(subject["repository_id"], subject["strategy"])
    for folder in (META_DIR, RAW_DIR, CLASS_DIR):
        path = folder / f"{stem}.json"
        if folder is not META_DIR:
            path = folder / f"{stem}.jsonl"
        if path.exists():
            path.unlink()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_progress(done: int, total: int, complete: int, excluded: int, free: float) -> None:
    payload = {
        "done": done,
        "total": total,
        "complete": complete,
        "excluded": excluded,
        "free_gb": round(free, 2),
    }
    (RQ3 / "progress.json").write_text(json.dumps(payload) + "\n", encoding="utf-8")


def _status_payload() -> dict:
    latest = history_status()
    counts = Counter(row.get("status") or "" for row in latest.values())
    return {"repositories": len(latest), "complete": counts["complete"], "excluded": counts["excluded"]}


def concat_parts() -> None:
    """Build edits_raw.jsonl and edits.jsonl from per-repo parts, without duplicating a resumed run."""
    latest = history_status()
    done_rows = _concat_done()
    raw_end = done_rows[-1]["raw_end"] if done_rows else 0
    class_end = done_rows[-1]["class_end"] if done_rows else 0
    done_keys = {row["key"] for row in done_rows}
    for path, end in ((EDITS_RAW, raw_end), (EDITS, class_end)):
        if path.exists() and path.stat().st_size != end:
            with path.open("ab") as handle:
                handle.truncate(end)
    with EDITS_RAW.open("ab") as raw, EDITS.open("ab") as classified, CONCAT_MANIFEST.open("a", encoding="utf-8") as manifest:
        for key, row in sorted(latest.items()):
            if row.get("status") != "complete" or key in done_keys:
                continue
            stem = file_stem(row["repository_id"], row["strategy"])
            raw_part = RAW_DIR / f"{stem}.jsonl"
            class_part = CLASS_DIR / f"{stem}.jsonl"
            if raw_part.exists():
                raw.write(raw_part.read_bytes())
            if class_part.exists():
                classified.write(class_part.read_bytes())
            raw.flush()
            classified.flush()
            os.fsync(raw.fileno())
            os.fsync(classified.fileno())
            record = {"key": key, "raw_end": raw.tell(), "class_end": classified.tell()}
            manifest.write(json.dumps(record) + "\n")
            manifest.flush()
            os.fsync(manifest.fileno())
            if raw_part.exists():
                raw_part.unlink()
            if class_part.exists():
                class_part.unlink()


def _concat_done() -> list[dict]:
    rows = []
    if not CONCAT_MANIFEST.exists():
        return rows
    for line in CONCAT_MANIFEST.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def run_stats() -> None:
    assert_files_hash()
    corpus = load_corpus()
    if not corpus:
        raise SystemExit("data/corpus.csv is missing; freeze the corpus before stats")
    if not EDITS.exists():
        concat_parts()
    metas = {}
    for row in corpus:
        path = META_DIR / f"{file_stem(row['repository_id'], row['strategy'])}.json"
        if not path.exists():
            raise SystemExit(f"missing history meta for {row['repository_full_name']}")
        metas[f"{row['repository_id']}|{row['strategy']}"] = json.loads(path.read_text(encoding="utf-8"))
    payload = {}
    for cohort in COHORTS:
        rows = [row for row in corpus if in_cohort(row["reason"], cohort)]
        payload[cohort] = _cohort_stats(rows, metas)
    STATS_JSON.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    _write_repo_lists(corpus)
    write_counts(RQ3 / "counts.csv", corpus)
    _write_gold()
    print(
        "stats "
        + " ".join(
            f"{cohort}={payload[cohort]['n_repos']}" for cohort in COHORTS
        ),
        flush=True,
    )


def _write_repo_lists(corpus: list[dict]) -> None:
    fields = ["repository_id", "repository_full_name", "strategy", "tool", "reason", "sample_index"]
    for cohort in COHORTS:
        rows = [row for row in corpus if in_cohort(row["reason"], cohort)]
        write_csv(RQ3 / cohort / "repos.csv", rows, fields)


def _cohort_stats(repos: list[dict], metas: dict[str, dict]) -> dict:
    files = []
    class_counts: Counter = Counter()
    class_by_tool: dict[str, Counter] = {tool: Counter() for tool in TOOLS}
    exemption_by_year: Counter = Counter()
    edits = 0
    for repo in repos:
        meta = metas[f"{repo['repository_id']}|{repo['strategy']}"]
        last = parse_dt(meta.get("last_commit_date") or "")
        for file_row in meta.get("files") or []:
            commits = file_row.get("commits") or []
            if not commits or last is None:
                continue
            origin = parse_dt(commits[0]["date"])
            if origin is None:
                continue
            files.append(_file_record(repo, commits, origin, last))
            for commit in commits:
                edits += 1
                class_counts[commit["edit_class"]] += 1
                class_by_tool[repo["tool"]][commit["edit_class"]] += 1
                if H31_EVENT.intersection(commit.get("classes") or []):
                    moment = parse_dt(commit["date"])
                    if moment:
                        exemption_by_year[str(moment.year)] += 1
    by_tool = {}
    for tool in TOOLS:
        tool_files = [row for row in files if row["tool"] == tool]
        by_tool[tool] = {
            "n_files": len(tool_files),
            "h31": _h31(tool_files),
            "h32": _h32(tool_files),
            "edit_classes": dict(class_by_tool[tool]),
        }
    return {
        "n_repos": len(repos),
        "n_files": len(files),
        "n_edits": edits,
        "edit_classes": dict(class_counts),
        "edit_class_share": {name: class_counts[name] / edits if edits else 0 for name in class_counts},
        "exemption_or_disable_by_year": dict(sorted(exemption_by_year.items())),
        "h31": _h31(files),
        "h32": _h32(files),
        "survival_loosen_or_exempt": _survival(files, SURVIVAL_EVENT),
        "by_tool": by_tool,
    }


def _file_record(repo: dict, commits: list[dict], origin, last) -> dict:
    h31 = _first_event(commits, H31_EVENT)
    survival = _first_event(commits, SURVIVAL_EVENT)
    authors = {commit.get("author") or "" for commit in commits}
    return {
        "tool": repo["tool"],
        "n_commits": len(commits),
        "n_authors": len(authors - {""}),
        "follow_months": max(0.0, months_between(origin, last)),
        "h31_months": None if h31 is None else max(0.0, months_between(origin, h31)),
        "survival_months": None if survival is None else max(0.0, months_between(origin, survival)),
        "never_modified": len(commits) == 1,
    }


def _first_event(commits: list[dict], classes: set[str]):
    for commit in commits:
        if classes.intersection(commit.get("classes") or []):
            return parse_dt(commit["date"])
    return None


def _h31(files: list[dict]) -> dict:
    times, events = _km_columns(files, "h31_months")
    estimate = bootstrap_incidence(times, events, 24.0)
    complete = [
        row["h31_months"] is not None and row["h31_months"] <= 24
        for row in files
        if row["follow_months"] >= 24 or (row["h31_months"] is not None and row["h31_months"] <= 24)
    ]
    complete_estimate = bootstrap(complete)
    point = estimate[0] if estimate else None
    return {
        "n_files": len(files),
        "km_incidence_24": None if estimate is None else {
            "point": estimate[0], "low": estimate[1], "high": estimate[2],
        },
        "meets_30": bool(point is not None and point >= 0.30),
        "complete_case": None if complete_estimate is None else {
            "n": len(complete),
            "point": complete_estimate[0],
            "low": complete_estimate[1],
            "high": complete_estimate[2],
        },
    }


def _h32(files: list[dict]) -> dict:
    flags = [row["never_modified"] for row in files]
    estimate = bootstrap(flags)
    if estimate is None:
        return {"n_files": 0}
    point, low, high = estimate
    return {
        "n_files": len(files),
        "n_never": sum(flags),
        "point": point,
        "low": low,
        "high": high,
        "below_0.738": point < 0.738,
        "interval_entirely_below_0.738": high < 0.738,
    }


def _survival(files: list[dict], label: str) -> dict:
    times, events = _km_columns(files, "survival_months")
    estimate = bootstrap_incidence(times, events, 24.0)
    covariates = [
        [math_log(row["n_commits"]) for row in files],
        [math_log(max(1, row["n_authors"])) for row in files],
    ]
    return {
        "event": label if isinstance(label, str) else "loosen_or_exempt",
        "km_incidence_24": None if estimate is None else {
            "point": estimate[0], "low": estimate[1], "high": estimate[2],
        },
        "cox": cox_ph(times, events, covariates),
    }


def _km_columns(files: list[dict], field: str) -> tuple[list[float], list[int]]:
    times = []
    events = []
    for row in files:
        event_time = row[field]
        if event_time is None:
            times.append(row["follow_months"])
            events.append(0)
        else:
            times.append(event_time)
            events.append(1)
    return times, events


def math_log(value: int) -> float:
    import math
    return math.log(max(1, value))


def _write_gold() -> None:
    rng = random.Random(SEED)
    strata: dict[tuple[str, str], list[dict]] = defaultdict(list)
    with EDITS.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            strata[(row.get("tool") or "", row.get("edit_class") or "")].append(row)
    total = sum(len(rows) for rows in strata.values())
    if total == 0:
        write_csv(GOLD, [], [
            "edit_id", "repository_id", "repository_full_name", "strategy", "tool", "reason",
            "commit", "date", "path", "edit_class", "classes", "text_before", "text_after",
            "gold_edit_class",
        ])
        return
    allocations = _allocate(strata, min(300, total))
    picked = []
    for key, count in allocations.items():
        pool = strata[key][:]
        rng.shuffle(pool)
        picked.extend(pool[:count])
    rng.shuffle(picked)
    rows = []
    for index, row in enumerate(picked, start=1):
        rows.append({
            "edit_id": f"E{index:04d}",
            "repository_id": row.get("repository_id") or "",
            "repository_full_name": row.get("repository_full_name") or "",
            "strategy": row.get("strategy") or "",
            "tool": row.get("tool") or "",
            "reason": row.get("reason") or "",
            "commit": row.get("commit") or "",
            "date": row.get("date") or "",
            "path": row.get("path") or "",
            "edit_class": row.get("edit_class") or "",
            "classes": "|".join(row.get("classes") or []),
            "text_before": row.get("text_before") or "",
            "text_after": row.get("text_after") or "",
            "gold_edit_class": "",
        })
    write_csv(GOLD, rows, list(rows[0].keys()) if rows else ["edit_id", "gold_edit_class"])
    print(f"gold edits={len(rows)}", flush=True)


def _allocate(strata: dict, target: int) -> dict:
    sizes = {key: len(rows) for key, rows in strata.items() if rows}
    total = sum(sizes.values())
    raw = {key: target * size / total for key, size in sizes.items()}
    base = {key: min(sizes[key], int(value)) for key, value in raw.items()}
    leftover = target - sum(base.values())
    order = sorted(sizes, key=lambda key: (-(raw[key] - base[key]), -sizes[key], key[0], key[1]))
    for key in order:
        if leftover <= 0:
            break
        if base[key] < sizes[key]:
            base[key] += 1
            leftover -= 1
    return {key: count for key, count in base.items() if count}


if __name__ == "__main__":
    main()
