
import base64
import csv
import re
from pathlib import Path
from typing import Any

import yaml
from github.client import GithubClient


TOOL_PATTERNS = {
    "import-linter": re.compile(
        r"\b(?:lint-imports|import-linter)\b",
        re.IGNORECASE,
    ),
    "dependency-cruiser": re.compile(
        r"\b(?:depcruise|dependency-cruiser)\b",
        re.IGNORECASE,
    ),
    "ArchUnit": re.compile(
        r"(?:\bmvnw?\s+(?:[\w.-]+\s+)*(?:test|verify|install|package)\b"
        r"|\bgradlew?\s+(?:[\w.-]+\s+)*(?:test|check|build)\b)",
        re.IGNORECASE,
    ),
}

CSV_PATH = Path("./data/funnel_pilot.csv")


def detect_ci(
    client: GithubClient,
    repository_full_name: str,
) -> dict[str, Any]:
    """Scan YAML files recursively under .github/ for architecture tools."""

    base_url = (
        f"{client.GITHUB_API_URL}/repos/{repository_full_name}"
    )

    response = client.session.get(base_url, timeout=30)
    response.raise_for_status()
    branch = response.json()["default_branch"]

    response = client.session.get(
        f"{base_url}/branches/{branch}",
        timeout=30,
    )
    response.raise_for_status()
    commit_sha = response.json()["commit"]["sha"]

    response = client.session.get(
        f"{base_url}/git/trees/{commit_sha}",
        params={"recursive": "1"},
        timeout=30,
    )
    response.raise_for_status()
    tree_data = response.json()

    if tree_data.get("truncated"):
        raise RuntimeError(
            f"Repository tree is truncated: {repository_full_name}"
        )

    yaml_files = [
        item
        for item in tree_data.get("tree", [])
        if item.get("type") == "blob"
        and item.get("path", "").startswith(".github/")
        and item["path"].lower().endswith((".yml", ".yaml"))
    ]

    detected_tools = {tool: [] for tool in TOOL_PATTERNS}

    for file_info in yaml_files:
        path = file_info["path"]

        response = client.session.get(
            f"{base_url}/contents/{path}",
            params={"ref": branch},
            timeout=30,
        )
        response.raise_for_status()

        content = base64.b64decode(
            response.json()["content"]
        ).decode("utf-8")

        try:
            document = yaml.safe_load(content) or {}
        except yaml.YAMLError:
            continue

        commands = []

        def collect_commands(value: Any) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    if key == "run" and isinstance(child, str):
                        commands.append(child)
                    else:
                        collect_commands(child)
            elif isinstance(value, list):
                for item in value:
                    collect_commands(item)

        collect_commands(document)

        for tool, pattern in TOOL_PATTERNS.items():
            matches = [
                command.strip()
                for command in commands
                if pattern.search(command)
            ]

            if matches:
                detected_tools[tool].append({
                    "file": path,
                    "commands": matches,
                })

    return {
        "repository": repository_full_name,
        "branch": branch,
        "file_count": len(yaml_files),
        "detected_tools": detected_tools,
        "ci": any(detected_tools.values()),
    }


def check_ci(token: str | None = None) -> list[dict[str, Any]]:
    """Check eligible repositories and update the CSV ci column."""

    # Read all rows, preserving existing columns.
    with CSV_PATH.open("r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])

        if "repository_full_name" not in fieldnames:
            raise ValueError("CSV is missing repository_full_name column")
        if "reason" not in fieldnames:
            raise ValueError("CSV is missing reason column")

        if "ci" not in fieldnames:
            fieldnames.append("ci")

        rows = list(reader)

    client = GithubClient(token=token)
    results = []

    for row in rows:
        # Only scan repositories marked "kept".
        if row.get("reason", "").strip().lower() != "kept":
            row["ci"] = "false"
            continue

        repository_full_name = row["repository_full_name"].strip()
        print(f"Scanning {repository_full_name} for CI tools...")
        try:
            result = detect_ci(client, repository_full_name)
            row["ci"] = str(result["ci"]).lower()
            results.append(result)

            print(
                f"{repository_full_name}: "
                f"ci={row['ci']}, "
                f"detected={list(result['detected_tools'].keys())}"
            )

        except (Exception) as exc:
            # Avoid falsely marking an API failure as ci=false.
            print(f"Error scanning {repository_full_name}: {exc}")
            row["ci"] = row.get("ci", "")

    # Write all rows back, retaining their original order and columns.
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return results



