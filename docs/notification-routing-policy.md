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
When `summary_evidence` receives broker outcome collections, their complete,
unique order identities must match the submitted collection. Missing, duplicate,
or conflicting identities leave fill counts unknown and the cycle non-routine.
Non-empty string and integer order IDs are compared in their string form; boolean
and other values cannot establish identity. Pending outcomes additionally need
producer proof and compatible submitted statuses.
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

## Shared asset-management entrypoints

`route_asset_management_event` is the P10 channel boundary. It accepts the
existing `NotificationEvent` envelope and candidate writer. In every flag state,
normal cycles, heartbeats, acknowledged orders, fills, recovery, ordinary
maintenance reminders, research candidates and strategy signals require a
confirmed candidate write before deferral. Unknown categories and unproven
expected blocks retain the error path. An incident reason on a normal envelope
is contradictory evidence and raises rather than being silently deferred,
except on a producer-confirmed recovery that names the original incident.
The producer must validate classification against its real source facts;
this API does not infer health from message text, cash or a monitor check.

`render_asset_management_error` provides the fixed Chinese (default) and English
error body. It reuses operational time/reason localization and approved display
names, omits private identities and raw diagnostics, and accepts only explicit
HTTPS run links on caller-approved hosts. Missing links and counts stay unknown.
It neither invents a run URL nor claims delivery. It never renders a normal fact
as an error; normal facts belong in the existing central daily digest.

For an asset-management plugin recipient, pass
`asset_management_event_factory` and `persist_candidate` to
`publish_strategy_plugin_telegram_alerts`. Bind each signal to its authentic run;
archive the original signals in the existing producer report. Ordinary research
candidates must use `research_candidate`, rather than an error envelope merely
to retain an immediate push. Independent signal errors cannot be deferred as a
normal candidate. Errors additionally require an `IncidentTracker` backed by a
durable cross-process compare-and-set store via
`asset_management_incident_tracker`; the legacy has/write marker is insufficient.
A producer-confirmed recovery with the original incident reason clears that
incident only after its candidate write succeeds, without sending a recovery
push. An unbound recovery fact does not clear an arbitrary active incident.
Reservation precedes transport. A boolean transport result has no receipt, so it
remains pending/uncertain, including after restart, and is not automatically
resent. State/marker failures propagate. Producer/archive/candidate failures
still require the caller's operational error handling.

The public transport, non-asset plugin uses and legacy routing helper defaults
retain their behavior. This is an additive contract for subsequent QRS and
broker notification PRs: consumers must pin the reviewed shared revision and
explicitly bind their asset-management call sites. This library change alone
does not establish consumer adoption, a deployment, or runtime P10 compliance.
No daily service, schedule, database or delivery retry mechanism is added.
