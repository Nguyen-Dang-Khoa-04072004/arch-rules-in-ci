import configparser
import re
import tomllib


_TYPE_LINE = re.compile(r"(?m)^[ \t]*type\s*=\s*['\"]?([A-Za-z0-9_-]+)")
_IGNORE_LINE = re.compile(r"(?m)^[ \t]*ignore_imports\s*=\s*(.*)$")


def extract(text: str, path: str) -> list[dict]:
    if path.endswith(".toml") or "[tool.importlinter" in text or "tool.importlinter" in text:
        parsed = _from_toml(text)
        if _named(parsed):
            return parsed
    parsed = _from_ini(text)
    if _named(parsed):
        return parsed
    fragments = _from_type_lines(text)
    if fragments:
        return fragments
    if parsed:
        return parsed
    if "importlinter" in text.lower():
        return [{"construct": "unparsed", "exemption": False, "raw_text": text[:500].strip()}]
    return []


def _named(rows: list[dict]) -> bool:
    return any(row["construct"] != "unparsed" for row in rows)


def _from_toml(text: str) -> list[dict]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return [{"construct": "unparsed", "exemption": False, "raw_text": text[:500].strip()}]
    tool = (data.get("tool") or {}).get("importlinter") or {}
    if not tool:
        return []
    contracts = tool.get("contracts") or []
    if not isinstance(contracts, list) or not contracts:
        return [{"construct": "unparsed", "exemption": False, "raw_text": text[:500].strip()}]
    rows = []
    for contract in contracts:
        if not isinstance(contract, dict):
            rows.append({"construct": "unparsed", "exemption": False, "raw_text": str(contract)[:500]})
            continue
        ignored = contract.get("ignore_imports") or []
        rows.append({
            "construct": str(contract.get("type") or "unparsed"),
            "exemption": bool(ignored),
            "raw_text": _snippet(contract),
        })
    return rows


def _from_ini(text: str) -> list[dict]:
    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read_string(text)
    except configparser.Error:
        return []
    rows = []
    for section in parser.sections():
        if not _is_contract(section) or not parser.has_option(section, "type"):
            continue
        body = "\n".join(f"{key} = {value}" for key, value in parser.items(section))
        rows.append({
            "construct": parser.get(section, "type", fallback="unparsed"),
            "exemption": _nonzero_ignore(parser.get(section, "ignore_imports", fallback="")),
            "raw_text": body[:500],
        })
    return rows


def _is_contract(section: str) -> bool:
    name = section.lower()
    if name == "importlinter":
        return False
    return name.startswith(("importlinter:contract:", "importlinter:", "contract:"))


def _from_type_lines(text: str) -> list[dict]:
    matches = list(_TYPE_LINE.finditer(text))
    if not matches:
        return []
    rows = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        start = max(0, match.start() - 200)
        block = text[start:end]
        rows.append({
            "construct": match.group(1),
            "exemption": _nonzero_ignore_block(block),
            "raw_text": block[:500].strip(),
        })
    return rows


def _nonzero_ignore(value: str) -> bool:
    text = value.strip().strip("'\"")
    return bool(text) and text not in {"[]", '""', "''"}


def _nonzero_ignore_block(text: str) -> bool:
    match = _IGNORE_LINE.search(text)
    return bool(match) and _nonzero_ignore(match.group(1))


def _snippet(contract: dict) -> str:
    parts = [f"{key} = {contract[key]}" for key in ("name", "type", "ignore_imports") if key in contract]
    return "\n".join(parts)[:500]
