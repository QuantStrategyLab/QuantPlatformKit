# Package Architecture Boundaries

Local rules for `src/quant_platform_kit/`, complementing the root `AGENTS.md`.

## Pure Contract vs Edge-Adapter Split

- **Pure contract and domain modules** (`common`, `schemas`, `strategy_spec`,
  `risk`, `strategy_lifecycle.contracts`): define schemas, domain models,
  validation, and port interfaces. Do not import edge/adapter subpackages or
  external broker/cloud SDKs at module or runtime scope.
- **Edge and adapter subpackages** (`binance`, `ibkr`, `longbridge`, `schwab`,
  `quantconnect`, `cloud`, `notifications`): implement broker clients, cloud
  storage/runtime bindings, and notification delivery. Keep SDK imports
  (`ib_insync`, `ibapi`, `longport`, `binance`, `ccxt`, `boto3`, `google.cloud`,
  `azure`) confined here or injected behind pure ports.

## Enforcement and Verification

- Boundary test: [tests/test_architecture_boundaries.py](../../tests/test_architecture_boundaries.py)
  checks pure modules with Python `ast`. Do not add entries to
  `LEGACY_EDGE_IMPORTS`; remove exemptions as legacy imports move behind ports.
- Facade guard: [tests/test_common_facade_imports.py](../../tests/test_common_facade_imports.py)
  and [scripts/check_common_facade_imports.py](../../scripts/check_common_facade_imports.py)
  keep `common/__init__.py` bounded; place new APIs in focused subpackages.
- After changing imports here, run:
  `python3 -m pytest -q tests/test_architecture_boundaries.py`
