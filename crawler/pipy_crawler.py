from crawler.crawler import CrawlerStrategy


class PypiCrawler(CrawlerStrategy):
    def crawl(self):
        print("Crawling PyPI ecosystem...")