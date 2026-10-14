import requests
import subprocess
from datetime import datetime
import threading
import time
import os
from dotenv import load_dotenv

load_dotenv()

class RateLimiter:
    def __init__(self, min_interval: float):
        self.min_interval = min_interval
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self) -> None:
        with self._lock:
            wait = self.min_interval - (time.time() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.time()

class GithubClient:

    GITHUB_API_URL = "https://api.github.com"

    def _get_token(self, token: str = None):
    
        if not token:
            print("Info: GitHub token not provided.")
            try:
                print("Info: Attempting to retrieve token using 'gh auth token' command...")
                token = subprocess.check_output(
                    ["gh", "auth", "token"],
                    stderr=subprocess.DEVNULL
                ).decode("utf-8").strip()
            
            except Exception as e:
                print(e)
                print("Error: GitHub token not provided and 'gh auth token' command failed. Please provide a valid GitHub token.")

        if not token:
            print("Attempting to retrieve token from environment variables.")
            token = os.getenv("GITHUB_TOKEN")

        if not token:
            raise ValueError("Error: GitHub token not provided. Please provide a valid GitHub token.")
        return token

    def _ping(self) -> None:
        response = requests.get(f"{self.GITHUB_API_URL}/rate_limit", headers={
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
        })

        if response.status_code != 200:
            raise RuntimeError(f"Failed to ping GitHub API. Status code: {response.status_code}, response: {response.text[:300]}")

        print("Successfully connected to GitHub API. Rate limit info:", response.json())

    def __init__(self, token: str = None,
                       min_interval: float = 1.0,
                       search_limiter: RateLimiter | None = None,
                       repo_limiter: RateLimiter | None = None):

        self.token = self._get_token(token)
        self.session = requests.Session()

        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
        })

        self.min_interval = min_interval
        self.repo_min_interval = 1.0
        self._search_limiter = search_limiter or RateLimiter(min_interval)
        self._repo_limiter = repo_limiter or RateLimiter(self.repo_min_interval)

        #self._ping()

    def search_code(self, query: str,
                              page: int = 1,
                              per_page: int = 100)-> dict:
    
            for attempt in range(8):
                self._search_limiter.wait()

                try:
                    response = self.session.get(
                        f"{self.GITHUB_API_URL}/search/code",
                        params={
                            "q": query,
                            "page": page,
                            "per_page": per_page
                        },
                        timeout=60
                    )
                except requests.RequestException as e:
                    print(f"Request failed: {e}. Attempt {attempt + 1}/8")
                    time.sleep(2 ** attempt)
                    continue
    
                if response.status_code == 200:
                    return response.json()
    
                if response.status_code == 422:
                    raise ValueError(f"invalid query {query!r}: {response.text[:300]}")
                if response.status_code in (403, 429):
                    delay = self._rate_limit_delay(response, attempt)
                    print("rate limited (%d), sleeping %.0fs", response.status_code, delay)
                    time.sleep(delay)
                    continue
                if response.status_code >= 500:
                    time.sleep(10 * 2 ** attempt)
                    continue
    
                response.raise_for_status()
    
            raise RuntimeError(f"Failed to get a successful response after 8 attempts. Last status code: {response.status_code}, response: {response.text[:300]}")

    def _get(self, path: str, params: dict | None = None):
        for attempt in range(8):
            self._repo_limiter.wait()

            try:
                response = self.session.get(
                    f"{self.GITHUB_API_URL}{path}",
                    params=params,
                    timeout=60,
                )
            except requests.RequestException as e:
                print(f"Request failed: {e}. Attempt {attempt + 1}/8")
                time.sleep(2 ** attempt)
                continue

            if response.status_code == 200:
                return response.json()
            if response.status_code == 204:
                return []
            if response.status_code == 404:
                return None
            if response.status_code in (403, 429):
                delay = self._rate_limit_delay(response, attempt)
                print(f"rate limited ({response.status_code}), sleeping {delay:.0f}s")
                time.sleep(delay)
                continue
            if response.status_code >= 500:
                time.sleep(10 * 2 ** attempt)
                continue

            response.raise_for_status()

        raise RuntimeError(f"GET {path} failed after 8 attempts")

    def get_repo(self, full_name: str) -> dict | None:
        return self._get(f"/repos/{full_name}")

    def list_contributors(self, full_name: str, per_page: int = 2) -> list | None:
        return self._get(
            f"/repos/{full_name}/contributors",
            params={"per_page": per_page, "anon": "true"},
        )

    def list_tags(self, full_name: str, per_page: int = 1) -> list | None:
        return self._get(
            f"/repos/{full_name}/tags",
            params={"per_page": per_page},
        )

    @staticmethod
    def _rate_limit_delay(r, attempt: int) -> float:
        if "Retry-After" in r.headers:
            return int(r.headers["Retry-After"]) + 1
        if r.headers.get("X-RateLimit-Remaining") == "0":
            return max(int(r.headers["X-RateLimit-Reset"]) - time.time(), 0) + 2
        return min(60 * 2 ** attempt, 900)