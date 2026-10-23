"""Classify one rule-file revision as add, tighten, loosen, exempt, disable, or restructure.

Exempt and disable follow the mechanisms already used by the parsers:
FreezingArchRule, @ArchIgnore, ignore_imports, exceptions, a severity drop,
and a rule that is commented out or deleted.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import re

from parsers.archunit import extract as extract_archunit
from parsers.depcruise import extract as extract_depcruise
from parsers.importlinter import extract as extract_importlinter

PRIORITY = ("disable", "exempt", "loosen", "tighten", "add", "restructure")
_SNIPPET = 8000


def parse_rules(strategy: str, path: str, text: str) -> list[dict]:
    if not (text or "").strip():
        return []
    if strategy == "MavenCrawler":
        return extract_archunit(text)
    if strategy == "PypiCrawler":
        return extract_importlinter(text, path)
    return extract_depcruise(text, path)


def introduces_archunit_rule(text: str) -> bool:
    rows = extract_archunit(text or "")
    if any(row.get("construct") != "unparsed" for row in rows):
        return True
    lowered = (text or "").lower()
    return bool(rows) and "archunit" in lowered


def classify_edit(strategy: str, path: str, before: str, after: str) -> dict:
    before = before or ""
    after = after or ""
    classes: set[str] = set()
    reasons: list[str] = []
    if _norm(before) == _norm(after):
        classes.add("restructure")
        reasons.append("unchanged_text")
        return _result(classes, reasons, before, after, False)

    before_rows = parse_rules(strategy, path, before)
    after_rows = parse_rules(strategy, path, after)
    if not before.strip() and after.strip():
        classes.add("add")
        reasons.append("empty_before")
    if before.strip() and not after.strip():
        classes.add("disable")
        reasons.append("empty_after")

    if _commented_out(before, after):
        classes.add("disable")
        reasons.append("commented_out")

    before_signals = _signals(before)
    after_signals = _signals(after)
    if after_signals["archignore"] > before_signals["archignore"]:
        classes.add("disable")
        reasons.append("archignore_added")
    if after_signals["freeze"] > before_signals["freeze"]:
        classes.add("exempt")
        reasons.append("freeze_added")
    if after_signals["ignore_imports"] > before_signals["ignore_imports"]:
        classes.add("exempt")
        reasons.append("ignore_imports_added")
    if after_signals["exceptions"] > before_signals["exceptions"]:
        classes.add("exempt")
        reasons.append("exceptions_added")
    if after_signals["severity_off"] > before_signals["severity_off"]:
        classes.add("disable")
        reasons.append("severity_off")
    elif after_signals["severity_soft"] > before_signals["severity_soft"]:
        classes.add("exempt")
        reasons.append("severity_down")

    before_names = _names(before_rows)
    after_names = _names(after_rows)
    if after_names - before_names:
        classes.add("add")
        reasons.append("rules_added")
    if before_names - after_names and after.strip():
        classes.add("disable")
        reasons.append("rules_removed")

    direction = _direction(before_signals, after_signals)
    if direction == "loosen":
        classes.add("loosen")
        reasons.append("constraint_loosened")
    elif direction == "tighten":
        classes.add("tighten")
        reasons.append("constraint_tightened")

    if not classes:
        classes.add("restructure")
        reasons.append("text_changed")
    elif "add" in classes and classes <= {"add", "restructure"} and before.strip() and before_names == after_names:
        classes.discard("add")
        classes.add("restructure")

    introduced = strategy == "MavenCrawler" and introduces_archunit_rule(after) and not introduces_archunit_rule(before)
    return _result(classes, reasons, before, after, introduced)


def snippet(text: str, limit: int = _SNIPPET) -> str:
    if len(text) <= limit:
        return text
    markers = (
        "noClasses",
        "layeredArchitecture",
        "onionArchitecture",
        "hexagonalArchitecture",
        "FreezingArchRule",
        "@ArchIgnore",
        "ignore_imports",
        "[importlinter",
        "forbidden",
        "dependency-cruiser",
        '"forbidden"',
    )
    for marker in markers:
        index = text.find(marker)
        if index >= 0:
            start = max(0, index - 400)
            return text[start:start + limit]
    return text[:limit]


def _result(classes: set[str], reasons: list[str], before: str, after: str, introduced: bool) -> dict:
    ordered = [name for name in PRIORITY if name in classes]
    return {
        "edit_class": ordered[0],
        "classes": ordered,
        "reasons": reasons,
        "introduces_rule": introduced,
        "text_before": snippet(before),
        "text_after": snippet(after),
    }


def _names(rows: list[dict]) -> set[str]:
    return {row.get("construct") or "unparsed" for row in rows if row.get("construct")}


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _signals(text: str) -> dict:
    code, comments = _split_comments(text)
    severities = [item.lower() for item in re.findall(r"""severity['"]?\s*[:=]\s*['"]([A-Za-z]+)['"]""", text)]
    allow = re.findall(r'"(?:\.\.[^"]+|[^"]*\.\.[^"]*)"', text)
    return {
        "archignore": len(re.findall(r"@ArchIgnore\b", text)),
        "freeze": len(re.findall(r"FreezingArchRule|\.freeze\s*\(", text)),
        "ignore_imports": _ignore_weight(text),
        "exceptions": _exception_weight(text),
        "severity_off": sum(1 for item in severities if item in {"off", "ignore"}),
        "severity_soft": sum(1 for item in severities if item in {"warn", "info"}),
        "commented_rules": _rule_markers(comments),
        "active_rules": _rule_markers(code),
        "allow": tuple(sorted(allow)),
        "should_not": len(re.findall(r"\bshouldNot\s*\(", text)),
        "no_classes": len(re.findall(r"\bnoClasses\s*\(", text)),
        "only_depend": len(re.findall(r"\bonlyDependOn", text)),
    }


def _direction(before: dict, after: dict) -> str:
    loosen = 0
    tighten = 0
    if len(after["allow"]) > len(before["allow"]):
        loosen += 1
    elif len(after["allow"]) < len(before["allow"]):
        tighten += 1
    if after["should_not"] < before["should_not"]:
        loosen += 1
    elif after["should_not"] > before["should_not"]:
        tighten += 1
    if after["no_classes"] < before["no_classes"]:
        loosen += 1
    elif after["no_classes"] > before["no_classes"]:
        tighten += 1
    if after["only_depend"] < before["only_depend"]:
        loosen += 1
    elif after["only_depend"] > before["only_depend"]:
        tighten += 1
    if loosen and tighten:
        return ""
    if loosen:
        return "loosen"
    if tighten:
        return "tighten"
    return ""


def _commented_out(before: str, after: str) -> bool:
    before_signals = _signals(before)
    after_signals = _signals(after)
    return (
        after_signals["commented_rules"] > before_signals["commented_rules"]
        and after_signals["active_rules"] < before_signals["active_rules"]
    )


def _rule_markers(text: str) -> int:
    return len(re.findall(
        r"\b(?:noClasses|classes|layeredArchitecture|onionArchitecture|hexagonalArchitecture|slices)\s*\(|"
        r"\bignore_imports\b|\btype\s*=",
        text,
    ))


def _ignore_weight(text: str) -> int:
    weight = 0
    for match in re.finditer(r"ignore_imports\s*[:=]\s*(.+)", text):
        body = match.group(1)
        weight += max(1, len(re.findall(r"[A-Za-z0-9_.*]+", body)))
    return weight


def _exception_weight(text: str) -> int:
    weight = len(re.findall(r"\bexceptions?\b", text))
    weight += len(re.findall(r"\bpathNot\b", text))
    return weight


def _split_comments(text: str) -> tuple[str, str]:
    code: list[str] = []
    comments: list[str] = []
    i = 0
    length = len(text)
    while i < length:
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            end = length if end < 0 else end + 2
            comments.append(text[i:end])
            i = end
            continue
        if text.startswith("//", i) or text.startswith("#", i):
            end = text.find("\n", i)
            end = length if end < 0 else end
            comments.append(text[i:end])
            i = end
            continue
        if text[i] in {'"', "'"}:
            quote = text[i]
            j = i + 1
            while j < length and text[j] != quote:
                if text[j] == "\\":
                    j += 2
                    continue
                j += 1
            code.append(text[i:j + 1])
            i = j + 1
            continue
        code.append(text[i])
        i += 1
    return "".join(code), "\n".join(comments)


def _self_check() -> None:
    added = classify_edit(
        "MavenCrawler",
        "A.java",
        "",
        'noClasses().that().resideInAPackage("..a..").should().dependOnClassesThat().resideInAPackage("..b..");',
    )
    assert added["edit_class"] == "add", added
    assert added["introduces_rule"] is True

    frozen = classify_edit(
        "MavenCrawler",
        "A.java",
        'noClasses().should().dependOnClassesThat().resideInAPackage("a");',
        'FreezingArchRule.freeze(noClasses().should().dependOnClassesThat().resideInAPackage("a"));',
    )
    assert frozen["edit_class"] == "exempt", frozen

    ignored = classify_edit(
        "MavenCrawler",
        "A.java",
        '@ArchTest\nstatic final ArchRule rule = noClasses().should().dependOnClassesThat().resideInAPackage("a");',
        '@ArchIgnore\n@ArchTest\nstatic final ArchRule rule = noClasses().should().dependOnClassesThat().resideInAPackage("a");',
    )
    assert ignored["edit_class"] == "disable", ignored

    deleted = classify_edit("MavenCrawler", "A.java", "noClasses().should().dependOnClassesThat().resideInAPackage(\"a\");", "")
    assert deleted["edit_class"] == "disable", deleted

    commented = classify_edit(
        "MavenCrawler",
        "A.java",
        'noClasses().should().dependOnClassesThat().resideInAPackage("a");',
        '// noClasses().should().dependOnClassesThat().resideInAPackage("a");',
    )
    assert commented["edit_class"] == "disable", commented

    ignore_imports = classify_edit(
        "PypiCrawler",
        ".importlinter",
        "[importlinter:contract:one]\ntype = forbidden\nsource_modules = a\nforbidden_modules = b\n",
        "[importlinter:contract:one]\ntype = forbidden\nsource_modules = a\nforbidden_modules = b\nignore_imports = a -> b\n",
    )
    assert "exempt" in ignore_imports["classes"], ignore_imports

    severity = classify_edit(
        "NpmCrawler",
        ".dependency-cruiser.js",
        '{ "forbidden": [{ "name": "a", "severity": "error", "from": {}, "to": {} }] }',
        '{ "forbidden": [{ "name": "a", "severity": "off", "from": {}, "to": {} }] }',
    )
    assert severity["edit_class"] == "disable", severity

    tightened = classify_edit(
        "MavenCrawler",
        "A.java",
        'classes().that().resideInAPackage("..a..").should().onlyDependOnClassesThat().resideInAnyPackage("..a..", "..b..");',
        'classes().that().resideInAPackage("..a..").should().onlyDependOnClassesThat().resideInAnyPackage("..a..");',
    )
    assert tightened["edit_class"] == "tighten", tightened
    print("editclass self-check ok")


if __name__ == "__main__":
    _self_check()
