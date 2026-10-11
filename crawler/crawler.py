from abc import ABC, abstractmethod

class CrawlerStrategy(ABC):
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