"""Source-level replay of ArchUnit dependency and layering rules.

Violations are internal import edges. A package pattern uses ArchUnit's
'..' and '*' wildcards. Rules outside that shape stay in the family
coverage denominator and out of the violation count.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import re
from collections import Counter
from dataclasses import dataclass, field

from parsers.archunit import extract as extract_archunit

_IMPORT = re.compile(r"(?m)^\s*import\s+(static\s+)?([^;\n]+)")
_PACKAGE = re.compile(r"(?m)^\s*package\s+([\w.]+)\s*;")
_STRINGS = re.compile(r'"([^"]*)"')


@dataclass
class Check:
    kind: str
    sources: list[str] = field(default_factory=list)
    targets: list[str] = field(default_factory=list)
    layers: dict[str, list[str]] = field(default_factory=dict)
    access: list[tuple[str, str, list[str]]] = field(default_factory=list)

    def violations(self, edges: list[tuple[str, str]]) -> int:
        if self.kind == "forbidden":
            return sum(1 for src, dst in edges if _any(self.sources, src) and _any(self.targets, dst))
        if self.kind == "allowed":
            count = 0
            for src, dst in edges:
                if _any(self.sources, src) and not _any(self.targets, dst):
                    count += 1
            return count
        if self.kind == "layered":
            return _layered_violations(self, edges)
        return 0


def family_counts(text: str, mapping: dict) -> tuple[int, int]:
    rows = extract_archunit(text or "")
    family = 0
    for row in rows:
        mapped = mapping.get(row.get("construct") or "")
        category = ""
        if isinstance(mapped, dict):
            category = mapped.get("category") or ""
        if category in {"dependency", "layering"}:
            family += 1
    return len(rows), family


def translate(text: str) -> list[Check]:
    checks: list[Check] = []
    for match in re.finditer(r"\blayeredArchitecture\s*\(", text or ""):
        statement = _until_semicolon(text, match.start())
        layered = _layered(statement)
        if layered is not None:
            checks.append(layered)
    for match in re.finditer(r"\bonionArchitecture\s*\(", text or ""):
        statement = _until_semicolon(text, match.start())
        onion = _onion(statement)
        if onion is not None:
            checks.append(onion)
    for match in re.finditer(r"\b(?:noClasses|classes)\s*\(", text or ""):
        statement = _until_semicolon(text, match.start())
        checks.extend(_dependency(statement))
    return checks


def graph_from_grep(lines: list[str]) -> tuple[list[tuple[str, str]], set[str]]:
    packages: dict[str, str] = {}
    imports: dict[str, list[str]] = {}
    for line in lines:
        parsed = _grep_line(line)
        if parsed is None:
            continue
        path, content = parsed
        package = _PACKAGE.search(content)
        if package:
            packages[path] = package.group(1)
            continue
        imported = _IMPORT.search(content)
        if not imported:
            continue
        imports.setdefault(path, []).append(_import_package(imported.group(2), bool(imported.group(1))))
    internal = set(packages.values())
    edges = []
    for path, destinations in imports.items():
        source = packages.get(path)
        if not source:
            continue
        for destination in destinations:
            if not destination or destination == source:
                continue
            if destination not in internal and not any(
                destination.startswith(name + ".") or name.startswith(destination + ".") for name in internal
            ):
                continue
            if destination not in internal:
                # Keep an edge only when the destination is a project package.
                continue
            edges.append((source, destination))
    return edges, internal


def _grep_line(line: str) -> tuple[str, str] | None:
    match = re.match(r"^[0-9a-f]+:(.*?):(\d+):(.*)$", line.rstrip("\n"))
    if not match:
        return None
    return match.group(1), match.group(3)


def _import_package(raw: str, static: bool) -> str:
    name = raw.strip().strip('"').strip("'")
    if name.endswith(".*"):
        return name[:-2]
    parts = [part for part in name.split(".") if part]
    if static and parts and (parts[-1][:1].islower() or parts[-1].isupper()):
        parts = parts[:-1]
    if parts and parts[-1][:1].isupper():
        parts = parts[:-1]
    return ".".join(parts)


def _dependency(statement: str) -> list[Check]:
    head, separator, tail = _split_should(statement)
    if not separator:
        return []
    sources = _packages_in(head) or [".."]
    if re.search(r"\bonlyDependOnClassesThat\b|\bonlyBeAccessed\b|\bonlyHaveDependentClassesThat\b", tail):
        targets = _packages_in(tail)
        if targets:
            return [Check("allowed", sources, targets)]
        return []
    if re.search(r"\bdependOnClassesThat\b|\baccessClassesThat\b", tail) and statement.lstrip().startswith("noClasses"):
        targets = _packages_in(tail)
        if targets:
            return [Check("forbidden", sources, targets)]
    if re.search(r"\bdependOnClassesThat\b", tail) and re.search(r"\bshouldNot\s*\(", statement):
        targets = _packages_in(tail)
        if targets:
            return [Check("forbidden", sources, targets)]
    return []


def _layered(statement: str) -> Check | None:
    layers: dict[str, list[str]] = {}
    for name, body in re.findall(r'\.layer\(\s*"([^"]+)"\s*\)\s*\.definedBy\s*\((.*?)\)', statement, re.S):
        patterns = _STRINGS.findall(body)
        if patterns:
            layers[name] = patterns
    access = []
    for name, kind, body in re.findall(
        r'\.whereLayer\(\s*"([^"]+)"\s*\)\s*\.(mayNotBeAccessedByAnyLayer|mayOnlyBeAccessedByLayers|mayOnlyAccessLayers|mayNotAccessAnyLayer)\s*\(([^)]*)\)',
        statement,
        re.S,
    ):
        access.append((name, kind, _STRINGS.findall(body)))
    if not layers or not access:
        return None
    return Check("layered", layers=layers, access=access)


def _onion(statement: str) -> Check | None:
    layers: dict[str, list[str]] = {}
    for kind, pattern in re.findall(
        r'\.(domainModels|domainServices|applicationServices)\(\s*"([^"]+)"\s*\)',
        statement,
    ):
        layers.setdefault(kind, []).append(pattern)
    for pattern in re.findall(r'\.adapter\(\s*"[^"]+"\s*,\s*"([^"]+)"\s*\)', statement):
        layers.setdefault("adapter", []).append(pattern)
    if "domainModels" not in layers:
        return None
    # Domain is accessed by the outer rings and accesses none of them.
    access = [("domainModels", "mayNotAccessAnyLayer", [])]
    if "domainServices" in layers:
        access.append(("domainServices", "mayOnlyAccessLayers", ["domainModels"]))
    if "applicationServices" in layers:
        access.append(("applicationServices", "mayOnlyAccessLayers", ["domainModels", "domainServices"]))
    if "adapter" in layers:
        access.append((
            "adapter",
            "mayOnlyAccessLayers",
            [name for name in ("domainModels", "domainServices", "applicationServices") if name in layers],
        ))
    return Check("layered", layers=layers, access=access)


def _layered_violations(check: Check, edges: list[tuple[str, str]]) -> int:
    owners = []
    for name, patterns in check.layers.items():
        for pattern in patterns:
            owners.append((name, pattern))
    count = 0
    for src, dst in edges:
        src_layers = {name for name, pattern in owners if package_matches(pattern, src)}
        dst_layers = {name for name, pattern in owners if package_matches(pattern, dst)}
        if not src_layers or not dst_layers:
            continue
        for src_layer in src_layers:
            for dst_layer in dst_layers:
                if src_layer == dst_layer:
                    continue
                if _blocked(check.access, src_layer, dst_layer):
                    count += 1
                    break
            else:
                continue
            break
    return count


def _blocked(access: list[tuple[str, str, list[str]]], src_layer: str, dst_layer: str) -> bool:
    for name, kind, allowed in access:
        if kind == "mayNotBeAccessedByAnyLayer" and name == dst_layer:
            return True
        if kind == "mayOnlyBeAccessedByLayers" and name == dst_layer and src_layer not in allowed:
            return True
        if kind == "mayNotAccessAnyLayer" and name == src_layer:
            return True
        if kind == "mayOnlyAccessLayers" and name == src_layer and dst_layer not in allowed:
            return True
    return False


def package_matches(pattern: str, package: str) -> bool:
    return re.search(package_regex(pattern), package) is not None


def package_regex(pattern: str) -> str:
    if pattern == "..":
        return r"^.*$"
    parts = ["^"]
    index = 0
    while index < len(pattern):
        if pattern.startswith("..", index):
            parts.append(r"(?:.*\.)?" if index == 0 else r"(?:\..*)?")
            index += 2
            continue
        char = pattern[index]
        if char == "*":
            parts.append(r"[^.]*")
        elif char == ".":
            parts.append(r"\.")
        else:
            parts.append(re.escape(char))
        index += 1
    parts.append("$")
    return "".join(parts)


def _any(patterns: list[str], package: str) -> bool:
    return any(package_matches(pattern, package) for pattern in patterns)


def _packages_in(text: str) -> list[str]:
    found = []
    for match in re.finditer(
        r"\b(?:resideInAPackage|resideInAnyPackage|resideOutsideOfPackage|byAnyPackage)\s*\(([^)]*)\)",
        text,
    ):
        found.extend(_STRINGS.findall(match.group(1)))
    return found


def _split_should(statement: str) -> tuple[str, str, str]:
    match = re.search(r"\.(?:shouldNot|should)\s*\(", statement)
    if not match:
        return statement, "", ""
    return statement[:match.start()], match.group(0), statement[match.end():]


def _until_semicolon(text: str, start: int) -> str:
    end = text.find(";", start)
    if end < 0 or end - start > 8000:
        end = min(len(text), start + 8000)
    return text[start:end]


def _self_check() -> None:
    assert package_matches("com.example..", "com.example")
    assert package_matches("com.example..", "com.example.foo")
    assert not package_matches("com.example..", "com.examplefoo")
    assert package_matches("..domain..", "com.acme.domain.model")
    assert package_matches("..domain..", "domain")
    assert not package_matches("..domain..", "domains")

    forbidden = translate(
        'noClasses().that().resideInAPackage("..domain..").should().dependOnClassesThat().resideInAPackage("..infra..");'
    )
    assert len(forbidden) == 1 and forbidden[0].kind == "forbidden"
    assert forbidden[0].violations([("com.domain", "com.infra")]) == 1
    assert forbidden[0].violations([("com.domain", "com.domain")]) == 0

    allowed = translate(
        'classes().that().resideInAPackage("..ui..").should().onlyDependOnClassesThat().resideInAnyPackage("..ui..", "java..");'
    )
    assert allowed[0].kind == "allowed"
    assert allowed[0].violations([("com.ui", "com.service")]) == 1
    assert allowed[0].violations([("com.ui", "com.ui.internal")]) == 0

    layered = translate(
        'layeredArchitecture()'
        '.layer("UI").definedBy("..ui..")'
        '.layer("Domain").definedBy("..domain..")'
        '.whereLayer("Domain").mayNotBeAccessedByAnyLayer()'
        '.whereLayer("UI").mayOnlyAccessLayers("Domain");'
    )
    assert layered and layered[0].kind == "layered"
    assert layered[0].violations([("com.ui", "com.domain")]) == 1
    assert layered[0].violations([("com.domain", "com.domain.model")]) == 0
    print("sourcegraph self-check ok")


if __name__ == "__main__":
    _self_check()
