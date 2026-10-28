# RQ4

ArchUnit rows of `data/corpus.csv`. Adoption is the first RQ3 commit that introduces an ArchUnit rule.
Ineligible repositories stay in the sample. The 12-month window only labels the treated subset.
ArchUnit N: 2422
Treated: 317
Panel ran: True

source-level dependency and layering replay on kept clones; within-treated description only, no ATT

## Ratify and reform

- replayed: 317
- classified (t=-1 and t=0 observed): 298
- ratifier (violations at t=-1 are 0): 240 (80.5%)
- reformer (a pre-adoption violation and 0 at t=0): 7 (2.3%)
- both: 1
- mean dependency/layering coverage: 52.9%
- mean evaluable coverage: 33.5%

Ratifier and reformer shares describe the treated repositories. They are not an effect relative to non-adopters.

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

## Difference in differences

- ran: False
- ATT estimated: False
- No control group, matching, or ATT. The Java control catalog (GHS/SEART) was not obtainable. Reported figures are within-treated descriptions.

