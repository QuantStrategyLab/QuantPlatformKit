# Interval return coverage

## Scope and evidence boundary

The interval calculator consumes supplied, validated USDT checkpoint receipts.
Its end-flow calculation and latest-contiguous-segment selection remain the
existing contract. It does not enumerate a native archive or establish source
identity, retention, authorization, fees, cash-flow completeness or runtime
adoption. A qualified local segment is not proof of a complete account history.
The current Binance producer supports deposits; signed negative-flow fixtures
do not enable production withdrawal support.

Returns use the final checkpoint equity on each represented UTC date and the
sum of declared external flows on the destination observation date. They are
end-flow checkpoint observation returns, not exact TWR or natural-midnight-day
returns. UTC date labels are grouping labels, not NAV timestamps.

## Compatible APIs

- `live_interval_records_to_return_series(records, ...)` still returns a Series
- `live_interval_records_to_return_series_result(records, ...)` exposes the same
  Series plus status, detail and typed `IntervalReturnCoverage`
- Existing `live_run_records_to_return_series_result` delegates interval mode to
  that result API; scalar/calendar calculation is unchanged
- Existing `LiveReturnSeriesResult(series, status, detail)` construction remains
  valid because `coverage` defaults to `None`
- Existing `LiveReturnCollectionResult(series_by_profile, incomplete_by_profile)`
  construction remains valid; `coverage_by_profile` defaults to an empty mapping
- These result types have no existing wire serializer. Generic dataclass
  serialization now has additive coverage fields; strict external allowlists
  need explicit adoption. Legacy no-coverage snapshot wire stays unchanged;
  the opt-in versioned snapshot/export envelopes are described below

Explicit result coverage is authoritative. `Series.attrs["interval_coverage"]`
and `attrs["observation_status"]` provide compatibility copies; pandas
transformations or CSV serialization may discard attrs. Callers that need
coverage must retain the explicit result rather than infer it from nonempty
values or date labels. No consumer pin or deployment is updated by this change.

## Source segment versus calculable return window

All metadata timestamps are normalized aware UTC ISO strings.

- `source_segment_start_at` / `source_segment_end_at`: the selected source
  receipt component's interval boundaries
- `available_return_start_at` / `available_return_end_at`: the calculable latest
  contiguous observation window before an optional required-window selection
- `return_start_at` / `return_end_at`: the actual returned window; `None` when
  no return Series is available
- `account_scope_sha256`: the one validated account scope, or `None` when not
  uniquely established
- `method`, `timezone`, `currency`, `valuation_basis`: the supported calculation
  contract, not independent evidence of native source qualification
- `normalized_interval_count`: unique normalized logical intervals, including
  intervals subsequently excluded by conflict/barrier rules
- `segment_interval_count`: source intervals retained in the selected component
- `return_count`: returned observations; no opening NAV is invented
- `truncation_reasons`: sorted bounded reason codes for gaps, barriers or
  unavailability; exact duplicate and input-order changes do not add reasons

The first receipt provides its end equity but no start equity. Its end checkpoint
is the opening anchor, not a computed return. Three consecutive receipts ending
on three consecutive UTC dates yield two returns. The source receipt start is
never advertised as a calculable return start. Intraday receipts continue to be
aggregated under the existing last-checkpoint convention.

`coverage_status` distinguishes `complete_segment`, `truncated_segment`,
`complete_requested_window` and `unavailable`. “Complete” here applies only to
the supplied local checkpoint window. It is not native archive completeness.

## Required whole windows

Pass both optional keyword arguments `required_start_at` and `required_end_at`
to request a complete return window. They are supported by both interval APIs,
both live-run APIs, and `ReturnCollector.collect_from_live_runs_result`,
`collect_from_live_runs` and `collect`.

Both bounds must be timezone-aware, strictly increasing, and exactly match
retained daily final checkpoints within the latest calculable contiguous
segment. Successful requests select returns after the opening bound through the
ending bound and set `requested_window_complete=True`. Historical truncation
outside the requested window remains disclosed in reasons, while status is
`ok` for the fully covered requested window.

An unsupported bound, missing opening NAV, missing ending checkpoint or window
crossing a gap returns an empty Series with `incomplete_requested_window` and
`requested_window_complete=False`. Malformed/missing-one-bound or reversed
bounds yield `invalid_requested_window`. Both arguments absent preserve the
legacy latest-segment behavior. Scalar records do not satisfy an interval
window and return `incomplete_requested_window:interval_records_required`.

No interpolation, midnight conversion, first-receipt start-NAV fabrication or
CSV fallback completes a required window. Available-window metadata can still
identify the otherwise calculable segment after request rejection.

## Status and reasons

Without a required window, a nonempty untruncated interval segment has status
`ok`. A nonempty recovered latest segment has
`truncated_after_interval_gap`, with exact reasons in coverage and detail.
Unusable mixed scopes, unlocated invalid records or impossible adjusted NAV use
`incomplete_interval_coverage`. Fewer than two retained observation dates use
`insufficient_observations`, retaining known barrier reasons.

Reason codes:

- `missing_interval`: a temporal gap between valid receipts
- `overlapping_interval`: receipt overlap, not an exact continuation
- `missing_interval_record`: a live-run record lacks the interval key while
  other records establish interval mode
- `null_interval`: the interval key is explicitly null
- `invalid_interval`: receipt schema, scope, timestamp, currency, basis or
  numeric validation fails
- `interval_conflict`: same normalized scope/start/end has conflicting values
- `same_end_different_start`: multiple intervals share one end checkpoint
- `unlocated_invalid_interval`: an invalid record has no usable aware timestamp
  for its existing UTC-day barrier
- `mixed_account_scope`: more than one normalized account scope
- `observation_day_gap`: missing adjacent UTC observation date
- `invalid_adjusted_return`: end-flow adjustment cannot produce a legal return
- `invalid_requested_window`: required bounds are missing, malformed or reversed
- `requested_checkpoint_unavailable`: a required bound is not a retained daily
  final checkpoint

Existing conservative UTC-day barrier rules are preserved. Located invalid,
null, missing or conflicting records exclude observations through that day;
valid later observations can establish a new segment. Exact normalized
duplicates are idempotent; order and equivalent timezone representations do not
change results. Unlocated failures and mixed scopes remain unavailable.

## Collector and consecutive loss consumers

`ReturnCollector.collect_from_live_runs_result` includes
`coverage_by_profile` for derived interval profiles even when no usable Series
remains. If stream selection itself is ambiguous or unavailable, no calculation
is attempted; `incomplete_by_profile` records
`incomplete_interval_coverage:ambiguous_lifecycle_stream` or
`incomplete_interval_coverage:requested_stream_unavailable`, with no invented
scope/coverage metadata. A truncated legal
segment stays in `series_by_profile` and is also named in
`incomplete_by_profile`. Plain-Series collection preserves compatibility attrs.

An interval-backed live segment replaces the corresponding CSV series, including
an untruncated interval segment. CSV and live checkpoint returns have different
scope/method/coverage provenance and cannot be concatenated. An unavailable
interval profile is omitted rather than substituted with CSV returns. Required
window collection uses only qualified live outcomes, never research CSV alone.
Scalar behavior outside required-window requests is unchanged.

Consecutive losses derived from live-run records consume only the retained
latest continuous segment, so losses on opposite sides of a barrier cannot form
one streak. No loss controls, trading permissions, strategy signals or runtime
schedules are changed.

## Opt-in monitor and versioned persistence

`ReturnCollector.collect_result` retains the existing merged Series behavior
alongside `incomplete_by_profile` and authoritative `coverage_by_profile`.
`collect` remains the compatible Series mapping API.

`run_monitor` accepts `required_start_at` / `required_end_at` and
`include_interval_coverage=False`. Explicit bounds also enable coverage mode.
That mode requires the result API and checks every target profile before any
snapshot write. The normalized Series' full UTC date set, bounds and count must
match effective coverage; shifted equal-length dates, duplicates or NaN-induced
changes cannot qualify. CSV or forged/lost attrs cannot satisfy a missing whole window.
Without either opt-in, the original monitor behavior and official no-coverage
snapshot wire remain unchanged.

`StrategyPerformanceSnapshot.interval_return_coverage` defaults to `None`.
With `None`, `to_dict` keeps the original 15 fields and PerformanceStore writes
`strategy_lifecycle.v1`. With coverage, the same store and daily key carry:

- `schema_version: strategy_lifecycle.snapshot.coverage.v1`
- `snapshot`: the original snapshot fields
- `interval_return_coverage`: validated source, available, effective return and
  requested windows, calculation method, counts and bounded reasons

The new reader explicitly validates and unwraps this schema. Unknown versions
or invalid coverage do not downgrade to ordinary successful observations.
The old reader lacks the required date/profile fields at the envelope root and
obtains an unavailable observation; its exporter refuses it. Generic dataclass
serialization is not the official snapshot wire and gains the optional field;
strict external dataclass allowlists need explicit adoption.

## Coverage export, comparison and paired readers

Coverage-bearing exports use `strategy_performance.coverage_envelope.v1` at
both container and item-wrapper level. Each item's `payload` is the existing
v2 snapshot with explicit coverage and comparison evidence in `metadata`.
Legacy no-coverage exports remain ordinary `strategy_performance.v2`.
Old watchers reject the new schema and cannot find ordinary metrics at their
expected level. The AAB coverage-aware paired reader is not yet adopted; do
not relabel or flatten this envelope to make an old watcher accept it. The
strict, sanitized 13-field P3 artifact is a separate unchanged contract. Public
coverage metadata and comparison evidence omit the internal account-scope hash.

`baseline_coverage_by_profile` supplies explicit reference coverage to the
exporter. A machine-checkable comparison needs the same effective checkpoint
window, method, timezone, currency, valuation basis, scope and observation
count, plus matching actual metric dates, calendar and annualization. Required
performance numbers must be finite. Both sides' sanitized coverage and actual
comparison dates/counts/bases are disclosed; missing reference coverage is
incomparable. A trailing metric slice with only date labels cannot invent an
exact checkpoint anchor. Nominal 126/252-window names do not establish that
many available observations.

`run_monitor` also accepts `baseline_coverage_by_profile` and applies this gate
before `compare_with_backtest`. In coverage mode, missing or mismatched baseline
coverage preserves the measured numbers but leaves `drift_score=None` and sets
`drift_status=not_comparable_interval_coverage`; it supplies no qualified drift
or automatic factor-invalidity evidence. Legacy no-coverage comparison behavior
is unchanged. Snapshot `as_of` remains the run date, distinct from effective
checkpoint timestamps.

`detect_drift` honors that status before missing-window/baseline fallbacks:
the fixed unevaluable reason is retained, `baseline_available=False`, alerts
are suppressed and previous restrictions are not loosened. The existing
store-backed drift and automatic-dispatch path cannot reopen optimization or
provider calls from it. A retained REVIEW/previous CRITICAL restriction is not
a newly measured failure of the unknown observation.

A legal segment after a historical gap remains available for its actual
effective window. Historical reasons do not invalidate a fully covered new
requested window, and they are not a blanket rejection of local learning.
AI review accepts explicit `snapshot` / `comparison_coverage` context, binds
declared current numerical metrics to the actual snapshot window, and permits
performance conclusions only for qualified comparisons. Unknown or unmet
coverage escalates before any provider/verifier call. Its new coverage prompt
context is allowlisted and contains no account-scope hash or path identifier.
Calls without snapshot context retain legacy advisory semantics; they do not
prove the new coverage contract.

Rollback disables the opt-in for future legacy writes; it does not erase the
meaning of existing envelopes. Keep the coverage-capable reader for those
records, or have an old reader treat them as unavailable. This change does not
update consumer dependency pins, deploy a paired reader or qualify a native
account archive, exact TWR, or live trading authority.
