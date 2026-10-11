from const.ecosystem import Ecosystem
from factory.factory import CrawlerFactory, PreprocessorFactory
def main():
    print("Architecture Rules in CI/CD Pipeline")
    for ecosystem in [Ecosystem.MAVEN, Ecosystem.NPM, Ecosystem.PYPI]:
        crawler = CrawlerFactory.create_crawler(ecosystem)
        preprocessor = PreprocessorFactory.create_preprocessor(ecosystem)
        print(f"\nProcessing {ecosystem.value.upper()} ecosystem:")
        crawler.crawl()
        preprocessor.preprocess()
if __name__ == "__main__":
    main()
