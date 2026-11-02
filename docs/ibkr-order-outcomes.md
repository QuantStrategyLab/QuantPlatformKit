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
fill. Missing commission reports stay unknown. `last_update` is a broker
observation timestamp, never the local query time. Empty sources, mismatched or
inconsistent facts, naive timestamps and ambiguous `Inactive` statuses remain
unknown. Transport failures raise `OrderOutcomeReadError` with a fixed diagnostic;
callers must not treat a partial source snapshot as success.

The `ib_insync` completed-order callback supplies an empty `OrderStatus`. Its
zero defaults are not fill facts. The resolver requires explicit
`order.filledQuantity` and/or matching executions. Without a broker timestamp,
a stable permanent ID is required for a zero-fill terminal observation.
Execution IDs are deduplicated; conflicting duplicates remain unknown.

Consumers own bounded request timeouts on their private connection and durable
observation storage. They must keep financial records in protected storage and
mask identifiers in notices. Observations do not clear UNKNOWN execution claims,
release cash or risk reservations, or authorize another order. Adoption requires
a separately reviewed consumer revision; library tests do not prove deployment
or real broker behavior. Commission evidence that arrives after the consumer
freezes a terminal observation can remain unknown in that observation.
