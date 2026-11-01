# Alpaca public market data collection

The `Fetch Alpaca public market data` workflow collects raw public market data
from the Alpaca data API (`data.alpaca.markets`). It is a manual collection aid
for research inputs. It is not part of any trading, risk or deployment path.

## Behaviour

- Trigger: `workflow_dispatch` only. There is no schedule and no automatic run.
- Permissions: `contents: read`. The job issues GET requests only, to
  `data.alpaca.markets` over HTTPS, and refuses redirects.
- Queries: [`scripts/alpaca_public_market_data_queries.json`](../scripts/alpaca_public_market_data_queries.json)
  lists raw SIP daily bars and corporate actions per symbol. Change the config
  to change what is collected; the script has no query logic of its own.
- Supplemental `actions-all-<symbol>` queries cover the continuation and overlap
  window with `data_quality=all`, retaining early incomplete events separately
  from the existing full-history queries. No action-type filter is applied, so
  capital-gain distributions and split variants remain visible for review.
- Pagination: every non-empty `next_page_token` is followed. A repeated token,
  a non-200 response or a non-JSON body marks the query failed and the run
  exits non-zero; the partial output is still uploaded for inspection.
- Output: each response page is stored byte for byte under `<query-id>/`,
  together with `manifest.json` (redacted request and page receipts) and
  `SHA256SUMS`.
- Artifact: uploaded as `alpaca-public-market-data-<run id>` and kept for 7 days.
  Copy anything that must be retained into approved protected storage; raw data
  is not committed to Git.

## Corporate-action evidence limits

The [Alpaca corporate-actions reference](https://docs.alpaca.markets/us/reference/corporateactions-1)
states that the default `data_quality=complete` excludes unprocessed incomplete
events. Processed events can still have missing fields. `data_quality=all`
exposes those early records; it does not certify that a ledger is complete.

The manifest's `complete` and `all_complete` flags describe HTTP pagination
only. Keep both query families as separate observations rather than adding
their events together. Reconcile event IDs and economic actions before use;
preserve missing fields as unknown. An event ID, process date or retrieval
timestamp is not a provider revision ID. Neither query proves revision history,
historical availability, currency/share units or the absence of an action.
Research admission still requires its existing independent evidence checks.

## Before dispatching

Add two repository Actions secrets: `ALPACA_API_KEY_ID` and
`ALPACA_API_SECRET_KEY`. The workflow masks both values and fails before any
request if either is empty. Credentials are read from the environment only and
are never written to the output.

## Local check

```bash
PYTHONPATH=src python -m pytest -q tests/test_fetch_alpaca_public_market_data.py
```

The unit tests use a mocked HTTP layer and make no network requests.

Whether the account is entitled to the SIP feed is not verified by this change;
an entitlement failure appears as a recorded HTTP status in `manifest.json`.
