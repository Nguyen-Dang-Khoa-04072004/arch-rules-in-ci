from crawler.crawler import CrawlerStrategy


class PypiCrawler(CrawlerStrategy):
    def crawl(self):
        print("Crawling Pypi ecosystem", flush=True)
        queries = (self.cfg.get("queries") or {}).get("pypi") or []
        if not queries:
            raise ValueError("Configuration is not provided for PypiCrawler.")
        self.crawl_queries(queries, "PypiCrawler")
