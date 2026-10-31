# Decision consumption receipt

`decision_consumption_receipts` records a run's observed input facts and hashes
of the actual pre-risk and post-risk `StrategyDecision` positions and budgets.
The caller supplies the decision clock, optional signal session, strategy
revision, configuration digest, and optional intent digest. A missing decision
or unknown identity is represented by `null`; callers must not infer a
pre-risk target from a post-risk decision. The canonical receipt digest detects
accidental or deliberate changes to its contents but does not authenticate
the producer or establish independent source provenance.

Each observation records an exact reference, observed/missing/unavailable
status, observed artifact digest and verification status when known, a consumer
authority decision, optional consumer identity, physical read-completion time,
canonical consumed-payload digest, and an optional availability time.
`availability_status` and `read_status` are derived separately against the
supplied decision clock; a read after that clock remains visible as such. A
loader's observed digest is
not proof of publication time or authority, and a missing or unavailable
observation cannot assert those facts. Callers must bind the observation to the
actual consumed payload and obtain any availability evidence independently.

An optional existing `qsl_execution_receipt.v1` is validated and linked by
its canonical digest. Its submitted outcome remains submitted; the receipt
does not infer acknowledgement, fills, or order identities. Attaching a
receipt checks report run and strategy identity, known strategy revision,
the report decision clock when present, optional actual post-risk target, and
any linked execution receipt. A known configuration digest is compared with
the report release digest when both are present; when the report lacks it, the
configuration binding remains unverified. The
caller must establish that the report, target, intent and execution facts
belong to the same run; the existing aggregate execution receipt contains no
run or fill identity and cannot establish that relationship by itself. Neither
receipt grants trading authority.

When an execution receipt is produced after the decision, the platform may
attach a separate `qsl_decision_execution_link.v1` to the same report. It
binds both receipt digests, run and strategy identities, plus canonical hashes
of order or fill records only when those records were explicitly observed.
`null` means unobserved; an empty record sequence means observed empty. The
link remains partial provenance because the aggregate execution receipt does
not independently contain the run identity.

For live static gate calls, optional `logical_evaluation_time` accepts only a
fresh UTC whole-second instant under the same freshness rules as the evidence
gate. Accepted explicit clocks appear as `risk_gate_evaluated_at`; malformed,
future, or stale clocks reject. Omitting it retains wall-clock evaluation.
Historical clocks are supported only by the separate offline replay API.
