# Changelog

All notable changes to `QuantPlatformKit` are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- Credential-free, immutable `NotificationIntent` and report-safe Telegram
  receipts while retaining existing sender interfaces.
- Structured, JSON, token-literal, and chained-exception redaction helpers,
  plus idempotent logging filters and optional stdout/stderr text redaction.

### Changed

- Extended default Gitleaks rules with keyword-independent Telegram token
  detection for pre-commit, PR/main checks, and weekly full-history scans.
- Consumer adoption requires a QPK pin update; hand-built Telegram sends will
  be migrated separately.
