# Pending order evidence v1

`AccountSubmissionSession` accepts optional order-level evidence on a complete
account snapshot. The evidence is recorded in the account journal and validated
again on replay. This contract records asserted coverage only: it does **not**
subtract exposure, release reservations, resolve UNKNOWN, or authorize orders.
Existing snapshots and journal events without the evidence retain their prior
behavior. Old writers cannot replay events with the new optional fields; upgrade
all account-journal readers and writers before emitting them, and retain one
account writer/fence. Roll back only after ensuring older readers will not read
new events.

For a new observation, opt in with `dispatch(...,
record_observation_watermark=True)` to record the session clock's UTC reception
time, or supply `record_observation(..., recorded_at=...)` when recording a
later observation. The journal exposes `observation_event_sha256` and
`observation_recorded_at` for each attempt. The reception watermark is not a
broker timestamp and does not itself prove when the broker produced the facts.
If the optional clock fails, returns invalid UTC, or moves backward relative to a
previous recorded reception time, the broker observation is still persisted
without a watermark. That observation cannot support this evidence. Replay
rejects an event that claims a backward watermark. Legacy observations have no
watermark and cannot support this evidence. An exact
observation replay is idempotent and cannot retrofit a watermark onto an older
event; a new valid observation event is required.

Pass `snapshot["pending_order_evidence"]` with exact fields:

- `schema_version`: `pending_order_evidence.v1`.
- `account_domain_key`, `account_binding`, `currency`, `source_digest`, and
  `valuation_at`: exactly those of the recorded account snapshot. Account
  binding is `submission_binding_digest({"broker": broker, "account_id": id})`.
- `source_version`: nonempty producer/source version; `observed_through`: UTC
  source coverage watermark, no later than valuation. The producer must be able
  to establish the watermark's meaning and clock comparability; a mere read time
  does not establish broker completeness.
- `orders`: list of objects with `attempt_id`, `broker_order_id`,
  `journal_observation_sha256`, `remaining_quantity`, `remaining_fee`, and
  `pending_3x_exposure`. Quantity is in order units. Fee and exposure are
  nonnegative account-currency amounts; exposure uses the same units and
  valuation convention as the snapshot aggregate `pending_3x_exposure`.

Each item must refer to a unique known-pending journal attempt and broker ID,
match its latest observation hash and remaining quantity, have a reconciled
reservation, and assert coverage through at least the journal reception time.
The sum of item exposures cannot exceed the aggregate pending exposure. This
check does not establish that the source truly covers those events, that the
fees or exposure are economically complete, or that the account's total pending
orders are represented by the list. Those are producer obligations requiring
independent native evidence. Reject malformed or mismatched evidence; omit it
when facts are unavailable. Real broker evidence and end-to-end operation remain
unverified until independently tested on an authorized source.
