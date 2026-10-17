from crawler.crawler import CrawlerStrategy


class NpmCrawler(CrawlerStrategy):
    def crawl(self):
        print("Crawling NPM ecosystem...", flush=True)
        queries = (self.cfg.get("queries") or {}).get("npm") or []
        if not queries:
            raise ValueError("Configuration is not provided for NpmCrawler.")
        self.crawl_queries(queries, "NpmCrawler")
