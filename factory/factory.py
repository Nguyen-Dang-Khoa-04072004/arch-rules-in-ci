from pre_processing.preprocessor import *
from crawler.crawler import *
from crawler.maven_crawler import MavenCrawler
from crawler.npm_crawler import NpmCrawler
from crawler.pipy_crawler import PypiCrawler
from pre_processing.maven_preprocessor import MavenPreprocessor
from pre_processing.npm_preprocessor import NpmPreprocessor
from pre_processing.pipy_preprocessor import PypiPreprocessor
from const.ecosystem import Ecosystem
class PreprocessorFactory:
    @staticmethod
    def create_preprocessor(ecosystem : Ecosystem) -> Preprocessor:
        strategy = None
        if ecosystem == Ecosystem.MAVEN:
            strategy = MavenPreprocessor()
        elif ecosystem == Ecosystem.NPM:
            strategy = NpmPreprocessor()
        elif ecosystem == Ecosystem.PYPI:
            strategy = PypiPreprocessor()
        else:
            raise ValueError(f"Unsupported ecosystem: {ecosystem}")
        return Preprocessor(strategy)
    
class CrawlerFactory:
    @staticmethod
    def create_crawler(ecosystem : Ecosystem) -> Crawler:
        strategy = None
        if ecosystem == Ecosystem.MAVEN:
            strategy = MavenCrawler()
        elif ecosystem == Ecosystem.NPM:
            strategy = NpmCrawler()
        elif ecosystem == Ecosystem.PYPI:
            strategy = PypiCrawler()
        else:
            raise ValueError(f"Unsupported ecosystem: {ecosystem}")
        return Crawler(strategy)

