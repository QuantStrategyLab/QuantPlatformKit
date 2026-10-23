"""Research promotion cycle: drift → bounded reopt → shadow evidence → human gate.

This control plane may prepare non-live candidates and notify operators. It must
never enable live trading, enlarge capital, or treat AI/reviewer verdicts as
deployment authority.

The implementation lives in :mod:`quant_platform_kit.strategy_lifecycle.research_promotion`.
This module re-exports the original names so existing import paths are unchanged.
"""

from __future__ import annotations

import calendar
import copy
import hashlib
import json
import math
import re
import uuid
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from quant_platform_kit.strategy_lifecycle.candidate_control import ResearchSourceReceiptRef
from quant_platform_kit.strategy_lifecycle.contracts import (
    DriftResult,
    DriftStatus,
    OptimizationProposal,
    PromotionBacktestRun,
)

from .research_promotion.budget import (
    _add_calendar_months,
    _promotion_backtest_evidence_mapping,
    enforce_optimization_budget,
    enforce_promotion_backtest_gates,
)
from .research_promotion.console_client import (
    _canonical_ticket_value,
    _default_research_promotion_pull_url,
    _reconcile_saved_research_promotion_ticket,
    _require_matching_console_promotion_candidate,
    apply_console_research_promotion_decision,
    make_console_research_promotion_pull,
    make_console_research_promotion_sync,
    reconcile_saved_research_promotion_ticket,
)
from .research_promotion.cycle import (
    _DIGIT_RE,
    _HAN_RE,
    _LATIN_RE,
    _MAX_IDLE_DAYS,
    _MAX_NO_IMPROVEMENT_ROUNDS,
    _RESEARCH_OWNER_FIELDS,
    _RESEARCH_OWNER_KEY_RE,
    _REPOSITORY_RE,
    _SUMMARY_LOCALE_FIELDS,
    _SUMMARY_MAX_TEXT,
    _SUMMARY_NEW_KEYS,
    _SUMMARY_OLD_KEYS,
    _SUMMARY_PROVIDERS,
    _SUMMARY_SEGMENT_MAX,
    _SUMMARY_TASK_KEYS,
    _ResearchScopeArchived,
    _accepted_summary_explanation,
    _archive_ticket,
    _attach_research_summary,
    _attach_shadow_or_park,
    _bilingual_summary_explanation,
    _candidate_summary_binding,
    _deliver_awaiting_human_ticket,
    _exact_identity,
    _exact_key,
    _lifecycle,
    _normalize_research_owner,
    _parse_progress_time,
    _pause_progress,
    _progress_now,
    _proposal_comparable,
    _proposal_no_improvement,
    _record_no_improvement,
    _same_ticket_material,
    _saved_exact_record,
    _saved_proposal,
    _saved_scope_records,
    _scope_identity,
    _scope_is_protected,
    _scope_key,
    _scope_lifecycle,
    _summary_context,
    _summary_segment,
    _touch_progress,
    decide_saved_research_promotion_ticket,
    open_awaiting_human_ticket,
    run_research_promotion_cycle,
    run_saved_research_promotion_cycle,
)
from .research_promotion.models import (
    DEFAULT_SUGGESTED_RISK_PROFILE,
    EXECUTION_MODES,
    RISK_PROFILE_IDS,
    NewResearchRequest,
    PromotionConfirmation,
    ResearchPromotionBudget,
    ResearchPromotionState,
    ResearchPromotionTicket,
    _ACTIVE_DRIFT,
    _REAL_DATETIME,
    _RESEARCH_CANDIDATE_RECOMMENDATIONS,
    _TERMINAL,
    _clock_now,
    _is_paired_shadow_kind,
    _new_ticket_id,
    _now_iso,
    _shadow_kind,
    apply_human_promotion_decision,
    shadow_record_from_paired_evidence,
    validate_promotion_confirmation,
)
from .research_promotion.notifications import (
    build_human_promotion_notification,
    make_telegram_research_promotion_notifier,
)
from .research_promotion.store import (
    _research_directory_lock,
    load_research_promotion_ticket,
    save_research_promotion_ticket,
)


__all__ = [
    "DEFAULT_SUGGESTED_RISK_PROFILE",
    "EXECUTION_MODES",
    "PromotionConfirmation",
    "RISK_PROFILE_IDS",
    "ResearchPromotionBudget",
    "NewResearchRequest",
    "ResearchPromotionState",
    "ResearchPromotionTicket",
    "apply_console_research_promotion_decision",
    "apply_human_promotion_decision",
    "build_human_promotion_notification",
    "decide_saved_research_promotion_ticket",
    "enforce_optimization_budget",
    "enforce_promotion_backtest_gates",
    "load_research_promotion_ticket",
    "make_console_research_promotion_pull",
    "make_console_research_promotion_sync",
    "make_telegram_research_promotion_notifier",
    "open_awaiting_human_ticket",
    "reconcile_saved_research_promotion_ticket",
    "run_research_promotion_cycle",
    "run_saved_research_promotion_cycle",
    "save_research_promotion_ticket",
    "shadow_record_from_paired_evidence",
    "validate_promotion_confirmation",
]
