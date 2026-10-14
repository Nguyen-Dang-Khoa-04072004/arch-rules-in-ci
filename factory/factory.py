from pre_processing.preprocessor import *
from crawler.crawler import *
from crawler.maven_crawler import MavenCrawler
from crawler.npm_crawler import NpmCrawler
from crawler.pipy_crawler import PypiCrawler
from pre_processing.maven_preprocessor import MavenPreprocessor
from pre_processing.npm_preprocessor import NpmPreprocessor
from pre_processing.pipy_preprocessor import PypiPreprocessor
from const.ecosystem import Ecosystem
from github.client import GithubClient

class PreprocessorFactory:
    @staticmethod
    def create_preprocessor(ecosystem : Ecosystem, cfg: dict, gh_client: GithubClient) -> Preprocessor:
        strategy = None
        if ecosystem == Ecosystem.MAVEN:
            strategy = MavenPreprocessor(cfg, gh_client)
        elif ecosystem == Ecosystem.NPM:
            strategy = NpmPreprocessor(cfg, gh_client)
        elif ecosystem == Ecosystem.PYPI:
            strategy = PypiPreprocessor(cfg, gh_client)
        else:
            raise ValueError(f"Unsupported ecosystem: {ecosystem}")
        return Preprocessor(strategy)
    
class CrawlerFactory:
    @staticmethod
    def create_crawler(ecosystem : Ecosystem, cfg: dict, gh_client: GithubClient) -> Crawler:
        strategy = None
        if ecosystem == Ecosystem.MAVEN:
            strategy = MavenCrawler(cfg, gh_client)
        elif ecosystem == Ecosystem.NPM:
            strategy = NpmCrawler(cfg, gh_client)
        elif ecosystem == Ecosystem.PYPI:
            strategy = PypiCrawler(cfg, gh_client)
        else:
            raise ValueError(f"Unsupported ecosystem: {ecosystem}")
        return Crawler(strategy)

