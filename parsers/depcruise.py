import json
import re

_KINDS = ("forbidden", "allowed", "required")


def extract(text: str, path: str) -> list[dict]:
    data = _load(text, path)
    if isinstance(data, dict):
        rows = _from_object(data)
        if rows:
            return rows
    return _from_source(text)


def _load(text: str, path: str):
    if path.endswith(".json"):
        try:
            return json.loads(_strip_comments(text))
        except json.JSONDecodeError:
            return None
    body = _strip_comments(text)
    match = re.search(r"(?:module\.exports|export default)\s*=\s*", body)
    if match:
        body = body[match.end():]
    body = body.strip().rstrip(";")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def _from_object(data: dict) -> list[dict]:
    rows = []
    for kind in _KINDS:
        rules = data.get(kind) or []
        if not isinstance(rules, list):
            continue
        for rule in rules:
            if not isinstance(rule, dict):
                rows.append({"construct": "unparsed", "exemption": False, "raw_text": str(rule)[:500]})
                continue
            target = rule.get("to") if isinstance(rule.get("to"), dict) else {}
            severity = str(rule.get("severity") or "")
            rows.append({
                "construct": "circular" if target.get("circular") else kind,
                "exemption": bool(rule.get("exception") or rule.get("exceptions")) or severity.lower() in {"ignore", "off", "info", "warn"},
                "raw_text": json.dumps(rule, ensure_ascii=False)[:500],
            })
    return rows


def _from_source(text: str) -> list[dict]:
    body = _strip_comments(text)
    if not re.search(r"\b(forbidden|allowed|required|circular)\b", body):
        return []
    names = re.findall(r"""['"]name['"]\s*:\s*['"]([^'"]+)['"]""", body)
    circular = bool(re.search(r"""['"]?circular['"]?\s*:\s*true""", body) or "no-circular" in names)
    rows = []
    if circular:
        rows.append({
            "construct": "circular",
            "exemption": bool(re.search(
                r"""['"]?severity['"]?\s*:\s*['"](?:ignore|off|info|warn)['"]""",
                body,
            )),
            "raw_text": _window(body, "circular" if "circular" in body else "no-circular"),
        })
    only_cycle = bool(names) and set(names) <= {"no-circular"}
    for kind in _KINDS:
        if only_cycle and kind == "forbidden" and circular:
            continue
        if re.search(rf"""['"]?{kind}['"]?\s*:""", body):
            rows.append({
                "construct": kind,
                "exemption": "exception" in body,
                "raw_text": _window(body, kind),
            })
    if rows:
        return rows
    return [{"construct": "unparsed", "exemption": False, "raw_text": text[:500].strip()}]


def _strip_comments(text: str) -> str:
    body = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"(^|\n)\s*//.*", r"\1", body)


def _window(text: str, token: str) -> str:
    index = text.find(token)
    if index < 0:
        return text[:500].strip()
    return text[max(0, index - 80): index + 420].strip()
