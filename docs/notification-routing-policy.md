# Notification routing policy

Routine cycles, healthy heartbeats, acknowledged orders and fills are daily
digest candidates. Their route does not depend on the platform unified flag or
`QSL_DIGEST_ROUTINE_ORDERS`. A routine fact is deferred only after its bound
identity is known and its candidate write is confirmed. A failed or uncertain
write remains a coverage failure; do not send the normal success message as a
fallback. Consumers must report the failure through their operational incident
path without inventing counts or delivery confirmation.

Unknown order outcomes, reconciliation failures, authentication failures and
other operational errors retain the existing urgent incident path. A broker
acknowledgement does not prove a fill. An expected risk block is routine only
when a producer validates the existing bound structured evidence; a bare event
or evidence string does not establish that proof.

The optional `known_pending` argument to cycle evidence is reserved for a
producer that has validated broker acknowledgement identities, compatible
status and counts, and the absence of unknown or conflicting outcomes. The
default remains false. This notification classification does not change a raw
reconciliation receipt or claim that reconciliation or a fill is complete.
Retain the underlying pending-reconciliation status in the archived summary;
the projection reports an order submission and leaves unproven fills unknown.
The lower-level legacy digest helper retains its existing mode default;
participating broker integrations explicitly request daily routing.

Routine plugin observations are counted from live signals, where the alert
criteria are available, and stored as bounded route counts in the report
summary before suppressing their individual notifications. Archived plugin
summaries alone omit some error fields and cannot establish that proof. An
unconfirmed archive or candidate write remains an operational coverage failure.
An empty observation count mapping means no routine observations were seen;
an absent mapping means the observation count is unknown. Conflicting mappings
for the same run must remain unknown rather than being added together.
The generic `project_reports` output groups cycles by day and is not a QRS
per-run input: QRS requires a source run identity and one cycle per run. A
consumer that combines archive and event candidates must use a validated
per-run projection and bind observation counts to that same run identity.

This source-level policy requires coordinated producer and digest consumer
adoption, compatible pinned revisions, and runtime validation. Its presence in
this repository does not establish production deployment or delivery.
