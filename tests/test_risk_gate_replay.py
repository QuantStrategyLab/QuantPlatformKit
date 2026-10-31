from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

from quant_platform_kit.common.strategy_contracts import PositionTarget, StrategyDecision
from quant_platform_kit.risk.gate import apply_risk_gate, assess_with_evidence
from quant_platform_kit.risk.gate.replay import ReplayRiskGateResult, replay_apply_risk_gate, replay_assess_with_evidence
from quant_platform_kit.risk.contracts import RiskAction
from quant_platform_kit.risk.engine import build_risk_engine
from test_risk_gate import _capital_base, _capital_base_binding, CanonicalRiskMetadataSanitizationTests


def test_replay_matches_live_static_gate_at_same_time_and_repeats():
    now = datetime(2026, 4, 17, 12, tzinfo=timezone.utc)
    decision = StrategyDecision(positions=(PositionTarget("QQQ", target_value=1000.0),))
    kwargs = {"enforce_value_target_exposure": True, "capital_base": _capital_base(as_of=now),
              "capital_base_binding": _capital_base_binding(), "portfolio_snapshot": {"total_equity": 100000.0},
              "market_data": {}, "product_leverage_factors": {"QQQ": 1}}
    with patch("quant_platform_kit.risk.gate._utc_now", return_value=now):
        live = apply_risk_gate(decision, **kwargs)
    result = replay_apply_risk_gate(decision, evaluation_time=now, **kwargs)
    assert live.diagnostics["risk_gate"] == "APPROVE"
    assert live.positions[0].target_value == 1000.0
    assert result.decision_record == asdict(live)
    assert result == replay_apply_risk_gate(decision, evaluation_time=now, **kwargs)
    assert result.executable is False
    assert result.scope == "research_only" and result.provenance_status == "unverified"
    with pytest.raises(TypeError):
        ReplayRiskGateResult(result.evaluation_time, result.decision_record, executable=True)
    assert apply_risk_gate(result).diagnostics["risk_gate"] == "REJECT"


def test_real_engine_rejected_position_matches_live():
    now = datetime(2026, 4, 17, 12, tzinfo=timezone.utc)
    decision = StrategyDecision(positions=(PositionTarget("QQQ", target_weight=0.9),))
    kwargs = {"portfolio_snapshot": {"total_equity": 100000.0}, "market_data": {}, "max_single_weight": 0.5,
              "product_leverage_factors": {"QQQ": 1}}
    with patch("quant_platform_kit.risk.gate._utc_now", return_value=now):
        live = apply_risk_gate(decision, **kwargs)
    replay = replay_apply_risk_gate(decision, evaluation_time=now, **kwargs)
    assert live.diagnostics["risk_gate"] == "REJECT"
    assert live.positions == ()
    assert live.risk_flags == ("rejected:concentration",)
    assert replay.decision_record == asdict(live)


@pytest.mark.parametrize("time", [None, datetime(2020, 1, 1), datetime(2020, 1, 1, tzinfo=timezone.utc).replace(microsecond=1)])
def test_replay_rejects_invalid_clock(time):
    with pytest.raises(ValueError):
        replay_apply_risk_gate(StrategyDecision(), evaluation_time=time)


def test_replay_enforces_historical_capital_freshness_and_live_clock_remains_guarded():
    now = datetime(2020, 1, 3, 12, tzinfo=timezone.utc)
    decision = StrategyDecision(positions=(PositionTarget("QQQ", target_value=1000.0),))
    kwargs = {"enforce_value_target_exposure": True, "capital_base_binding": _capital_base_binding()}
    for source_time in (now - timedelta(seconds=301), now + timedelta(seconds=1)):
        result = replay_apply_risk_gate(decision, evaluation_time=now, capital_base=_capital_base(as_of=source_time), **kwargs)
        assert result.decision_record["risk_flags"] == ("rejected:capital_base",)
    with patch("quant_platform_kit.risk.gate._utc_now", return_value=datetime(2026, 1, 1, tzinfo=timezone.utc)):
        live = assess_with_evidence(decision, {}, scope="MEMBER", mandate_provenance=None,
                                    market_data={}, logical_evaluation_time=now)
    assert "stale_logical_evaluation_time" in live.assessment.reason_codes


def test_evidence_replay_matches_live_and_enforces_mandate_window():
    fixture = CanonicalRiskMetadataSanitizationTests
    now = fixture._NOW
    decision = StrategyDecision(positions=(PositionTarget("XLK", target_weight=0.1),))
    kwargs = {"scope": "MEMBER", "mandate_provenance": fixture._mandate(),
              "market_data": {}, "candidate_identity": fixture._candidate()}
    engine = Mock()
    engine.assess.return_value = RiskAction(action="approve", reason="passed")
    with patch("quant_platform_kit.risk.gate._utc_now", return_value=now), \
            patch("quant_platform_kit.risk.gate.build_risk_engine", return_value=engine):
        live = assess_with_evidence(decision, fixture._SNAPSHOT, **kwargs)
        replay = replay_assess_with_evidence(decision, fixture._SNAPSHOT, evaluation_time=now, **kwargs)
        assert replay.decision_record == asdict(live.decision)
        assert replay.assessment_record == asdict(live.assessment)
        assert replay.executable is False
        for mandate in (fixture._mandate(effective_at="2026-08-04T04:29:00Z"),
                        fixture._mandate(expires_at="2026-08-04T04:27:59Z")):
            changed = {**kwargs, "mandate_provenance": mandate}
            blocked = replay_assess_with_evidence(decision, fixture._SNAPSHOT, evaluation_time=now, **changed)
            assert blocked.assessment_record["outcome"] == "REJECT"


def test_engine_failure_matches_live_rejection():
    now = datetime(2026, 4, 17, 12, tzinfo=timezone.utc)
    decision = StrategyDecision(positions=(PositionTarget("QQQ", target_weight=0.2),))
    with patch("quant_platform_kit.risk.gate._utc_now", return_value=now), \
            patch("quant_platform_kit.risk.gate.build_risk_engine", side_effect=RuntimeError("unavailable")):
        live = apply_risk_gate(decision)
        replay = replay_apply_risk_gate(decision, evaluation_time=now)
        assert replay.decision_record == asdict(live)
        assert live.diagnostics["risk_gate"] == "REJECT"
        fixture = CanonicalRiskMetadataSanitizationTests
        kwargs = {"scope": "MEMBER", "mandate_provenance": fixture._mandate(),
                  "market_data": {}, "candidate_identity": fixture._candidate()}
        evidence_live = assess_with_evidence(decision, fixture._SNAPSHOT, **kwargs)
        evidence_replay = replay_assess_with_evidence(decision, fixture._SNAPSHOT, evaluation_time=now, **kwargs)
        assert evidence_replay.decision_record == asdict(evidence_live.decision)
        assert evidence_replay.assessment_record == asdict(evidence_live.assessment)
        assert evidence_live.assessment.outcome == "REJECT"


def test_evidence_replay_with_real_engine_approves_nonempty_decision():
    fixture = CanonicalRiskMetadataSanitizationTests
    decision = StrategyDecision(positions=(PositionTarget("XLK", target_weight=0.1),))
    kwargs = {"scope": "MEMBER", "mandate_provenance": fixture._mandate(),
              "market_data": {}, "candidate_identity": fixture._candidate()}
    with patch("quant_platform_kit.risk.gate._utc_now", return_value=fixture._NOW):
        live = assess_with_evidence(decision, fixture._SNAPSHOT, **kwargs)
    replay = replay_assess_with_evidence(decision, fixture._SNAPSHOT, evaluation_time=fixture._NOW, **kwargs)
    assert live.assessment.outcome == "APPROVE"
    assert live.decision.positions[0].target_weight == 0.1
    assert replay.decision_record == asdict(live.decision)
    assert replay.assessment_record == asdict(live.assessment)


def test_replay_calls_real_engine_once_per_path():
    fixture = CanonicalRiskMetadataSanitizationTests
    decision = StrategyDecision(positions=(PositionTarget("XLK", target_weight=0.1),))
    engine = build_risk_engine()
    with patch.object(engine, "assess", wraps=engine.assess) as assess, \
            patch("quant_platform_kit.risk.gate.build_risk_engine", return_value=engine):
        replay_apply_risk_gate(decision, evaluation_time=fixture._NOW,
                               portfolio_snapshot=fixture._SNAPSHOT, product_leverage_factors={"XLK": 1})
        assert assess.call_count == 1
        assess.reset_mock()
        replay_assess_with_evidence(decision, fixture._SNAPSHOT, evaluation_time=fixture._NOW,
            scope="MEMBER", mandate_provenance=fixture._mandate(), market_data={}, candidate_identity=fixture._candidate())
        assert assess.call_count == 1


def test_live_static_gate_explicit_clock_requires_fresh_utc_and_records_it():
    now = datetime(2026, 4, 17, 12, tzinfo=timezone.utc)
    decision = StrategyDecision(positions=(PositionTarget("QQQ", target_weight=0.05),))
    kwargs = {"portfolio_snapshot": {"total_equity": 100000.0}, "product_leverage_factors": {"QQQ": 1}}
    with patch("quant_platform_kit.risk.gate._utc_now", return_value=now):
        accepted = apply_risk_gate(decision, logical_evaluation_time=now, **kwargs)
        assert accepted.diagnostics["risk_gate"] == "APPROVE"
        assert accepted.diagnostics["risk_gate_evaluated_at"] == "2026-04-17T12:00:00Z"
        for invalid in (now + timedelta(seconds=1), now - timedelta(days=1), now.replace(tzinfo=None)):
            rejected = apply_risk_gate(decision, logical_evaluation_time=invalid, **kwargs)
            assert rejected.diagnostics["risk_gate"] == "REJECT"
    with pytest.raises(TypeError):
        replay_apply_risk_gate(decision, evaluation_time=now, logical_evaluation_time=now, **kwargs)
