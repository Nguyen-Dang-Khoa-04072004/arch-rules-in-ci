"""RQ4 treated-set selection and source-level replay on the RQ3 clones.

RQ4 does not clone the study repositories again. Replay starts once 150
ArchUnit repositories are known to have 12 months before and after the
RQ3 adoption commit. Below that threshold the panel stops.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import argparse
import csv
import json
import os
import shutil
import signal
import subprocess
import time

from analysis.corpuslib import (
    META_DIR,
    RQ2,
    RQ3,
    RQ4,
    TREATED_MIN,
    add_months,
    clone_path,
    ensure_dirs,
    file_stem,
    git_env,
    history_status,
    load_corpus,
    parse_dt,
    rel_clone,
    write_counts,
    write_csv,
)
from analysis.sourcegraph import Check, family_counts, graph_from_grep, translate

ELIGIBILITY = RQ4 / "eligibility"
REPLAY = RQ4 / "replay"
PANEL = RQ4 / "panel_eligibility.csv"
REPLAY_SUMMARY = RQ4 / "replay_summary.json"
PANEL_FIELDS = [
    "repository_id",
    "repository_full_name",
    "tool",
    "strategy",
    "reason",
    "cohort",
    "adoption_commit",
    "adoption_date",
    "first_commit_date",
    "last_commit_date",
    "eligible",
    "ineligibility_reason",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True, choices=("follow", "aggregate", "pilot"))
    parser.add_argument("--replay-workers", type=int, default=1)
    args = parser.parse_args()
    ensure_dirs()
    if args.phase == "follow":
        follow(args.replay_workers)
        return
    if args.phase == "aggregate":
        aggregate()
        return
    pilot()


def follow(replay_workers: int) -> None:
    """Select each ArchUnit repo when its history meta exists. Replay after 150 are eligible."""
    from concurrent.futures import ThreadPoolExecutor

    seen: set[str] = set()
    replayed: set[str] = {path.stem for path in REPLAY.glob("*.json")}
    pool = ThreadPoolExecutor(max_workers=max(1, replay_workers))
    inflight: set[str] = set()
    try:
        while True:
            _refresh_eligibility(seen)
            treated = _eligible_stems()
            history_done = (RQ3 / "history_done.json").exists()
            if len(treated) >= TREATED_MIN:
                for stem in treated:
                    if stem in replayed or stem in inflight:
                        continue
                    inflight.add(stem)
                    pool.submit(_replay_and_mark, stem, replayed, inflight)
            if history_done and not inflight:
                treated = _eligible_stems()
                if len(treated) < TREATED_MIN or treated <= replayed:
                    break
            time.sleep(15)
    finally:
        pool.shutdown(wait=True)
    treated = _eligible_stems()
    payload = {
        "treated": len(treated),
        "threshold": TREATED_MIN,
        "panel_started": len(treated) >= TREATED_MIN,
    }
    (RQ4 / "follow_done.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"follow done treated={len(treated)}", flush=True)


def _write_replay(record: dict) -> None:
    path = REPLAY / f"{file_stem(record['repository_id'], record['strategy'])}.json"
    if path.exists():
        return
    try:
        _write_json(path, replay_repo(record))
    except Exception as exc:
        _write_json(path, {
            "repository_id": record.get("repository_id"),
            "repository_full_name": record.get("repository_full_name"),
            "error": str(exc)[:500],
            "snapshots": [],
        })


def _replay_and_mark(stem: str, replayed: set[str], inflight: set[str]) -> None:
    try:
        path = ELIGIBILITY / f"{stem}.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("eligible") and not (REPLAY / f"{stem}.json").exists():
            _write_json(REPLAY / f"{stem}.json", replay_repo(record))
        replayed.add(stem)
    except Exception as exc:
        _write_json(REPLAY / f"{stem}.json", {"stem": stem, "error": str(exc)[:500], "snapshots": []})
        replayed.add(stem)
    finally:
        inflight.discard(stem)


def _refresh_eligibility(seen: set[str]) -> None:
    complete = {
        file_stem(row["repository_id"], row["strategy"])
        for row in history_status().values()
        if row.get("status") == "complete" and row.get("strategy") == "MavenCrawler"
    }
    for path in META_DIR.glob("*.json"):
        if path.stem in seen or path.stem not in complete:
            continue
        meta = json.loads(path.read_text(encoding="utf-8"))
        if meta.get("strategy") != "MavenCrawler":
            seen.add(path.stem)
            continue
        _write_json(ELIGIBILITY / path.name, eligibility_from_meta(meta))
        seen.add(path.stem)


def _eligible_stems() -> set[str]:
    found = set()
    for path in ELIGIBILITY.glob("*.json"):
        row = json.loads(path.read_text(encoding="utf-8"))
        if row.get("eligible"):
            found.add(path.stem)
    return found


def eligibility_from_meta(meta: dict) -> dict:
    adoption = parse_dt(meta.get("adoption_date") or "")
    first = parse_dt(meta.get("first_commit_date") or "")
    last = parse_dt(meta.get("last_commit_date") or "")
    reason = ""
    eligible = False
    if adoption is None:
        reason = "no_rule_commit"
    elif first is None or last is None:
        reason = "no_rule_commit"
    else:
        short_pre = first > add_months(adoption, -12)
        short_post = last < add_months(adoption, 12)
        if short_pre and short_post:
            reason = "short_pre_post"
        elif short_pre:
            reason = "short_pre"
        elif short_post:
            reason = "short_post"
        else:
            eligible = True
    cohort = "no_extend|with_extend" if meta.get("reason") == "kept" else "with_extend"
    return {
        "repository_id": meta.get("repository_id") or "",
        "repository_full_name": meta.get("repository_full_name") or "",
        "tool": "ArchUnit",
        "strategy": meta.get("strategy") or "MavenCrawler",
        "reason": meta.get("reason") or "",
        "cohort": cohort,
        "sample_index": meta.get("sample_index") or 0,
        "adoption_commit": meta.get("adoption_commit") or "",
        "adoption_date": meta.get("adoption_date") or "",
        "first_commit_date": meta.get("first_commit_date") or "",
        "last_commit_date": meta.get("last_commit_date") or "",
        "eligible": eligible,
        "ineligibility_reason": reason,
        "clone_dir": meta.get("clone_dir") or rel_clone(str(meta.get("repository_id")), meta.get("strategy") or "MavenCrawler"),
    }


def replay_repo(record: dict) -> dict:
    dest = clone_path(record["repository_id"], record["strategy"])
    meta_path = META_DIR / f"{file_stem(record['repository_id'], record['strategy'])}.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    adoption = parse_dt(record.get("adoption_date") or "")
    if adoption is None or not dest.exists():
        return {"error": "missing adoption date or clone", "snapshots": []}
    texts = []
    for file_row in meta.get("files") or []:
        text = _text_at(dest, file_row, adoption)
        if text:
            texts.append(text)
    mapping = _codebook()
    n_rules = 0
    n_family = 0
    checks: list[Check] = []
    for text in texts:
        rules, family = family_counts(text, mapping)
        n_rules += rules
        n_family += family
        checks.extend(translate(text))
    commits = _commit_index(dest)
    snapshots = []
    cached: dict[str, tuple[list[tuple[str, str]], str]] = {}
    for offset in range(-12, 13):
        target = add_months(adoption, offset)
        chosen = _commit_at(commits, target)
        if chosen is None:
            snapshots.append({"t": offset, "commit": "", "date": "", "violations": None, "error": "no commit at or before t"})
            continue
        moment, sha, date = chosen
        if sha not in cached:
            try:
                edges, error = _imports(dest, sha)
            except Exception as exc:
                edges, error = [], str(exc)[:300]
            cached[sha] = (edges, error)
        edges, error = cached[sha]
        violations = None if error else sum(check.violations(edges) for check in checks)
        snapshots.append({
            "t": offset,
            "commit": sha,
            "date": date,
            "violations": violations,
            "error": error,
        })
    series = {row["t"]: row["violations"] for row in snapshots if row["violations"] is not None}
    pre = [series[t] for t in range(-12, 0) if t in series]
    ratifier = series.get(-1) == 0
    reformer = series.get(0) == 0 and any(value > 0 for value in pre)
    known = -1 in series and 0 in series
    return {
        "repository_id": record["repository_id"],
        "repository_full_name": record["repository_full_name"],
        "adoption_commit": record.get("adoption_commit") or "",
        "adoption_date": record.get("adoption_date") or "",
        "n_rules": n_rules,
        "n_family": n_family,
        "n_evaluable": len(checks),
        "family_coverage": None if not n_rules else n_family / n_rules,
        "evaluable_coverage": None if not n_rules else len(checks) / n_rules,
        "ratifier": bool(ratifier) if known else None,
        "reformer": bool(reformer) if known else None,
        "snapshots": snapshots,
        "error": "",
    }


def aggregate() -> None:
    corpus = load_corpus()
    if not corpus:
        raise SystemExit("data/corpus.csv is missing")
    arch = [row for row in corpus if row.get("tool") == "ArchUnit"]
    panel = []
    metas_missing = []
    for row in arch:
        path = META_DIR / f"{file_stem(row['repository_id'], row['strategy'])}.json"
        if not path.exists():
            metas_missing.append(row["repository_full_name"])
            continue
        meta = json.loads(path.read_text(encoding="utf-8"))
        panel.append(eligibility_from_meta(meta))
    if metas_missing:
        raise SystemExit(f"missing meta for {len(metas_missing)} ArchUnit repos, e.g. {metas_missing[:3]}")
    write_csv(PANEL, panel, PANEL_FIELDS)
    treated = [row for row in panel if str(row.get("eligible")).lower() == "true" or row.get("eligible") is True]
    ran = len(treated) >= TREATED_MIN
    replays = []
    if ran:
        missing = [
            row for row in treated
            if not (REPLAY / f"{file_stem(row['repository_id'], row['strategy'])}.json").exists()
        ]
        if missing:
            from concurrent.futures import ThreadPoolExecutor, as_completed
            print(f"replay remaining {len(missing)}", flush=True)
            with ThreadPoolExecutor(max_workers=3) as pool:
                futures = {pool.submit(_write_replay, row): row for row in missing}
                for index, future in enumerate(as_completed(futures), start=1):
                    future.result()
                    if index % 10 == 0 or index == len(missing):
                        print(f"replay {index}/{len(missing)}", flush=True)
        for row in treated:
            path = REPLAY / f"{file_stem(row['repository_id'], row['strategy'])}.json"
            replays.append(json.loads(path.read_text(encoding="utf-8")))
    summary = _summarize(treated, replays, ran)
    summary["did"] = did_status(summary)
    _write_json(REPLAY_SUMMARY, summary)
    write_counts(RQ4 / "counts.csv", corpus, archunit_only=True)
    print(
        f"aggregate arch={len(panel)} treated={len(treated)} panel_ran={ran}",
        flush=True,
    )


def _summarize(treated: list[dict], replays: list[dict], ran: bool) -> dict:
    if not ran:
        return {
            "treated": len(treated),
            "threshold": TREATED_MIN,
            "panel_ran": False,
            "reason": f"treated {len(treated)} is below {TREATED_MIN}; panel stopped and DiD was not estimated",
        }
    known = [row for row in replays if row.get("ratifier") is not None and not row.get("error")]
    ratifier = [row for row in known if row.get("ratifier")]
    reformer = [row for row in known if row.get("reformer")]
    both = [row for row in known if row.get("ratifier") and row.get("reformer")]
    coverages = [row["family_coverage"] for row in replays if isinstance(row.get("family_coverage"), (int, float))]
    evaluable = [row["evaluable_coverage"] for row in replays if isinstance(row.get("evaluable_coverage"), (int, float))]
    return {
        "treated": len(treated),
        "threshold": TREATED_MIN,
        "panel_ran": True,
        "replayed": len(replays),
        "classified": len(known),
        "ratifier_n": len(ratifier),
        "reformer_n": len(reformer),
        "both_n": len(both),
        "ratifier_share": len(ratifier) / len(known) if known else None,
        "reformer_share": len(reformer) / len(known) if known else None,
        "mean_family_coverage": sum(coverages) / len(coverages) if coverages else None,
        "mean_evaluable_coverage": sum(evaluable) / len(evaluable) if evaluable else None,
        "reason": "source-level dependency and layering replay on kept clones",
    }


def did_status(summary: dict) -> dict:
    if not summary.get("panel_ran"):
        return {"ran": False, "reason": "panel stopped below the treated threshold; DiD was not estimated"}
    catalog = _find_catalog()
    if catalog is None:
        return {
            "ran": False,
            "reason": "Java control catalog (GHS/SEART) was not obtainable; DiD did not run. Ratify and reform are reported for the treated set.",
        }
    return {"ran": False, "reason": f"catalog found at {catalog} but no matched control panel was built in this run; DiD did not run"}


def _find_catalog() -> str | None:
    candidates = []
    external = RQ4.parent / "external"
    if external.exists():
        candidates.extend(external.glob("*"))
    candidates.extend(RQ4.glob("control*.csv"))
    candidates.extend(RQ4.glob("*seart*"))
    candidates.extend(RQ4.glob("*ghs*"))
    for path in candidates:
        if path.is_file() and path.stat().st_size > 0:
            return str(path)
    return None


def pilot() -> None:
    """Compile attempt on 20 ArchUnit clones. This is not the panel result."""
    corpus = [row for row in load_corpus() if row.get("tool") == "ArchUnit"]
    eligible = []
    if PANEL.exists():
        eligible = [row for row in csv_rows(PANEL) if str(row.get("eligible")).lower() == "true"]
    chosen = (eligible or corpus)[:20]
    rows = []
    for row in chosen:
        rows.append(_compile_one(row))
        print(f"pilot {row['repository_full_name']} {rows[-1]['status']}", flush=True)
    write_csv(
        RQ4 / "compile_pilot.csv",
        rows,
        ["repository_id", "repository_full_name", "status", "builder", "seconds", "error"],
    )
    succeeded = sum(1 for row in rows if row["status"] == "compiled")
    _write_json(RQ4 / "compile_pilot.json", {
        "n": len(rows),
        "compiled": succeeded,
        "share": succeeded / len(rows) if rows else None,
    })
    print(f"pilot compiled {succeeded}/{len(rows)}", flush=True)


def _compile_one(row: dict) -> dict:
    dest = clone_path(row["repository_id"], row.get("strategy") or "MavenCrawler")
    started = time.monotonic()
    if not dest.exists():
        return _pilot_row(row, "missing_clone", "", started, "clone directory missing")
    try:
        _run(["git", "--no-pager", "-C", str(dest), "checkout", "-f", "HEAD"], timeout=900)
    except Exception as exc:
        _restore_nocheckout(dest)
        return _pilot_row(row, "checkout_error", "", started, str(exc))
    builder, command = _build_command(dest)
    if not command:
        _restore_nocheckout(dest)
        return _pilot_row(row, "no_build_file", "", started, "")
    try:
        _run(command, timeout=480, cwd=dest)
        status, error = "compiled", ""
    except Exception as exc:
        status, error = "failed", str(exc)
    _restore_nocheckout(dest)
    return _pilot_row(row, status, builder, started, error)


def _restore_nocheckout(dest: Path) -> None:
    """Drop the pilot worktree and keep the git directory."""
    if not dest.exists():
        return
    for child in dest.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)


def _build_command(dest: Path) -> tuple[str, list[str] | None]:
    if (dest / "mvnw").exists():
        return "mvnw", ["bash", str(dest / "mvnw"), "-B", "-DskipTests", "test-compile"]
    if (dest / "pom.xml").exists() and shutil_which("mvn"):
        return "mvn", ["mvn", "-B", "-DskipTests", "test-compile"]
    if (dest / "gradlew").exists():
        return "gradlew", ["bash", str(dest / "gradlew"), "testClasses", "--no-daemon"]
    if list(dest.glob("*.gradle*")) and shutil_which("gradle"):
        return "gradle", ["gradle", "testClasses", "--no-daemon"]
    return "", None


def _pilot_row(row: dict, status: str, builder: str, started: float, error: str) -> dict:
    return {
        "repository_id": row["repository_id"],
        "repository_full_name": row["repository_full_name"],
        "status": status,
        "builder": builder,
        "seconds": round(time.monotonic() - started, 1),
        "error": error.replace("\n", " ")[:400],
    }


def _text_at(dest: Path, file_row: dict, adoption) -> str:
    chosen = None
    for commit in file_row.get("commits") or []:
        moment = parse_dt(commit.get("date") or "")
        if moment and moment <= adoption:
            chosen = commit
    if chosen is None:
        return ""
    path = chosen.get("path_at_commit") or file_row.get("path") or ""
    if not path:
        return ""
    proc = subprocess.run(
        ["git", "--no-pager", "-C", str(dest), "show", f"{chosen['commit']}:{path}"],
        capture_output=True,
        timeout=120,
        check=False,
        env=git_env(),
    )
    if proc.returncode != 0:
        return ""
    return proc.stdout.decode("utf-8", errors="replace")


def _commit_index(dest: Path) -> list[tuple]:
    text = _run(
        ["git", "--no-pager", "-C", str(dest), "log", "--format=%H%x1f%aI"],
        timeout=600,
    )
    rows = []
    for line in text.splitlines():
        sha, _, date = line.partition("\x1f")
        moment = parse_dt(date)
        if moment and sha:
            rows.append((moment, sha, date))
    rows.sort(key=lambda item: item[0])
    return rows


def _commit_at(commits: list[tuple], target):
    chosen = None
    for row in commits:
        if row[0] <= target:
            chosen = row
        else:
            break
    return chosen


def _imports(dest: Path, sha: str) -> tuple[list[tuple[str, str]], str]:
    command = [
        "git", "--no-pager", "-C", str(dest), "grep", "-I", "-n", "-E",
        r"^(import |package )", sha, "--", "*.java", "*.kt", "*.kts",
    ]
    proc = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        start_new_session=True,
        env=git_env(),
    )
    try:
        out, err = proc.communicate(timeout=300)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        return [], "git grep timeout"
    if proc.returncode not in (0, 1):
        return [], (err or "git grep failed").strip()[:300]
    edges, _internal = graph_from_grep(out.splitlines())
    return edges, ""


def _codebook() -> dict:
    payload = json.loads((RQ2 / "codebook_map.json").read_text(encoding="utf-8"))
    return payload.get("map") or {}


def _run(args: list[str], timeout: int, cwd: Path | None = None) -> str:
    proc = subprocess.Popen(
        args,
        cwd=cwd,
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
        raise TimeoutError(f"timeout {' '.join(args[:4])}")
    if proc.returncode != 0:
        detail = (err or out or "command failed").strip().replace("\n", " ")
        raise RuntimeError(detail[-500:])
    return out


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def csv_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def shutil_which(name: str) -> str | None:
    from shutil import which
    return which(name)


if __name__ == "__main__":
    main()
