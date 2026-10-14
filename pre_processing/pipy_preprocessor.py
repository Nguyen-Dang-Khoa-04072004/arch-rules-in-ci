from github.client import GithubClient
from pre_processing.funnel import run_funnel
from pre_processing.preprocessor import PreprocessorStrategy


class PypiPreprocessor(PreprocessorStrategy):
    def __init__(self, cfg: dict, gh_client: GithubClient):
        self.cfg = cfg
        self.gh_client = gh_client

    def preprocess(self):
        print("Preprocessing PyPI ecosystem...")
        run_funnel(self.cfg, self.gh_client, "PypiCrawler")
        
