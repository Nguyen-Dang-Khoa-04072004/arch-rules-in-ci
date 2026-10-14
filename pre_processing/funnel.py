from datetime import datetime
from pathlib import Path
import csv

from github.client import GithubClient
from utils.utils import append_csv


TEMPLATE_MARKERS = (
    "pom.xml.ejs",
    "TechnicalStructureTest.java",
    "archunit-examples",
    "spring-modulith",
)

def run_funnel(cfg: dict, gh_client: GithubClient, strategy: str) -> None:
    funnel_cfg = cfg.get("funnel", {})
    output = cfg.get("output", {})

    raw_path = output.get("repos")
    funnel_path = output.get("funnel")

    min_activity_days = int(funnel_cfg.get("min_activity_days", 183))
    min_contributors = int(funnel_cfg.get("min_contributors", 2))
    gh_client.repo_min_interval = float(funnel_cfg.get("min_interval_sec", 1.0))
    gh_client._repo_limiter.min_interval = gh_client.repo_min_interval

    if not raw_path or not funnel_path:
        raise ValueError("Funnel output paths are missing from configuration.")

    repos = _dedupe_strategy(_read_csv(raw_path), strategy)
    done = _done_keys(_read_csv(funnel_path))
    pending = [
        repo
        for repo in repos
        if (repo["repository_id"], strategy) not in done
    ]

    print(
        f"Funnel {strategy}: {len(repos)} repos after dedupe, "
        f"{len(pending)} to classify"
    )

    fieldnames = ["repository_id", "repository_full_name", "strategy", "reason"]
    for repo in pending:
        reason = _classify(
            gh_client,
            repo,
            min_activity_days=min_activity_days,
            min_contributors=min_contributors,
        )
        print(f"{repo['repository_full_name']}: {reason}")
        append_csv(funnel_path, [{
            "repository_id": repo["repository_id"],
            "repository_full_name": repo["repository_full_name"],
            "strategy": strategy,
            "reason": reason,
        }], fieldnames)


def _read_csv(path: str) -> list[dict]:
    path_obj = Path(path)
    if not path_obj.exists():
        return []

    with path_obj.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _dedupe_strategy(rows: list[dict], strategy: str) -> list[dict]:
    repos: dict[str, dict] = {}
    seen_hits: set[tuple[str, str]] = set()

    for row in rows:
        if row.get("strategy") != strategy:
            continue

        repository_id = row.get("repository_id") or ""
        path = row.get("path") or ""
        hit = (repository_id, path)

        if not repository_id or hit in seen_hits:
            continue

        seen_hits.add(hit)
        repo = repos.get(repository_id)

        if repo is None:
            repos[repository_id] = {
                "repository_id": repository_id,
                "repository_full_name": row.get("repository_full_name") or "",
                "paths": [path],
            }
        else:
            repo["paths"].append(path)

    return sorted(
        repos.values(),
        key=lambda repo: _repo_sort_key(repo["repository_id"]),
    )


def _done_keys(rows: list[dict]) -> set[tuple[str, str]]:
    return {
        (row.get("repository_id") or "", row.get("strategy") or "")
        for row in rows
        if row.get("repository_id") and row.get("strategy")
    }


def _repo_sort_key(repository_id: str) -> tuple[int, int | str]:
    try:
        return (0, int(repository_id))
    except (TypeError, ValueError):
        return (1, repository_id)


def _classify(
    gh_client: GithubClient,
    repo: dict,
    min_activity_days: int,
    min_contributors: int,
) -> str:
    if _is_template(repo["paths"]):
        return "template"

    full_name = repo["repository_full_name"]
    if not full_name:
        return "missing"

    info = gh_client.get_repo(full_name)
    if info is None:
        return "missing"
    if info.get("fork"):
        return "fork"
    if info.get("archived"):
        return "archived"
    if _is_short_lived(info, min_activity_days):
        return "short_lived"

    contributors = gh_client.list_contributors(
        full_name,
        per_page=min_contributors,
    )
    if not isinstance(contributors, list):
        return "missing"
    if len(contributors) < min_contributors:
        return "contributors"

    tags = gh_client.list_tags(full_name, per_page=1)
    if not isinstance(tags, list):
        return "missing"
    if not tags:
        return "no_release"

    return "kept"


def _is_template(paths: list[str]) -> bool:
    return any(
        marker in path
        for path in paths
        for marker in TEMPLATE_MARKERS
    )


def _is_short_lived(info: dict, min_activity_days: int) -> bool:
    created = _parse_github_time(info.get("created_at"))
    pushed = _parse_github_time(info.get("pushed_at"))

    if created is None or pushed is None:
        return True

    return (pushed - created).days < min_activity_days


def _parse_github_time(value: str | None) -> datetime | None:
    if not value:
        return None

    return datetime.fromisoformat(value.replace("Z", "+00:00"))