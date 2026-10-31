# Research trial and forward evidence

`PerformanceStore` supports create-only research trial records and daily
ledgers. A research runner can save a `ResearchTrialRecord` with status
`STARTED` for each declared attempt before evaluation. Failed, rejected and
aborted attempts retain a terminal record and reason. A successful terminal
record requires a matching stored `BacktestResult` and `ResearchDailyLedger`;
the store validates their identity, window, cost inputs and results.

The store does not establish that a full trial family was declared before
performance was calculated. A runner that requires preregistration must freeze
and verify its complete candidate list, source and input identities, parameters,
costs, execution assumptions and registration evidence before evaluation.
Registration and content hashes alone do not prove when the commitment existed.

`ForwardObservationPolicy` and `forward_observation_receipt` provide a
candidate-specific non-live policy and a sequential, dependency-bound receipt
chain. They do not authenticate publication times or establish that a
candidate was frozen before an observation became available. Callers must
independently verify prospective freeze, actual data availability, freshness,
candidate identity and observation continuity before supplying healthy or
ready facts. Missing, stale, mismatched or unreadable evidence must remain
distinct and must not be treated as a completed observation. Policy completion
does not grant live execution or promotion authority.
