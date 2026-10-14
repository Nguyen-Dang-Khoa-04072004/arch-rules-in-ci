from pathlib import Path
import json, os 
from typing import Iterator
import csv

def read_jsonl(path: str) -> Iterator[dict]:
    path_obj = Path(path)

    if not path_obj.exists():
        return iter([])  # Return an empty iterator if the file does not exist

    with path_obj.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line:  # Only yield non-empty lines
                yield json.loads(line)

def append_jsonl(path: str, rows: list[dict]) -> None:
    if not rows:
        return
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    with path_obj.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def append_csv(path: str, rows: list[dict], fieldnames: list[str]) -> None:
    if not rows:
        return
    path_obj = Path(path)
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    file_exists = path_obj.exists()

    with path_obj.open("a", encoding="utf-8", newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        if not file_exists:
            writer.writeheader()

        for row in rows:
            writer.writerow(row)
        f.flush()
        os.fsync(f.fileno())