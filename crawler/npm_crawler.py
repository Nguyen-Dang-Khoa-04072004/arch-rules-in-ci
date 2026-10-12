from crawler.crawler import CrawlerStrategy


class NpmCrawler(CrawlerStrategy):
    def crawl(self):
        print("Crawling NPM ecosystem...")

        if not self.cfg or 'queries' not in self.cfg or 'npm' not in self.cfg['queries']:
            raise ValueError("Configuration is not provided for NpmCrawler.")

        try:
            queries = self.cfg.get('queries', {}).get('npm', [])

            for query in queries:
                print(f"Executing query: {query}")
                # Here you would implement the actual crawling logic using the query
                # For example, you might call self.gh_client.search_repositories(query)
                # and process the results accordingly.

        except (ValueError, AttributeError, TypeError) as e:
            print(f"Invalid configuration format: {e}")