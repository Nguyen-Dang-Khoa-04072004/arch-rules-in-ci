from crawler.crawler import CrawlerStrategy
from utils.utils import append_csv

class NpmCrawler(CrawlerStrategy):
    def crawl(self):
        print("Crawling NPM ecosystem...")

        if not self.cfg or 'queries' not in self.cfg or 'npm' not in self.cfg['queries']:
            raise ValueError("Configuration is not provided for NpmCrawler.")

        try:
            queries = self.cfg.get('queries', {}).get('npm', [])

            seen_records = set()

            for query in queries:
                print(f"Executing query: {query}")
                # Here you would implement the actual crawling logic using the query
                # For example, you might call self.gh_client.search_repositories(query)
                # and process the results accordingly.

                for record in self._process_query(query):
                    record['strategy'] = 'NpmCrawler'

                    # Check for duplicates based on repository_id, path, and sha
                    hit_key = (record['repository_id'], record['path'], record['sha'])
                    if hit_key in seen_records:
                        print(f"Duplicate record found: {record}. Skipping.")
                        continue
                    
                    append_csv(
                        path=self.cfg.get('output', {}).get('repos'),
                        rows=[record],
                        fieldnames=["repository_id", "repository_full_name", "path", "sha", "strategy"]
                    )

        except (ValueError, AttributeError, TypeError) as e:
            print(f"Invalid configuration format: {e}")