# Comparison summary

Four-way count check: passed.

## Corpus N

- no_extend ArchUnit: 734
- no_extend import-linter: 472
- no_extend dependency-cruiser: 512
- no_extend __all__: 1718
- with_extend ArchUnit: 2422
- with_extend import-linter: 826
- with_extend dependency-cruiser: 1073
- with_extend __all__: 4321

## Exclusions

- unavailable ArchUnit: 5
- unavailable import-linter: 4
- unavailable dependency-cruiser: 6
- no_rule_file ArchUnit: 377
- no_rule_file import-linter: 10
- no_rule_file dependency-cruiser: 5
- clone_error ArchUnit: 8
- clone_error import-linter: 5
- clone_error dependency-cruiser: 2

## History

- complete: 4321
- excluded: 15
- checkpoints: 4336

Clones: `data/RQ3/clones/<repository_id>__<strategy>`.

## H3

- no_extend H3.1: 0.28493533535750315 (CI 0.271576039208399–0.297805464081508); H3.2: 0.38547918683446275 (CI 0.3723136495643756–0.3986447241045499)
- with_extend H3.1: 0.26269986793842526 (CI 0.2535030096448396–0.2723130150661768); H3.2: 0.4956748963777257 (CI 0.4862137322040007–0.5039646783204181)

## RQ4

- treated: 317
- panel ran: True
- DiD ran: False
- ATT estimated: False
- No control group, matching, or ATT. The Java control catalog (GHS/SEART) was not obtainable. Reported figures are within-treated descriptions.

## Within-treated change

Source-level dependency and layering violations on treated repositories that have at least one evaluable rule and observed counts at t=-1, t=0 and t=12.
This is not an average treatment effect. There is no control group, no matching, and no difference-in-differences estimate.
Repositories with no evaluable rule are omitted, so a zero caused by an untranslated rule is not read as a clean architecture.

- snapshot cells with violations missing: 771
- repositories with at least one evaluable rule: 148
- of those, t=-1, t=0 and t=12 observed: 141
- zero violations at t=-1 in that subset: 83

Violation counts:

- t=-1: median 0.000 (95% CI 0.000–0.000); mean 73.348 (95% CI 23.879–138.241)
- t=0: median 0.000 (95% CI 0.000–3.000); mean 85.596 (95% CI 28.624–154.823)
- t=12: median 0.000 (95% CI 0.000–4.000); mean 103.879 (95% CI 33.794–196.163)

Change from t=-1 to t=12:

- decreased: 18 (12.8%; 95% CI 7.1%–17.7%)
- unchanged: 86 (61.0%; 95% CI 53.2%–69.5%)
- increased: 37 (26.2%; 95% CI 19.1%–33.3%)

- mean slope t=-12..-1: 1.630 violations per month (95% CI -0.090–4.383; n=141)
- mean slope t=1..12: 1.827 violations per month (95% CI 0.466–3.744; n=141)

Slopes are ordinary least squares within each repository on observed months in the window. They are not an ATT.

## RQ5

- dropped: no agent-authored pull-request linkage; the 200-pull-request threshold was not evaluated

## Clone failures

- Agrid-Dev/gridone (import-linter, kept): remote: Repository not found. fatal: repository 'https://github.com/Agrid-Dev/gridone.git/' not found
- vvChu/ccba-agent-platform (import-linter, extended): remote: Repository not found. fatal: repository 'https://github.com/vvChu/ccba-agent-platform.git/' not found
- achimdehnert/platform (import-linter, kept): remote: Repository not found. fatal: repository 'https://github.com/achimdehnert/platform.git/' not found
- crackedstudio/tikka (dependency-cruiser, extended): remote: Repository not found. fatal: repository 'https://github.com/crackedstudio/tikka.git/' not found
- mizo432/modulith-learning (ArchUnit, extended): git log failed with status 128
- giuliaprosio/authentication-app (ArchUnit, extended): git log returned no commits for rule paths
- pbxjtumse/iron-components-java (ArchUnit, extended): remote: Repository not found. fatal: repository 'https://github.com/pbxjtumse/iron-components-java.git/' not found
- gonzalopozo/gonzalopozo.github.io (dependency-cruiser, extended): git log returned no commits for rule paths
- leanderdulac/Atom-Finance (import-linter, extended): git log returned no commits for rule paths
- manwithacat/dazzle (import-linter, kept): git log exceeded 1200s for pyproject.toml
- oktadev/okta-ionic4-jhipster-example (ArchUnit, extended): git log returned no commits for rule paths
- mraible/mobile-jhipster (ArchUnit, extended): git log returned no commits for rule paths
- srikanthrayudu12/Social-media-backend (ArchUnit, extended): git log returned no commits for rule paths
- BreixoCF/padelcenter (ArchUnit, extended): git log returned no commits for rule paths
- AxonIQ/axoniq-framework (ArchUnit, kept): git log failed with status 128
