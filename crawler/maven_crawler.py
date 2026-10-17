from crawler.crawler import CrawlerStrategy


class MavenCrawler(CrawlerStrategy):
    def crawl(self):
        print("Crawling Maven ecosystem...", flush=True)
        queries = (self.cfg.get("queries") or {}).get("maven") or []
        if not queries:
            raise ValueError("Configuration is not provided for MavenCrawler.")
        self.crawl_queries(queries, "MavenCrawler")
