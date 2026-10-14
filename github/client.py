import requests
import subprocess
from datetime import datetime
import time

class GithubClient:

    GITHUB_API_URL = "https://api.github.com"

    def _get_token(self, token: str = None):

        if not token:
            try:
                token = subprocess.check_output(
                    ["gh", "auth", "token"],
                    stderr=subprocess.DEVNULL
                ).decode("utf-8").strip()
            
            except subprocess.CalledProcessError:
                raise RuntimeError("Failed to retrieve GitHub token. Please ensure you are logged in with the GitHub CLI.")

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
                       min_interval: float = 1.0):

        self.token = self._get_token(token)
        self.session = requests.Session()

        self.session.headers.update({
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2026-03-10",
        })

        self.min_interval = min_interval
        self._last_request_time = 0.0

        #self._ping()

    def search_code(self, query: str,
                              page: int = 1,
                              per_page: int = 100)-> dict:
    
            for attempt in range(8):
                wait = self.min_interval - (datetime.now().timestamp() - self._last_request_time)
    
                if wait > 0:
                    time.sleep(wait)
    
                self._last_request_time = datetime.now().timestamp()
    
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


    @staticmethod
    def _rate_limit_delay(r, attempt: int) -> float:
        if "Retry-After" in r.headers:
            return int(r.headers["Retry-After"]) + 1
        if r.headers.get("X-RateLimit-Remaining") == "0":
            return max(int(r.headers["X-RateLimit-Reset"]) - time.time(), 0) + 2
        return min(60 * 2 ** attempt, 900)