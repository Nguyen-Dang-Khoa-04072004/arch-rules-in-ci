# Codebook

Categories are the automatic map in `data/RQ2/codebook_map.json`.
The structural family used for H2.1 is dependency and layering.
A null map entry is not assigned a category.

| construct | category | subtype | subject |
|---|---|---|---|
| @ArchIgnore |  |  |  |
| FreezingArchRule |  |  |  |
| acyclic_siblings | cycle |  |  |
| allowed | dependency | allowed |  |
| allowed_dependency | dependency | allowed |  |
| allowlist | dependency | allowed |  |
| annotation | annotation |  |  |
| circular | cycle |  |  |
| conditional | dependency | conditional |  |
| custom_condition |  |  |  |
| cycle_freedom | cycle |  |  |
| declaration_site | naming |  |  |
| domain_purity | dependency | allowed |  |
| element_count | other |  |  |
| field_injection | other |  | field_injection |
| forbidden | dependency | forbidden |  |
| forbidden_dependency | dependency | forbidden |  |
| forbidden_import | dependency | forbidden |  |
| generic_exceptions | other |  | generic_exceptions |
| independence | dependency | forbidden |  |
| inheritance | other |  |  |
| isolated_apps | dependency | allowed |  |
| java_util_logging | dependency | forbidden | java_util_logging |
| joda_time | dependency | forbidden | joda_time |
| layering | layering |  |  |
| layers | layering |  |  |
| naming | naming |  |  |
| no-cross-test-imports | dependency | forbidden |  |
| package_location | naming |  |  |
| plantuml | dependency | allowed | plantuml |
| protected | dependency | allowed |  |
| required | dependency | required |  |
| required_dependency | dependency | required |  |
| signature | other |  |  |
| slice_dependency | dependency | forbidden |  |
| standard_streams | dependency | forbidden | standard_streams |
| unparsed |  |  |  |
| visibility | visibility |  |  |

## Lucena et al.

Lucena et al. category counts are not in this workspace, so this study does not report a cell-by-cell comparison with that natural-language taxonomy.
Naming, visibility, annotation and other stay as separate categories in the tables.

