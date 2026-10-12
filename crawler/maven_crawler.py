from crawler.crawler import CrawlerStrategy

class MavenCrawler(CrawlerStrategy):
    def crawl(self):
        # Implement the logic to crawl Maven packages
        print("Crawling Maven ecosystem...")

        if not self.cfg or 'queries' not in self.cfg or 'maven' not in self.cfg['queries']:
            raise ValueError("Configuration is not provided for MavenCrawler.")

        try:
            queries = self.cfg.get('queries', {}).get('maven', [])

            for query in queries:
                print(f"Executing query: {query}")
                # Here you would implement the actual crawling logic using the query
                # For example, you might call self.gh_client.search_repositories(query)
                # and process the results accordingly.

        except (ValueError, AttributeError, TypeError) as e:
            print(f"Invalid configuration format: {e}")