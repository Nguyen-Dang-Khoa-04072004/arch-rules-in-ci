from abc import ABC, abstractmethod
import csv
import json
import threading
from pathlib import Path

from github.client import GithubClient
from utils.utils import append_csv, append_jsonl


PATH_PREFIXES = "abcdefghijklmnopqrstuvwxyz0123456789"
HIT_FIELDS = [
    "repository_id",
    "repository_full_name",
    "path",
    "sha",
    "strategy",
]
DEFAULT_SIZE_BOUNDS = [0, 200, 500, 1000, 2000, 5000, 20000]
MAX_OPEN_SIZE = 2_000_000

_checkpoint_lock = threading.Lock()


def initial_size_ranges(bounds: list[int]) -> list[tuple[int, int | None]]:
    edges = sorted({int(bound) for bound in bounds})
    if not edges or edges[0] != 0:
        edges = [0, *edges]
    if len(edges) == 1:
        return [(edges[0], None)]

    ranges: list[tuple[int, int | None]] = []
    last = edges[-1]
    for left, right in zip(edges, edges[1:]):
        lo = left if left == 0 else left + 1
        hi = right - 1 if right == last else right
        if lo <= hi:
            ranges.append((lo, hi))
    ranges.append((last, None))
    return ranges


def size_clause(base: str, lo: int, hi: int | None) -> str:
    if hi is None:
        return f"{base} size:>={lo}"
    return f"{base} size:{lo}..{hi}"


class CrawlerStrategy(ABC):
    def __init__(self, cfg: dict, gh_client: GithubClient):
        self.cfg = cfg
        self.gh_client = gh_client

    @abstractmethod
    def crawl(self):
        pass

    def crawl_queries(self, queries: list[str], strategy: str) -> None:
        repos_path = (self.cfg.get("output") or {}).get("repos")
        if not repos_path:
            raise ValueError("Repository output path is missing from configuration.")

        search = self.cfg.get("search") or {}
        self._per_page = min(int(search.get("per_page", 100)), 100)
        self._max_results = int(search.get("max_results", 1000))
        self._size_bounds = list(search.get("size_bounds") or DEFAULT_SIZE_BOUNDS)
        self._repos_path = repos_path
        self._checkpoint_path = str(
            Path(repos_path).parent / "checkpoints" / "crawl_shards.jsonl"
        )
        self._strategy = strategy
        self._bases = list(queries)
        self._seen, self._initial_repos = _load_seen(repos_path, strategy)
        self._done = _load_done(self._checkpoint_path)
        self._new_hits = 0
        self._new_repos: set[str] = set()

        print(
            f"{strategy}: {len(self._seen)} existing hits, "
            f"{len(self._initial_repos)} existing repos",
            flush=True,
        )
        for query in queries:
            self._visit_base(query)
        self._print_summary()

    def _visit_base(self, query: str) -> None:
        self._visit(query, lambda: self._split_base(query))

    def _split_base(self, query: str) -> None:
        for lo, hi in initial_size_ranges(self._size_bounds):
            self._visit_size(query, lo, hi)

    def _visit_size(self, base: str, lo: int, hi: int | None) -> None:
        query = size_clause(base, lo, hi)
        self._visit(query, lambda: self._bisect_or_path(base, lo, hi, query))

    def _bisect_or_path(
        self,
        base: str,
        lo: int,
        hi: int | None,
        query: str,
    ) -> None:
        if hi is None:
            self._split_open(base, lo)
            return
        if lo >= hi:
            self._split_paths(query)
            return
        mid = (lo + hi) // 2
        self._visit_size(base, lo, mid)
        if mid < hi:
            self._visit_size(base, mid + 1, hi)

    def _split_open(self, base: str, lo: int) -> None:
        if lo >= MAX_OPEN_SIZE:
            self._split_paths(size_clause(base, lo, None))
            return
        width = max(lo, 1)
        hi = min(lo + width - 1, MAX_OPEN_SIZE)
        self._visit_size(base, lo, hi)
        self._visit_size(base, hi + 1, None)

    def _split_paths(self, sized_query: str) -> None:
        for prefix in PATH_PREFIXES:
            self._visit_path(f"{sized_query} path:{prefix}")

    def _visit(self, query: str, on_split) -> None:
        status = self._done.get(query)
        if status in ("paginated", "capped"):
            print(f"{self._strategy}: skip {status} {query}", flush=True)
            return
        if status == "split":
            on_split()
            return

        response = self._fetch_page(query, 1)
        if response is None:
            return

        total = int(response.get("total_count") or 0)
        if total >= self._max_results:
            print(
                f"{self._strategy}: split total={total} {query}",
                flush=True,
            )
            self._checkpoint(query, total, 0, "split")
            on_split()
            return

        new_rows = self._paginate(query, response, total)
        print(
            f"{self._strategy}: paginated total={total} new_rows={new_rows} {query}",
            flush=True,
        )
        self._checkpoint(query, total, new_rows, "paginated")

    def _visit_path(self, query: str) -> None:
        status = self._done.get(query)
        if status in ("paginated", "capped"):
            print(f"{self._strategy}: skip {status} {query}", flush=True)
            return

        response = self._fetch_page(query, 1)
        if response is None:
            return

        total = int(response.get("total_count") or 0)
        if total >= self._max_results:
            new_rows = self._paginate(query, response, total)
            print(
                f"{self._strategy}: capped total={total} new_rows={new_rows} {query}",
                flush=True,
            )
            self._checkpoint(query, total, new_rows, "capped")
            return

        new_rows = self._paginate(query, response, total)
        print(
            f"{self._strategy}: paginated total={total} new_rows={new_rows} {query}",
            flush=True,
        )
        self._checkpoint(query, total, new_rows, "paginated")

    def _fetch_page(self, query: str, page: int) -> dict | None:
        try:
            return self.gh_client.search_code(query, page, self._per_page)
        except ValueError as exc:
            print(f"{self._strategy}: invalid query, skip: {exc}", flush=True)
            return None

    def _paginate(self, query: str, first: dict, total: int) -> int:
        new_rows = self._store_items(first.get("items") or [])
        per_page = self._per_page
        first_items = first.get("items") or []
        if len(first_items) < per_page:
            return new_rows

        incomplete = bool(first.get("incomplete_results"))
        max_page = max(self._max_results // per_page, 1)
        page = 2
        while page <= max_page:
            response = self._fetch_page(query, page)
            if response is None:
                break
            items = response.get("items") or []
            new_rows += self._store_items(items)
            incomplete = incomplete or bool(response.get("incomplete_results"))
            if len(items) < per_page:
                break
            if not incomplete and total and page * per_page >= total:
                break
            page += 1
        return new_rows

    def _store_items(self, items: list[dict]) -> int:
        rows = []
        strategy = self._strategy
        for item in items:
            repo = item.get("repository") or {}
            repo_id = str(repo.get("id") or "")
            path = item.get("path") or ""
            if not repo_id or not path:
                continue
            key = (repo_id, path, strategy)
            if key in self._seen:
                continue
            self._seen.add(key)
            rows.append({
                "repository_id": repo_id,
                "repository_full_name": repo.get("full_name") or "",
                "path": path,
                "sha": item.get("sha") or "",
                "strategy": strategy,
            })
            if repo_id not in self._initial_repos:
                self._new_repos.add(repo_id)

        if not rows:
            return 0

        append_csv(self._repos_path, rows, HIT_FIELDS)
        self._new_hits += len(rows)
        return len(rows)

    def _checkpoint(
        self,
        query: str,
        total_count: int,
        new_rows: int,
        status: str,
    ) -> None:
        row = {
            "query": query,
            "total_count": total_count,
            "new_rows": new_rows,
            "status": status,
        }
        with _checkpoint_lock:
            append_jsonl(self._checkpoint_path, [row])
        self._done[query] = status

    def _print_summary(self) -> None:
        print(
            f"{self._strategy}: new_hits={self._new_hits} "
            f"new_repos={len(self._new_repos)}",
            flush=True,
        )
        latest: dict[str, dict] = {}
        with _checkpoint_lock:
            rows = list(_iter_checkpoint(self._checkpoint_path))
        for row in rows:
            query = row.get("query") or ""
            if query:
                latest[query] = row
        capped = [
            row for query, row in latest.items()
            if row.get("status") == "capped" and _belongs_to(query, self._bases)
        ]
        if not capped:
            print(f"{self._strategy}: no shards still at the cap", flush=True)
            return
        for row in capped:
            print(
                f"{self._strategy}: capped total={row.get('total_count')} "
                f"{row.get('query')}",
                flush=True,
            )


class Crawler(ABC):
    def __init__(self, crawlerStrategy: CrawlerStrategy):
        self.crawlerStrategy = crawlerStrategy

    def crawl(self):
        print("Crawling processing is starting...", flush=True)
        self.crawlerStrategy.crawl()
        print("Crawling processing is done.", flush=True)


def _belongs_to(query: str, bases: list[str]) -> bool:
    return any(query == base or query.startswith(base + " ") for base in bases)


def _load_seen(path: str, strategy: str) -> tuple[set[tuple[str, str, str]], set[str]]:
    seen: set[tuple[str, str, str]] = set()
    repos: set[str] = set()
    for row in _read_csv(path):
        if (row.get("strategy") or "") != strategy:
            continue
        repo_id = str(row.get("repository_id") or "")
        file_path = row.get("path") or ""
        if not repo_id or not file_path:
            continue
        seen.add((repo_id, file_path, strategy))
        repos.add(repo_id)
    return seen, repos


def _load_done(path: str) -> dict[str, str]:
    done: dict[str, str] = {}
    with _checkpoint_lock:
        rows = list(_iter_checkpoint(path))
    for row in rows:
        query = row.get("query") or ""
        if query:
            done[query] = row.get("status") or "paginated"
    return done


def _iter_checkpoint(path: str):
    path_obj = Path(path)
    if not path_obj.exists():
        return
    with path_obj.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _read_csv(path: str) -> list[dict]:
    path_obj = Path(path)
    if not path_obj.exists():
        return []
    with path_obj.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
