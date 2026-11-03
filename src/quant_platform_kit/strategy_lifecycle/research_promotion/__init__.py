"""Research promotion implementation package."""

from __future__ import annotations

from .budget import enforce_optimization_budget, enforce_promotion_backtest_gates
from .console_client import (
    apply_console_research_promotion_decision,
    make_console_research_promotion_pull,
    make_console_research_promotion_sync,
    reconcile_saved_research_promotion_ticket,
)
from .cycle import (
    decide_saved_research_promotion_ticket,
    open_awaiting_human_ticket,
    run_research_promotion_cycle,
    run_saved_research_promotion_cycle,
)
from .models import (
    DEFAULT_SUGGESTED_RISK_PROFILE,
    EXECUTION_MODES,
    RISK_PROFILE_IDS,
    NewResearchRequest,
    PromotionConfirmation,
    ResearchPromotionBudget,
    ResearchPromotionState,
    ResearchPromotionTicket,
    apply_human_promotion_decision,
    shadow_record_from_paired_evidence,
    validate_promotion_confirmation,
)
from .notifications import (
    build_human_promotion_notification,
    make_telegram_research_promotion_notifier,
)
from .store import load_research_promotion_ticket, save_research_promotion_ticket

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
