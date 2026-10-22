"""Reclassify the development fetch from stored raw_text.

The first 1000 kept+extended repos stay the development set. This script
does not crawl, does not overwrite constructs.jsonl, and does not run H2.1.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from parsers.archunit import classify_stored, extra_constants  # noqa: E402
from parsers.depcruise import extract as extract_depcruise  # noqa: E402
from parsers.importlinter import extract as extract_importlinter  # noqa: E402

OUT = ROOT / "data" / "RQ2"
SOURCE = OUT / "constructs.jsonl"

# High-level categories used to compare tools. None is a status, not a category:
# unparsed text, a custom condition with no stable definition, or an exemption
# marker. Exemption markers are metadata on the inner rule.
#
# Each value is (category, dependency subtype, subject tag).
# Subtype is allowed, forbidden, required, or conditional. Subject names the
# API a forbidden-dependency rule targets.
TAXONOMY = [
    "dependency",
    "layering",
    "cycle",
    "naming",
    "visibility",
    "annotation",
    "other",
]
DETAIL = {
    # Dependency. Aliases checked against rule text: import-linter `forbidden`
    # and dependency-cruiser `forbidden` name a from/to import constraint;
    # `allowed` and `required` are the same shape.
    "forbidden_dependency": ("dependency", "forbidden", ""),
    "forbidden": ("dependency", "forbidden", ""),
    "forbidden_import": ("dependency", "forbidden", ""),
    "allowed_dependency": ("dependency", "allowed", ""),
    "allowed": ("dependency", "allowed", ""),
    "required_dependency": ("dependency", "required", ""),
    "required": ("dependency", "required", ""),
    "allowlist": ("dependency", "allowed", ""),
    "protected": ("dependency", "allowed", ""),
    "domain_purity": ("dependency", "allowed", ""),
    "isolated_apps": ("dependency", "allowed", ""),
    "independence": ("dependency", "forbidden", ""),
    "no-cross-test-imports": ("dependency", "forbidden", ""),
    "slice_dependency": ("dependency", "forbidden", ""),
    "conditional": ("dependency", "conditional", ""),
    "plantuml": ("dependency", "allowed", "plantuml"),
    # General coding rules forbid use of a named API. The category is the
    # constraint; the subject is the target.
    "standard_streams": ("dependency", "forbidden", "standard_streams"),
    "java_util_logging": ("dependency", "forbidden", "java_util_logging"),
    "joda_time": ("dependency", "forbidden", "joda_time"),
    # Layering. import-linter `layers` is the same contract as a layer rule.
    "layering": ("layering", "", ""),
    "layers": ("layering", "", ""),
    # Cycles. `circular` is dependency-cruiser to.circular; acyclic_siblings
    # states that the package graph is acyclic.
    "cycle_freedom": ("cycle", "", ""),
    "circular": ("cycle", "", ""),
    "acyclic_siblings": ("cycle", "", ""),
    # Naming includes package and declaration-site stereotypes.
    "naming": ("naming", "", ""),
    "package_location": ("naming", "", ""),
    "declaration_site": ("naming", "", ""),
    "visibility": ("visibility", "", ""),
    "annotation": ("annotation", "", ""),
    # Defined constraints that do not overlap the six groups above.
    "inheritance": ("other", "", ""),
    "signature": ("other", "", ""),
    "element_count": ("other", "", ""),
    "field_injection": ("other", "", "field_injection"),
    "generic_exceptions": ("other", "", "generic_exceptions"),
    "custom_condition": (None, "", ""),
    "unparsed": (None, "", ""),
    "FreezingArchRule": (None, "", ""),
    "@ArchIgnore": (None, "", ""),
}
CATEGORY = {construct: spec[0] for construct, spec in DETAIL.items()}
# H2.1: dependency and layering rules.
STRUCTURAL = ["dependency", "layering"]


def _detail_record(construct: str) -> dict | None:
    category, subtype, subject = DETAIL[construct]
    if not category:
        return None
    return {"category": category, "subtype": subtype, "subject": subject}


def main() -> None:
    source = _read(SOURCE)
    classified = []
    file_constants: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in source:
        classified.extend(_reclassify(row, file_constants))
    unknown = sorted({row["construct"] for row in classified} - set(CATEGORY))
    if unknown:
        raise SystemExit(f"constructs missing from the map: {unknown}")
    _write_jsonl(OUT / "dev_classified.jsonl", classified)
    counts = Counter((row["strategy"], row["construct"]) for row in classified)
    with (OUT / "dev_construct_counts.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["strategy", "construct", "count"])
        for (strategy, construct), count in sorted(counts.items()):
            writer.writerow([strategy, construct, count])
    present = {row["construct"] for row in classified}
    mapping = {
        construct: _detail_record(construct)
        for construct in sorted(present)
        if construct in DETAIL
    }
    family = [name for name in STRUCTURAL if name in {row["category"] for row in mapping.values() if row}]
    (OUT / "codebook_map.json").write_text(
        json.dumps({"taxonomy": TAXONOMY, "structural_family": family, "map": mapping}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"rows {len(source)} -> {len(classified)}")
    print(f"wrote {OUT / 'dev_classified.jsonl'}")


def _reclassify(row: dict, file_constants: dict[tuple[str, str], set[str]]) -> list[dict]:
    if row["strategy"] == "MavenCrawler":
        return _maven(row, file_constants)
    if row["strategy"] == "PypiCrawler":
        return _importlinter(row)
    return _depcruise(row)


def _maven(row: dict, file_constants: dict[tuple[str, str], set[str]]) -> list[dict]:
    produced = classify_stored(row.get("raw_text") or "", row["construct"])
    key = (row["repository_id"], row["file"])
    seen = file_constants[key]
    rows = []
    for item in produced:
        if item["construct"] != "unparsed":
            seen.add(item["construct"])
        rows.append(_copy(row, item))
    for item in extra_constants(row.get("raw_text") or "", seen):
        rows.append(_copy(row, item))
    if any(item["construct"] != "unparsed" for item in rows):
        rows = [item for item in rows if item["construct"] != "unparsed"]
    return rows


def _importlinter(row: dict) -> list[dict]:
    found = extract_importlinter(row.get("raw_text") or "", row.get("file") or "")
    named = [item for item in found if item["construct"] != "unparsed"]
    if row["construct"] != "unparsed":
        # The stored flag was computed on the full contract. A 500-character
        # snippet can drop ignore_imports, so keep that flag.
        construct = named[0]["construct"] if named else row["construct"]
        return [_copy(row, {
            "construct": construct,
            "exemption": row["exemption"],
            "raw_text": row.get("raw_text") or "",
        })]
    if named:
        return [_copy(row, item) for item in named]
    return [_copy(row, {"construct": "unparsed", "exemption": False, "raw_text": row.get("raw_text") or ""})]


def _depcruise(row: dict) -> list[dict]:
    if row["construct"] != "unparsed":
        return [_copy(row, row)]
    found = extract_depcruise(row.get("raw_text") or "", row.get("file") or "")
    named = [item for item in found if item["construct"] != "unparsed"]
    if named:
        return [_copy(row, item) for item in named]
    return [_copy(row, {"construct": "unparsed", "exemption": False, "raw_text": row.get("raw_text") or ""})]


def _copy(row: dict, item: dict) -> dict:
    return {
        "sample_index": row["sample_index"],
        "repository_id": row["repository_id"],
        "repository_full_name": row["repository_full_name"],
        "strategy": row["strategy"],
        "reason": row["reason"],
        "file": row["file"],
        "construct": item["construct"],
        "exemption": bool(item["exemption"]),
        "raw_text": item.get("raw_text") or "",
        "dev": True,
    }


def _read(path: Path) -> list[dict]:
    """Keep the last copy of each stored row, matching analysis/rq2.py counts."""
    latest = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            identity = (
                row["repository_id"],
                row["strategy"],
                row["file"],
                row["construct"],
                row.get("raw_text") or "",
            )
            latest[identity] = row
    return list(latest.values())


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
