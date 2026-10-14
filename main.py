from concurrent.futures import ThreadPoolExecutor, as_completed

from const.ecosystem import Ecosystem
from factory.factory import CrawlerFactory, PreprocessorFactory
from github.client import GithubClient, RateLimiter
import yaml
from pathlib import Path
import argparse
from pre_processing.ci import check_ci

def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--crawlers",
        action="store_true",
        help="Run crawlers for all ecosystems",
    )

    parser.add_argument(
        "--preprocess",
        action="store_true",
        help="Run repository funnel",
    )

    return parser.parse_args()

def _process_ecosystem(ecosystem, cfg, args, search_limiter, repo_limiter):
    gh_client = GithubClient(
        min_interval=cfg["search"]["min_interval_sec"],
        search_limiter=search_limiter,
        repo_limiter=repo_limiter,
    )
    crawler = CrawlerFactory.create_crawler(ecosystem, cfg, gh_client)
    preprocessor = PreprocessorFactory.create_preprocessor(ecosystem, cfg, gh_client)
    print(f"\nProcessing {ecosystem.value.upper()} ecosystem:")

    if args.crawlers:
        crawler.crawl()

    if args.preprocess:
        preprocessor.preprocess()

def crawl_and_preprocess():

    args = parse_args()

    cfg = yaml.safe_load(Path("cfg/config.yaml").read_text())
    print("Configuration loaded:", cfg)

    search_limiter = RateLimiter(cfg["search"]["min_interval_sec"])
    repo_limiter = RateLimiter(cfg.get("funnel", {}).get("min_interval_sec", 1.0))
    ecosystems = [Ecosystem.MAVEN, Ecosystem.NPM, Ecosystem.PYPI]

    print("Architecture Rules in CI/CD Pipeline")
    with ThreadPoolExecutor(max_workers=len(ecosystems)) as pool:
        futures = [
            pool.submit(
                _process_ecosystem,
                ecosystem,
                cfg,
                args,
                search_limiter,
                repo_limiter,
            )
            for ecosystem in ecosystems
        ]
        for future in as_completed(futures):
            future.result()

if __name__ == "__main__":
    # crawl_and_preprocess()
    check_ci()
