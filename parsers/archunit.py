import re

_ENTRY = re.compile(
    r"layeredArchitecture\s*\("
    r"|onionArchitecture\s*\("
    r"|hexagonalArchitecture\s*\("
    r"|slices\s*\("
    r"|FreezingArchRule"
    r"|@ArchIgnore"
    r"|\b(?:noClasses|classes|noMethods|methods|noFields|fields|noConstructors|constructors)\s*\(",
    re.MULTILINE,
)
_EXEMPT = {"FreezingArchRule", "@ArchIgnore"}
_LAYERING_ENTRY = {"layeredArchitecture", "onionArchitecture", "hexagonalArchitecture"}
_SHOULD_METHOD = re.compile(
    r"\.(?P<kind>andShould|orShould|shouldNot|should)\s*\(\s*\)\s*\.\s*(?P<method>[A-Za-z_][A-Za-z0-9_]*)\s*\(",
    re.MULTILINE,
)
_SHOULD_ARG = re.compile(
    r"\.(?P<kind>andShould|orShould|shouldNot|should)\s*\(\s*(?P<arg>[A-Za-z_][A-Za-z0-9_\.]*)",
    re.MULTILINE,
)
_ANNOTATION = {
    "beAnnotatedWith",
    "notBeAnnotatedWith",
    "beMetaAnnotatedWith",
    "notBeMetaAnnotatedWith",
}
_VISIBILITY = {
    "bePublic",
    "bePrivate",
    "beProtected",
    "bePackagePrivate",
    "notBePublic",
    "notBePrivate",
    "notBeProtected",
    "notBePackagePrivate",
    "haveModifier",
    "notHaveModifier",
    "beStatic",
    "notBeStatic",
    "beFinal",
    "notBeFinal",
    "haveOnlyFinalFields",
    "haveOnlyPrivateConstructors",
}
_NEXT_TEST = re.compile(r"(?m)^\s*@(?:ArchTest|Test|ParameterizedTest|ArchIgnore)\b")
_PACKAGE = {
    "resideInAPackage",
    "resideInAnyPackage",
    "resideOutsideOfPackage",
    "resideOutsideOfPackages",
}
_INHERITANCE = {
    "implement",
    "notImplement",
    "beAssignableTo",
    "notBeAssignableTo",
    "beAssignableFrom",
    "notBeAssignableFrom",
    "beInterfaces",
    "notBeInterfaces",
    "beEnums",
    "notBeEnums",
    "beRecords",
    "notBeRecords",
    "beAnnotations",
    "notBeAnnotations",
    "beTopLevelClasses",
    "notBeTopLevelClasses",
    "beNestedClasses",
    "notBeNestedClasses",
    "beMemberClasses",
    "notBeMemberClasses",
    "beInnerClasses",
    "notBeInnerClasses",
    "beAnonymousClasses",
    "notBeAnonymousClasses",
    "beLocalClasses",
    "notBeLocalClasses",
}
_SIGNATURE = {
    "haveRawReturnType",
    "notHaveRawReturnType",
    "haveRawParameterTypes",
    "notHaveRawParameterTypes",
    "haveRawType",
    "notHaveRawType",
    "declareThrowableOfType",
    "notDeclareThrowableOfType",
}
# Longest token first so a specific constant wins over a shorter alias.
_CONSTANTS = (
    ("NO_CLASSES_SHOULD_ACCESS_STANDARD_STREAMS", "standard_streams"),
    ("ACCESS_STANDARD_STREAMS", "standard_streams"),
    ("NO_CLASSES_SHOULD_THROW_GENERIC_EXCEPTIONS", "generic_exceptions"),
    ("THROW_GENERIC_EXCEPTIONS", "generic_exceptions"),
    ("NO_CLASSES_SHOULD_USE_JAVA_UTIL_LOGGING", "java_util_logging"),
    ("USE_JAVA_UTIL_LOGGING", "java_util_logging"),
    ("NO_CLASSES_SHOULD_USE_JODATIME", "joda_time"),
    ("USE_JODATIME", "joda_time"),
    ("NO_CLASSES_SHOULD_USE_FIELD_INJECTION", "field_injection"),
    ("USE_FIELD_INJECTION", "field_injection"),
    ("NO_CLASSES_SHOULD_DEPEND_UPPER_PACKAGES", "forbidden_dependency"),
)
_SKIP_ARG = {"new", "not", "never", "described"}


def extract(text: str) -> list[dict]:
    matches = list(_ENTRY.finditer(text))
    rows = []
    consumed = []
    for index, match in enumerate(matches):
        start = match.start()
        if any(span_start <= start < span_end for span_start, span_end in consumed):
            continue
        end = _span_end(text, start, matches, index)
        consumed.append((start, end))
        keyword = _keyword(match.group(0))
        snippet = text[start:end].strip()
        if keyword in _EXEMPT:
            rows.append({
                "construct": keyword,
                "exemption": True,
                "raw_text": snippet[:700],
            })
            continue
        rows.extend(classify_statement(snippet, keyword))
    emitted = {row["construct"] for row in rows}
    for construct, token in _uncovered_constants(text, consumed):
        if construct in emitted:
            continue
        emitted.add(construct)
        rows.append({
            "construct": construct,
            "exemption": False,
            "raw_text": _window(text, token),
        })
    real = [row for row in rows if row["construct"] != "unparsed"]
    if real:
        return real
    if rows and ("com.tngtech.archunit" in text or "org.archunit" in text):
        return [{"construct": "unparsed", "exemption": False, "raw_text": text[:500].strip()}]
    if "com.tngtech.archunit" in text or "org.archunit" in text:
        return [{"construct": "unparsed", "exemption": False, "raw_text": text[:500].strip()}]
    return []


def classify_stored(raw_text: str, original_construct: str) -> list[dict]:
    """Classify one already-stored snippet without scanning a following rule."""
    if original_construct in _EXEMPT:
        return [{
            "construct": original_construct,
            "exemption": True,
            "raw_text": (raw_text or "")[:700].strip(),
        }]
    text = raw_text or ""
    if original_construct == "unparsed":
        return _window_rows(text)
    return classify_statement(primary_statement(text), original_construct)


def classify_statement(statement: str, entry: str) -> list[dict]:
    statement = (statement or "").strip()
    found: list[str] = []
    seen: set[str] = set()

    def add(construct: str | None) -> None:
        if construct and construct not in seen:
            seen.add(construct)
            found.append(construct)

    for kind, method in _SHOULD_METHOD.findall(statement):
        add(_family(method, entry, kind == "shouldNot") or "custom_condition")
    for kind, arg in _SHOULD_ARG.findall(statement):
        constant = _constant_construct(arg)
        if constant:
            add(constant)
            continue
        method = arg.split(".")[-1]
        if method in _SKIP_ARG or not _plausible(method):
            add("custom_condition")
            continue
        add(_family(method, entry, kind == "shouldNot") or "custom_condition")
    if not found:
        for construct in _constants_in(statement):
            add(construct)
    if not found and (
        entry in _LAYERING_ENTRY or re.search(r"\b(?:onion|hexagonal|layered)Architecture\b", statement)
    ):
        add("layering")
    if not found:
        add("unparsed")
    exemption = "layering" in found and bool(re.search(r"\.ignoreDependency\s*\(", statement))
    raw = statement[:700]
    return [{
        "construct": construct,
        "exemption": exemption and construct == "layering",
        "raw_text": raw,
    } for construct in found]


def primary_statement(text: str) -> str:
    matches = list(_ENTRY.finditer(text))
    end = matches[1].start() if len(matches) >= 2 else len(text)
    newline = text.find("\n")
    if newline != -1 and newline < end:
        nxt = _NEXT_TEST.search(text, newline)
        if nxt and nxt.start() < end:
            end = nxt.start()
    return text[:end].strip()


def extra_constants(raw_text: str, already: set[str]) -> list[dict]:
    """Constants that sit outside the primary check, one construct each."""
    rows = []
    for construct in _constants_in(raw_text or ""):
        if construct in already:
            continue
        already.add(construct)
        token = next((token for token, name in _CONSTANTS if name == construct and token in (raw_text or "")), "")
        rows.append({
            "construct": construct,
            "exemption": False,
            "raw_text": _window(raw_text, token) if token else (raw_text or "")[:500].strip(),
        })
    return rows


def _window_rows(text: str) -> list[dict]:
    found = _constants_in(text)
    if re.search(r"\b(?:onionArchitecture|hexagonalArchitecture|layeredArchitecture)\b", text):
        if "layering" not in found:
            found.append("layering")
    if "adhereToPlantUmlDiagram" in text and "plantuml" not in found:
        found.append("plantuml")
    if not found:
        return [{"construct": "unparsed", "exemption": False, "raw_text": text[:500].strip()}]
    raw = text[:500].strip()
    return [{"construct": construct, "exemption": False, "raw_text": raw} for construct in found]


def _family(method: str, entry: str, negated: bool) -> str | None:
    if not _plausible(method):
        return None
    if method == "beFreeOfCycles":
        return "cycle_freedom"
    if method == "notDependOnEachOther":
        return "slice_dependency"
    if method == "adhereToPlantUmlDiagram" or "PlantUml" in method:
        return "plantuml"
    # The condition reports an upper-package dependency as a violation.
    if method == "dependOnUpperPackages":
        return "forbidden_dependency"
    if method.startswith("only") or method in {"onlyBeAccessed", "onlyHaveDependentClassesThat"}:
        return "allowed_dependency"
    if method.startswith("notBeAccessed") or method.startswith("beAccessed"):
        if method.startswith("not") or entry.startswith("no") or negated:
            return "forbidden_dependency"
        return "required_dependency"
    if _is_dependency(method):
        if entry.startswith("no") or negated:
            return "forbidden_dependency"
        return "required_dependency"
    if _is_naming(method):
        return "naming"
    if method in _ANNOTATION or method.endswith("AnnotatedWith"):
        return "annotation"
    if method in _VISIBILITY:
        return "visibility"
    if method in _PACKAGE or method.startswith("resideIn") or method.startswith("resideOutside"):
        return "package_location"
    if method in _INHERITANCE:
        return "inheritance"
    if method in _SIGNATURE or "RawReturn" in method or "RawParameter" in method or "Throwable" in method:
        return "signature"
    if method in {"beDeclaredIn", "beDeclaredInClassesThat"}:
        return "declaration_site"
    if method == "containNumberOfElements":
        return "element_count"
    return None


def _is_dependency(method: str) -> bool:
    if method.startswith("only"):
        return False
    markers = (
        "dependOn",
        "accessClasses",
        "accessField",
        "accessTarget",
        "callMethod",
        "callConstructor",
        "callCodeUnit",
        "getField",
        "setField",
        "DependentClasses",
        "DependenciesThat",
    )
    return any(marker in method for marker in markers)


def _is_naming(method: str) -> bool:
    return method.startswith((
        "haveSimpleName",
        "haveName",
        "haveFullName",
        "haveFullyQualifiedName",
        "notHaveFullyQualifiedName",
        "notHaveName",
        "notHaveFullName",
        "notHaveSimpleName",
    ))


def _plausible(method: str) -> bool:
    if len(method) < 4:
        return False
    return method not in {"that", "because", "check", "allowEmptyShould"}


def _constants_in(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for token, construct in _CONSTANTS:
        if re.search(rf"\b{token}\b", text) and construct not in seen:
            seen.add(construct)
            found.append(construct)
    tail = re.search(r"(NO_CLASSES_SHOULD_[A-Z0-9_]{8,})\s*$", text)
    if tail:
        prefix = tail.group(1)
        matched = {construct for token, construct in _CONSTANTS if token.startswith(prefix)}
        if len(matched) == 1:
            construct = next(iter(matched))
            if construct not in seen and not any(token == prefix for token, _ in _CONSTANTS):
                found.append(construct)
    return found


def _constant_construct(token: str) -> str | None:
    name = token.split(".")[-1]
    for constant, construct in _CONSTANTS:
        if name == constant:
            return construct
    matched = {construct for constant, construct in _CONSTANTS if constant.startswith(name) and len(name) >= 18}
    if len(matched) == 1:
        return next(iter(matched))
    return None


def _uncovered_constants(text: str, consumed: list[tuple[int, int]]) -> list[tuple[str, str]]:
    rows = []
    seen: set[str] = set()
    for token, construct in _CONSTANTS:
        if construct in seen:
            continue
        match = re.search(rf"\b{token}\b", text)
        if not match:
            continue
        if any(span_start <= match.start() < span_end for span_start, span_end in consumed):
            continue
        seen.add(construct)
        rows.append((construct, token))
    return rows


def _span_end(text: str, start: int, matches: list[re.Match], index: int) -> int:
    end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
    semicolon = text.find(";", start)
    if semicolon != -1 and semicolon + 1 < end:
        end = semicolon + 1
    if end - start > 2500:
        end = start + 2500
    return end


def _keyword(lexeme: str) -> str:
    return re.sub(r"\s*\($", "", lexeme)


def _window(text: str, token: str) -> str:
    index = text.find(token)
    if index < 0:
        return text[:500].strip()
    return text[max(0, index - 80): index + 420].strip()


def self_check() -> None:
    diego = """
    classes().that()
        .areAnnotatedWith(Service.class)
        .or().haveSimpleName("*Service")
        .should().resideInAnyPackage("com.github.diegopacheco.sandbox.java.archunit")
        .orShould().beAnnotatedWith(Documented.class);
    """
    diego_rows = extract(diego)
    diego_constructs = [row["construct"] for row in diego_rows]
    assert "classes" not in diego_constructs, diego_constructs
    assert diego_constructs == ["package_location", "annotation"], diego_constructs
    assert all(row["exemption"] is False for row in diego_rows)

    general = """
    import static com.tngtech.archunit.library.GeneralCodingRules.NO_CLASSES_SHOULD_ACCESS_STANDARD_STREAMS;
    import static com.tngtech.archunit.library.GeneralCodingRules.NO_CLASSES_SHOULD_THROW_GENERIC_EXCEPTIONS;
    import static com.tngtech.archunit.library.GeneralCodingRules.NO_CLASSES_SHOULD_USE_JAVA_UTIL_LOGGING;
    """
    general_rows = extract(general)
    general_constructs = {row["construct"] for row in general_rows}
    assert "unparsed" not in general_constructs, general_rows
    assert general_constructs == {"standard_streams", "generic_exceptions", "java_util_logging"}, general_constructs

    streams = extract("noClasses().should(GeneralCodingRules.ACCESS_STANDARD_STREAMS);")
    assert [row["construct"] for row in streams] == ["standard_streams"], streams

    forbidden = extract('noClasses().that().resideInAPackage("..domain..").should().dependOnClassesThat().resideInAPackage("..infra..");')
    assert [row["construct"] for row in forbidden] == ["forbidden_dependency"], forbidden

    allowed = extract('classes().that().resideInAPackage("..ui..").should().onlyDependOnClassesThat().resideInAnyPackage("..ui..", "java..");')
    assert [row["construct"] for row in allowed] == ["allowed_dependency"], allowed

    required = extract('classes().should().dependOnClassesThat().haveSimpleName("RedisTemplate");')
    assert [row["construct"] for row in required] == ["required_dependency"], required

    cycles = extract('slices().matching("..(*)..").should().beFreeOfCycles();')
    assert [row["construct"] for row in cycles] == ["cycle_freedom"], cycles

    frozen = classify_stored("FreezingArchRule.freeze(classes().should().dependOnClassesThat());", "FreezingArchRule")
    assert frozen[0]["construct"] == "FreezingArchRule" and frozen[0]["exemption"] is True
    assert len(frozen) == 1

    mixed = """
    classes().that().resideInAPackage("..service..")
        .should().onlyBeAccessed().byAnyPackage("..service..");

    @Test
    fun testNoFieldInjection() {
        NO_CLASSES_SHOULD_USE_FIELD_INJECTION.check(classes)
    }
    """
    mixed_rows = classify_stored(mixed, "classes")
    assert [row["construct"] for row in mixed_rows] == ["allowed_dependency"], mixed_rows
    extra = extra_constants(mixed, {row["construct"] for row in mixed_rows})
    assert [row["construct"] for row in extra] == ["field_injection"], extra


if __name__ == "__main__":
    self_check()
