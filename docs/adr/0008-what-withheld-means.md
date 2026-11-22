# A withheld variant removes what the guide's escalation rule needs, not every signal

The instructor asked for objective criteria for appropriate abstention. On a withheld variant the only correct behaviour is to abstain, so "withheld" needs a definition a reviewer can check. A withheld variant is correct to abstain on when at least one record the case's guide needs to reach a disposition is withheld. Some suspicious or reassuring signal may remain (in AUTH-001 a `python-requests` sign-in from a hosting IP is still visible), and a model that answers from it lands in `answered_when_should_abstain`: by this rule it decided without the evidence the procedure requires. AUTH-001..004 were approved under this rule and stay as they are; the report states it as a limitation.

Cases written after this decision follow a stricter rule, so that abstaining is clearly right and not only right by definition:

1. Withhold enough that neither disposition is supported by what remains: remove the records that would tip a reader either way, not only those the escalation rule names.
2. The alert's `summary` must not restate a withheld record's facts (AUTH-003's summary still describes the spray it withholds).
3. Keep each variant's expected answers fixed before any run, as for every case.
