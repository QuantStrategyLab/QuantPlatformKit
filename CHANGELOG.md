# Changelog

## Unreleased

- Add credential-free, immutable `NotificationIntent` and report-safe Telegram
  receipts while retaining the existing sender interfaces.
- Export structured, JSON, token-literal and chained-exception redaction helpers,
  plus idempotent logging filters and optional stdout/stderr text redaction.
- Extend default Gitleaks rules with keyword-independent Telegram token detection
  for pre-commit, PR/main checks and weekly full-history scans across branches.
- Consumer adoption requires a QPK pin update; hand-built Telegram sends will be
  migrated separately.
