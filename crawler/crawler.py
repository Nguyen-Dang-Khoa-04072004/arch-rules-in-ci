from abc import ABC, abstractmethod
from github.client import GithubClient

class CrawlerStrategy(ABC):
    def __init__(self, cfg: dict, gh_client: GithubClient):
        self.cfg = cfg
        self.gh_client = gh_client

    @abstractmethod
    def crawl(self):
        pass

class Crawler(ABC):
    def __init__(self, crawlerStrategy: CrawlerStrategy):
        self.crawlerStrategy = crawlerStrategy

    def crawl(self):
        print(f"Crawling processing is starting...")
        self.crawlerStrategy.crawl()
        print(f"Crawling processing is done.")