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
  need explicit adoption. Other lifecycle schemas and snapshot serializers are
  unchanged

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
