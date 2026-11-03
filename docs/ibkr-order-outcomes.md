# IBKR read-only order outcomes

`quant_platform_kit.ibkr.order_outcome.resolve_order_outcome` observes one
submitted order using `reqAllOpenOrders`, `reqCompletedOrders(apiOnly=False)`
and `reqExecutions`. It does not submit, modify, cancel or retry an order. The
existing `submit_order_intent` wait and return contract are unchanged.

The caller supplies the original broker order ID, account, client ID, symbol,
side, requested quantity and aware submission timestamp. An available permanent
ID adds an identity check. Order IDs alone are not globally unique. Same-number
orders on other clients or accounts cannot contribute evidence.

`OrderOutcome` is frozen and contains `order_id`, `status`, `filled_qty`,
`remaining`, `avg_price`, `commission`, `last_update`, `terminal` and immutable
execution fills. Its status is one of `filled`, `partially_filled`, `cancelled`,
`rejected`, `pending` or `unknown`. A nonterminal partial fill retains its open
obligation. A cancellation can be terminal with a positive filled quantity.

Missing quantities/prices stay `None`; no requested quantity is promoted to a
fill. Missing commission reports stay unknown. A known fee requires a matching
execution ID, a populated report currency and a finite commission; a matching
zero is valid. Currency participates in duplicate comparison; conflicting reports
remain unknown. Fees are summed only when every report uses the same currency;
mixed currencies leave commission unknown without conversion. `last_update` is a
broker observation timestamp, never the local query time. Empty sources, mismatched or
inconsistent facts, naive timestamps and ambiguous `Inactive` statuses remain
unknown. Transport failures raise `OrderOutcomeReadError` with a fixed diagnostic;
callers must not treat a partial source snapshot as success. SDK error events
observed during the three reads also fail the observation, including when the
SDK returns an empty list instead of raising. The temporary listener is removed
on success or failure; the caller's `RaiseRequestErrors` setting is unchanged.

The `ib_insync` completed-order callback supplies an empty `OrderStatus`. Its
zero defaults are not fill facts. The resolver requires explicit
`order.filledQuantity` and/or matching executions. Without a broker timestamp,
a positive, non-Boolean integer permanent ID must bind that terminal to the
caller's supplied permanent ID or to every matching execution. An unbound
terminal cannot borrow execution freshness, including for partial cancellations.
Invalid supplied permanent IDs leave the outcome unknown.
Each terminal observation must supply its own freshness evidence; an open order's
log cannot date a timeless terminal. Conflicting observed permanent IDs remain
unknown even when the caller has no permanent ID. Execution freshness compares
UTC timestamps at broker second resolution, admitting same-second fills while
rejecting executions from an earlier second. Original timestamp values are kept.
Execution IDs are deduplicated; conflicting duplicates remain unknown.

Consumers own bounded request timeouts and exclusive reads on their private
connection, and durable observation storage. They must keep financial records in protected storage and
mask identifiers in notices. Observations do not clear UNKNOWN execution claims,
release cash or risk reservations, or authorize another order. Adoption requires
a separately reviewed consumer revision; library tests do not prove deployment
or real broker behavior. Commission evidence that arrives after the consumer
freezes a terminal observation can remain unknown in that observation.
