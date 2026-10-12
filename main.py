from const.ecosystem import Ecosystem
from factory.factory import CrawlerFactory, PreprocessorFactory
from github.client import GithubClient
import yaml
from pathlib import Path

def main():
    print("Setup GH Client...")
    gh_client = GithubClient()

    cfg = yaml.safe_load(Path("cfg/discover.yaml").read_text())
    print("Configuration loaded:", cfg)

    print("Architecture Rules in CI/CD Pipeline")
    for ecosystem in [Ecosystem.MAVEN, Ecosystem.NPM, Ecosystem.PYPI]:
        crawler = CrawlerFactory.create_crawler(ecosystem, cfg, gh_client)
        preprocessor = PreprocessorFactory.create_preprocessor(ecosystem)
        print(f"\nProcessing {ecosystem.value.upper()} ecosystem:")
        crawler.crawl()
        preprocessor.preprocess()
if __name__ == "__main__":
    main()
