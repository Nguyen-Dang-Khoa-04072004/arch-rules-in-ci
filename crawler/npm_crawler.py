from crawler.crawler import CrawlerStrategy


class NpmCrawler(CrawlerStrategy):
    def crawl(self):
        print("Crawling NPM ecosystem...")