# RQ4

ArchUnit rows of `data/corpus.csv`. Adoption is the first RQ3 commit that introduces an ArchUnit rule.
Ineligible repositories stay in the sample. The 12-month window only labels the treated subset.
ArchUnit N: 2422
Treated: 317
Panel ran: True

source-level dependency and layering replay on kept clones

## Ratify and reform

- replayed: 317
- classified (t=-1 and t=0 observed): 298
- ratifier (violations at t=-1 are 0): 240 (80.5%)
- reformer (a pre-adoption violation and 0 at t=0): 7 (2.3%)
- both: 1
- mean dependency/layering coverage: 52.9%
- mean evaluable coverage: 33.5%

## Difference in differences

- ran: False
- Java control catalog (GHS/SEART) was not obtainable; DiD did not run. Ratify and reform are reported for the treated set.

