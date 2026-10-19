# RQ2 codebook (development set)

This codebook was induced from the first 1,000 kept and extended funnel repositories. That set is the development set and is excluded from H2.1. Labels come from re-parsing the `raw_text` already stored in `data/RQ2/constructs.jsonl`. The repos were not crawled again. For a Maven file the old extractor had marked `unparsed`, that stored text is only the first 500 characters of the file. A matched ArchUnit rule stores the statement up to the next semicolon, capped around 700 characters. Where a Kotlin rule has no semicolon, the stored text can run into the next test. The classifier keeps the primary `should()` / `shouldNot()` call and cuts at the next rule entry or the next `@Test` / `@ArchTest`.

A row's `construct` names the check. `data/RQ2/codebook_map.json` maps each construct to a category. `structural_family` lists the categories that are layering or dependency checks. `null` is used only for `unparsed` and for the exemption markers `FreezingArchRule` and `@ArchIgnore`. Exemption stays a boolean (`ignoreDependency` on a layering rule, `ignore_imports` on an import-linter contract, `exception` / severity `ignore` / `off` / `info` / `warn` on a dependency-cruiser rule).

Counts below are rows in `data/RQ2/dev_classified.jsonl` (10,314 rows after re-parsing the 10,231 unique stored rows).

| Category | Count | Structural | Tools |
| --- | ---: | --- | --- |
| forbidden_dependency | 2583 | yes | ArchUnit, import-linter, dependency-cruiser |
| cycle_freedom | 563 | yes | ArchUnit, dependency-cruiser |
| layering | 497 | yes | ArchUnit, import-linter |
| allowed_dependency | 374 | yes | ArchUnit, dependency-cruiser |
| naming | 315 | no | ArchUnit |
| custom_condition | 229 | no | ArchUnit |
| visibility | 195 | no | ArchUnit |
| annotation | 191 | no | ArchUnit |
| inheritance | 182 | no | ArchUnit |
| package_location | 165 | no | ArchUnit |
| required_dependency | 103 | yes | ArchUnit, dependency-cruiser |
| independence | 103 | yes | import-linter |
| signature | 83 | no | ArchUnit |
| slice_dependency | 57 | yes | ArchUnit |
| protected | 34 | yes | import-linter |
| plantuml | 33 | yes | ArchUnit |
| standard_streams | 30 | no | ArchUnit |
| acyclic_siblings | 18 | yes | import-linter |
| declaration_site | 18 | no | ArchUnit |
| element_count | 15 | no | ArchUnit |
| java_util_logging | 8 | no | ArchUnit |
| generic_exceptions | 7 | no | ArchUnit |
| allowlist | 4 | yes | import-linter |
| joda_time | 3 | no | ArchUnit |
| field_injection | 3 | no | ArchUnit |
| isolated_apps | 2 | yes | import-linter |
| domain_purity | 2 | yes | import-linter |
| conditional | 1 | yes | import-linter |
| no-cross-test-imports | 1 | yes | import-linter |
| forbidden_import | 1 | yes | import-linter |

### forbidden_dependency

Structural. Constructs: `forbidden_dependency` (ArchUnit, 774), `forbidden` (import-linter, 1,027; dependency-cruiser, 782). ArchUnit rows are `noClasses()` / `noMethods()` / `noFields()` with `dependOn`, `access`, or `call`, and `DependencyRules.dependOnUpperPackages` / `NO_CLASSES_SHOULD_DEPEND_UPPER_PACKAGES`.

`noClasses().that().resideInAPackage("..core").should().dependOnClassesThat(resideInAPackage("..renderer.."));` (neo4j/cypher-dsl)

### cycle_freedom

Structural. Constructs: `cycle_freedom` (ArchUnit `beFreeOfCycles`, 166), `circular` (dependency-cruiser, 397).

`slices().matching("net.amygdalum.(**)").should().beFreeOfCycles()` (almondtools/testrecorder)

### layering

Structural. Constructs: `layering` (ArchUnit `layeredArchitecture` and `onionArchitecture`, 176), `layers` (import-linter, 321). Seventeen ArchUnit rows also set `exemption` because the statement calls `ignoreDependency`.

`layeredArchitecture().consideringAllDependencies().layer("Web").definedBy("..web..").layer("Service").definedBy("..service..")` (citrusframework/citrus-simulator)

### allowed_dependency

Structural. Constructs: `allowed_dependency` (ArchUnit `onlyDependOn`, `onlyAccess`, `onlyBeAccessed`, `onlyHaveDependent`, `onlyCall`, 364), `allowed` (dependency-cruiser, 10).

`classes().that().resideInAPackage("..command.service..").should().onlyBeAccessed().byAnyPackage("..command.service..", "..command.handlers..")` (cwoolner/flex-poker)

### naming

Construct: `naming` (ArchUnit, 315). `haveSimpleName*`, `haveNameMatching`, `haveFullyQualifiedName`, and the same calls on fields and methods. A `haveSimpleName` in the `that()` filter is scope, so it does not select this category.

`noClasses().should().haveSimpleNameEndingWith("Mapper")` (sofn/ArchForge)

### custom_condition

Construct: `custom_condition` (ArchUnit, 229). A `should(condition)` call is visible, and the condition is a project-specific `ArchCondition`, an ArchUnit test fixture (`satisfySomething`, `BE_SATISFIED`), or `should().be(Class)` / `should().notBe(Class)`.

`noClasses().should(publiclyImplementInterfacesInSamePackage())` (hjohn/Dirk)

### visibility

Construct: `visibility` (ArchUnit, 195). `bePublic`, `bePrivate`, `beProtected`, `bePackagePrivate`, `beStatic`, `beFinal`, `haveModifier`, `haveOnlyFinalFields`, `haveOnlyPrivateConstructors`, and their negations. Two modifier checks in one statement stay one row.

`fields().that().areDeclaredInClassesThat().areAnnotatedWith(ValueObject.class).should().bePrivate().andShould().beFinal()` (konradrenner/stammdaten)

### annotation

Construct: `annotation` (ArchUnit, 191). `beAnnotatedWith`, `notBeAnnotatedWith`, `beMetaAnnotatedWith`.

`classes().that(serviceClasses).should().beAnnotatedWith(Service::class.java)` (cwoolner/flex-poker)

### inheritance

Construct: `inheritance` (ArchUnit, 182). `implement`, `beAssignableTo`, `beAssignableFrom`, `beInterfaces`, and the `notBe*` type-kind checks.

`classes().that(areEntity()).should().beAssignableTo(BaseEntity.class)` (jbb-project/jbb)

### package_location

Construct: `package_location` (ArchUnit, 165). The `should()` call is `resideInAPackage`, `resideInAnyPackage`, or `resideOutsideOfPackage`, and the rule is not a `layeredArchitecture` / `onionArchitecture` rule. The same snippet can also emit `annotation` when a second `should()` checks a different thing: `classes().that().areAnnotatedWith(Service.class).or().haveSimpleName("*Service").should().resideInAnyPackage("...archunit").orShould().beAnnotatedWith(Documented.class)` (diegopacheco/Diego-Pacheco-Sandbox).

### required_dependency

Structural. Constructs: `required_dependency` (ArchUnit, 101), `required` (dependency-cruiser, 2). ArchUnit rows are positive `classes()` / `methods()` rules whose `should()` is `dependOnClassesThat` or `accessClassesThat` (a dependency that must exist), which is a different check from `onlyDependOn` and from `noClasses().should().dependOn`.

`classes().that(redisRepositoryClasses).should().dependOnClassesThat().haveSimpleName("RedisTemplate")` (cwoolner/flex-poker)

### independence

Structural. Construct: `independence` (import-linter, 103). A set of modules that must not import one another.

`name = tool packages are mutually independent` / `type = independence` (mavlink/qgroundcontrol)

### signature

Construct: `signature` (ArchUnit, 83). Raw return type, raw parameter types, raw field type, or declared thrown type.

`noFields().should().haveRawType(SimpleDateFormat.class)` (Calimerico/eventify)

### slice_dependency

Structural. Construct: `slice_dependency` (ArchUnit, 57). `slices()` whose `should()` is `notDependOnEachOther`.

`slices().matching("..core.(*)..").should().notDependOnEachOther()` (braintelligencePL/project-manager-kotlin)

### protected

Structural. Construct: `protected` (import-linter, 34). A module whose internals may be imported only by named importers.

`name = Settings can be directly imported only in settings, use django.conf` / `type = protected` (wemake-services/wemake-django-template)

### plantuml

Structural. Construct: `plantuml` (ArchUnit, 33). Classes must follow the dependencies drawn in a PlantUML component diagram.

`classes().should(adhereToPlantUmlDiagram(PACKAGE_DESIGN, consideringOnlyDependenciesInAnyPackage("io.jenkins.plugins.checks..")))` (jenkinsci/checks-api-plugin)

### standard_streams

Construct: `standard_streams` (ArchUnit, 30). `NO_CLASSES_SHOULD_ACCESS_STANDARD_STREAMS` or `ACCESS_STANDARD_STREAMS`.

`noClasses().should(GeneralCodingRules.ACCESS_STANDARD_STREAMS)` (eclipse-sirius/sirius-web)

### acyclic_siblings

Structural. Construct: `acyclic_siblings` (import-linter, 18). Sibling modules under a package must not form import cycles.

`name = Package modules form an acyclic dependency graph` / `type = acyclic_siblings` (underloam/xbbg)

### declaration_site

Construct: `declaration_site` (ArchUnit, 18). `beDeclaredIn` / `beDeclaredInClassesThat` on methods or fields.

`noMethods().that().areAnnotatedWith(Scheduled.class).should().beDeclaredInClassesThat().resideOutsideOfPackage("org.example.spring1.jobs..")` (UTCN-SoftwareDesignLab/SoftwareDesignUTCN)

### element_count

Construct: `element_count` (ArchUnit, 15). `containNumberOfElements`.

`classes().that().resideInAPackage(...).should(containNumberOfElements(greaterThanOrEqualTo(1)))` (famri/wamya-backend)

### java_util_logging

Construct: `java_util_logging` (ArchUnit, 8). `NO_CLASSES_SHOULD_USE_JAVA_UTIL_LOGGING` or `USE_JAVA_UTIL_LOGGING`.

`noClasses().should(GeneralCodingRules.USE_JAVA_UTIL_LOGGING)` (eclipse-sirius/sirius-web)

### generic_exceptions

Construct: `generic_exceptions` (ArchUnit, 7). `NO_CLASSES_SHOULD_THROW_GENERIC_EXCEPTIONS` or `THROW_GENERIC_EXCEPTIONS`.

`noClasses().should(GeneralCodingRules.THROW_GENERIC_EXCEPTIONS)` (eclipse-sirius/sirius-web)

### allowlist

Structural. Construct: `allowlist` (import-linter, 4).

`name = Core is standalone` / `type = allowlist` (hass-energy/haeo)

### joda_time

Construct: `joda_time` (ArchUnit, 3). `NO_CLASSES_SHOULD_USE_JODATIME` or `USE_JODATIME`.

`import static com.tngtech.archunit.library.GeneralCodingRules.NO_CLASSES_SHOULD_USE_JODATIME` (junrar/junrar)

### field_injection

Construct: `field_injection` (ArchUnit, 3). `NO_CLASSES_SHOULD_USE_FIELD_INJECTION`. A field whose `should()` is `notBeAnnotatedWith` stays in `annotation`; only the library constant is this group.

`NO_CLASSES_SHOULD_USE_FIELD_INJECTION.check(classesUnderTest.that(serviceClasses))` (cwoolner/flex-poker)

### isolated_apps

Structural. Construct: `isolated_apps` (import-linter, 2). Code outside an isolated app may reach only that app's public API.

`name = Do not depend on non-public API of isolated apps.` / `type = isolated_apps` (openedx/openedx-platform)

### domain_purity

Structural. Construct: `domain_purity` (import-linter, 2). A domain package may depend only on itself and the standard library.

`name = ER shared exception vocabulary depends only on itself and the standard library` / `type = domain_purity` (finecode-dev/finecode)

### conditional

Structural. Construct: `conditional` (import-linter, 1). Named third-party modules may be imported only conditionally.

`name = 3rd-party clients must be secured by conditional imports` / `type = conditional` (nolar/kopf)

### no-cross-test-imports

Structural. Construct: `no-cross-test-imports` (import-linter, 1). Test modules must not import other test modules.

`name = Test files do not import other test files` / `type = no-cross-test-imports` (DataDog/system-tests)

### forbidden_import

Structural. Construct: `forbidden_import` (import-linter, 1). Modules inside a container may import only listed external packages.

`name = Prevent Non-listed external imports in physicsnemo` / `type = forbidden_import` (NVIDIA/physicsnemo)

## Exemption markers

These stay markers. The map value is null, and they are outside the structural family.

- `FreezingArchRule` (ArchUnit, 120). A frozen violation store wrapped around a rule.
- `@ArchIgnore` (ArchUnit, 52). A test or method dropped from evaluation.

## What remains unparsed

`unparsed` is 4,322 rows (ArchUnit 4,276, import-linter 32, dependency-cruiser 14). The map value is null.

Of the 3,321 Maven rows that were `unparsed` before this pass, 19 contained a recoverable predicate in the stored window and moved out. They produced 22 labeled rows: 10 `layering` (`onionArchitecture`, which the old entry list did not match), 4 `forbidden_dependency` (upper-package constants), 3 `standard_streams`, 3 `generic_exceptions`, 1 `java_util_logging`, and 1 `joda_time`. Junrar's `CodingRulesTest` is one of those rows: four `GeneralCodingRules` static imports in the first 500 characters, and no `classes()` call. The other 3,302 Maven windows stay `unparsed` because the 500-character cut does not reach a predicate: 2,170 mention an ArchUnit import or API type and stop before any `should()` or library constant; 1,079 are a license or copyright header with the import past the cut; 47 contain neither an ArchUnit token nor a license marker; 6 import `GeneralCodingRules` or `ModuleRuleDefinition` without a constant name or a `modules()` predicate in the window.

Another 974 Maven rows that used to be labeled `classes`, `methods`, `fields`, `constructors`, `slices`, or a `no*` entry are `unparsed` now. The stored statement has no complete `should()` / `shouldNot()` call. That happens when the text is ArchUnit's own method definition, or when the predicate sits past the stored cutoff. `classes` is an API entry, so those rows are not given a rule type.

Six import-linter files moved out of `unparsed` because the stored prefix held a contract under `[contract:...]` or `[importlinter:name]` rather than `[importlinter:contract:...]`. Thirty-two remain: a `pyproject.toml` header, an `[importlinter]` block with no `type` line in the first 500 characters, or a document that only mentions the tool. Two dependency-cruiser files moved out: one prefix contains both a `no-circular` rule and a `no-orphans` rule (circular and forbidden), and one prefix names `no-circular` where `"circular": true` is past the cut. Fourteen remain because the stored prefix is options only (`doNotFollow`, reporters) and has no forbidden, allowed, required, or circular rule.

Left `unparsed` on purpose: an ArchUnit import with no recoverable predicate; a `GeneralCodingRules` or `modules` import that does not name the check; a statement cut off before `should()`; an import-linter file with no `type` line in the stored text; a dependency-cruiser file whose stored prefix has no rule array. A visible project-specific `should(condition)` is `custom_condition`, not `unparsed`.

## Comparison

ArchUnit's documented library use cases, import-linter's contract types, and the natural-language rules studied by Lucena, Alves, and Brunet were sensitizing concepts only. The groups above are the ones this development set actually contains.

ArchUnit's layer and onion APIs, and import-linter `layers`, resemble our `layering`. ArchUnit `noClasses().should().dependOn` / `access` / `call`, import-linter `forbidden`, and dependency-cruiser `forbidden` resemble `forbidden_dependency`. ArchUnit `onlyDependOn` / `onlyBeAccessed` / `onlyHaveDependent` and dependency-cruiser `allowed` resemble `allowed_dependency`. ArchUnit `classes().should().dependOnClassesThat` and dependency-cruiser `required` resemble `required_dependency`. ArchUnit `slices().should().beFreeOfCycles` and dependency-cruiser `circular` resemble `cycle_freedom`. ArchUnit `slices().should().notDependOnEachOther` resembles `slice_dependency`; import-linter `independence` is the same idea for a named set of modules and stays its own category. `acyclic_siblings` resembles cycle freedom and stays its own contract. `naming`, `inheritance`, `annotation`, and `visibility` resemble the naming/stereotype, annotation, and visibility families in those sources. `package_location` is a `resideIn` check on its own, separate from layering.

`standard_streams`, `generic_exceptions`, `java_util_logging`, `joda_time`, and `field_injection` resemble ArchUnit `GeneralCodingRules` and sit outside the six-way layering/dependency/naming/visibility/annotation list. `plantuml` resembles ArchUnit's PlantUML component-diagram rules. `protected`, `allowlist`, `domain_purity`, `forbidden_import`, `isolated_apps`, `conditional`, and `no-cross-test-imports` are import-linter contract types present in this set; they stay separate from `forbidden` and `layers`. `signature`, `declaration_site`, `element_count`, and `custom_condition` are checks the stored text actually makes. No category was added only because a paper names it, and none of these tool-specific contracts was folded into another group to force a six-way scheme.
