from abc import ABC, abstractmethod
from github.client import GithubClient

class CrawlerStrategy(ABC):
    def __init__(self, cfg: dict, gh_client: GithubClient):
        self.cfg = cfg
        self.gh_client = gh_client

    @abstractmethod
    def crawl(self):
        pass

    def _process_query(self, query):
        current_page = 1
        total_counts = None
        current_offset = 0
        per_page = min(self.cfg.get("search", {}).get("per_page", 100), 100)
        max_page = 1000 // per_page

        while current_page <= max_page:
            if total_counts is not None and current_offset >= total_counts:
                break

            responses = self.gh_client.search_code(
                query,
                current_page,
                self.cfg.get("search", {}).get("per_page", 100)
            )

            total_counts = responses.get("total_count", 0)
            items = responses.get("items", [])

            for item in items:
                yield {
                    "repository_id": item.get("repository", {}).get("id"),
                    "repository_full_name": item.get("repository", {}).get("full_name"),
                    "path": item.get("path"),
                    "sha": item.get("sha")
                }

                current_offset += 1

            if len(items) < per_page:
                break

            current_page += 1

        yield from []


class Crawler(ABC):
    def __init__(self, crawlerStrategy: CrawlerStrategy):
        self.crawlerStrategy = crawlerStrategy

    def crawl(self):
        print(f"Crawling processing is starting...")
        self.crawlerStrategy.crawl()
        print(f"Crawling processing is done.")