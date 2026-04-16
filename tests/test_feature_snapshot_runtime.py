from __future__ import annotations

import unittest
from datetime import datetime, timezone
from typing import Any

from quant_platform_kit.common.feature_snapshot_runtime import (
    FeatureSnapshotContextRequest,
    FeatureSnapshotRuntimeSettings,
    evaluate_feature_snapshot_strategy,
)
from quant_platform_kit.strategy_contracts import (
    CallableStrategyEntrypoint,
    PositionTarget,
    StrategyContext,
    StrategyDecision,
    StrategyManifest,
    StrategyRuntimeAdapter,
    StrategyRuntimePolicy,
)


def _entrypoint() -> CallableStrategyEntrypoint:
    return CallableStrategyEntrypoint(
        manifest=StrategyManifest(
            profile="feature_snapshot_strategy",
            domain="us_equity",
            display_name="Feature Snapshot Strategy",
            description="test",
            required_inputs=frozenset({"feature_snapshot"}),
        ),
        _evaluate=lambda ctx: StrategyDecision(
            positions=(
                PositionTarget(
                    symbol=ctx.market_data["feature_snapshot"][0]["symbol"],
                    target_weight=1.0,
                ),
            ),
            diagnostics={"run_as_of": ctx.runtime_config.get("run_as_of")},
        ),
    )


class FeatureSnapshotRuntimeTests(unittest.TestCase):
    def test_fail_closes_when_path_missing(self) -> None:
        result = evaluate_feature_snapshot_strategy(
            entrypoint=_entrypoint(),
            runtime_adapter=StrategyRuntimeAdapter(status_icon="🧲"),
            runtime_settings=FeatureSnapshotRuntimeSettings(
                feature_snapshot_path=None,
                strategy_config_path="/tmp/config.json",
                strategy_config_source="env",
            ),
            runtime_config={},
            merged_runtime_config={"managed_symbols": ("AAPL", "BOXX")},
            base_managed_symbols=("AAPL", "BOXX"),
        )

        self.assertEqual(result.decision.risk_flags, ("no_execute",))
        self.assertEqual(result.metadata["snapshot_guard_decision"], "fail_closed")
        self.assertEqual(result.metadata["fail_reason"], "feature_snapshot_path_missing")
        self.assertEqual(result.metadata["status_icon"], "🛑")
        self.assertEqual(result.metadata["managed_symbols"], ("AAPL", "BOXX"))

    def test_loads_snapshot_into_context(self) -> None:
        observed: dict[str, Any] = {}
        as_of = datetime(2026, 4, 15, tzinfo=timezone.utc)

        def snapshot_loader(path: str, **kwargs: Any):
            observed["path"] = path
            observed["kwargs"] = kwargs
            return type(
                "GuardResult",
                (),
                {
                    "frame": [{"symbol": "AAPL", "close": 100.0}],
                    "metadata": {
                        "snapshot_guard_decision": "proceed",
                        "snapshot_as_of": "2026-04-15",
                    },
                },
            )()

        result = evaluate_feature_snapshot_strategy(
            entrypoint=_entrypoint(),
            runtime_adapter=StrategyRuntimeAdapter(
                status_icon="🧲",
                required_feature_columns=frozenset({"symbol", "close"}),
                managed_symbols_extractor=lambda *_args, **_kwargs: ("AAPL", "BOXX"),
                runtime_policy=StrategyRuntimePolicy(runtime_execution_window_trading_days=1),
            ),
            runtime_settings=FeatureSnapshotRuntimeSettings(
                feature_snapshot_path="gs://bucket/snapshot.csv",
                feature_snapshot_manifest_path="gs://bucket/snapshot.csv.manifest.json",
                dry_run_only=True,
            ),
            runtime_config={},
            merged_runtime_config={"safe_haven": "BOXX", "benchmark_symbol": "QQQ"},
            as_of=as_of,
            set_run_as_of=True,
            snapshot_loader=snapshot_loader,
        )

        self.assertEqual(observed["path"], "gs://bucket/snapshot.csv")
        self.assertEqual(observed["kwargs"]["run_as_of"], as_of)
        self.assertEqual(
            observed["kwargs"]["manifest_path"],
            "gs://bucket/snapshot.csv.manifest.json",
        )
        self.assertEqual(result.decision.positions[0].symbol, "AAPL")
        self.assertEqual(result.decision.diagnostics["run_as_of"], as_of)
        self.assertEqual(result.metadata["managed_symbols"], ("AAPL", "BOXX"))
        self.assertEqual(result.metadata["status_icon"], "🧲")
        self.assertIs(result.metadata["dry_run_only"], True)

    def test_supports_custom_context_builder(self) -> None:
        def snapshot_loader(_path: str, **_kwargs: Any):
            return type(
                "GuardResult",
                (),
                {
                    "frame": [{"symbol": "MSFT", "close": 200.0}],
                    "metadata": {"snapshot_guard_decision": "proceed"},
                },
            )()

        def build_inputs(frame):
            return {"custom_snapshot": frame}

        def context_builder(request: FeatureSnapshotContextRequest) -> StrategyContext:
            return StrategyContext(
                as_of=request.as_of,
                market_data={"feature_snapshot": request.available_inputs["custom_snapshot"]},
                runtime_config=request.runtime_config,
            )

        result = evaluate_feature_snapshot_strategy(
            entrypoint=_entrypoint(),
            runtime_adapter=StrategyRuntimeAdapter(status_icon="📏"),
            runtime_settings=FeatureSnapshotRuntimeSettings(feature_snapshot_path="/tmp/snapshot.csv"),
            runtime_config={},
            merged_runtime_config={},
            build_available_inputs=build_inputs,
            context_builder=context_builder,
            snapshot_loader=snapshot_loader,
        )

        self.assertEqual(result.decision.positions[0].symbol, "MSFT")

    def test_can_fail_close_entrypoint_errors(self) -> None:
        entrypoint = CallableStrategyEntrypoint(
            manifest=StrategyManifest(
                profile="feature_snapshot_strategy",
                domain="us_equity",
                display_name="Feature Snapshot Strategy",
                description="test",
                required_inputs=frozenset({"feature_snapshot"}),
            ),
            _evaluate=lambda _ctx: (_ for _ in ()).throw(RuntimeError("boom")),
        )

        def snapshot_loader(_path: str, **_kwargs: Any):
            return type(
                "GuardResult",
                (),
                {
                    "frame": [{"symbol": "AAPL", "close": 100.0}],
                    "metadata": {"snapshot_guard_decision": "proceed"},
                },
            )()

        result = evaluate_feature_snapshot_strategy(
            entrypoint=entrypoint,
            runtime_adapter=StrategyRuntimeAdapter(status_icon="📏"),
            runtime_settings=FeatureSnapshotRuntimeSettings(feature_snapshot_path="/tmp/snapshot.csv"),
            runtime_config={},
            merged_runtime_config={},
            snapshot_loader=snapshot_loader,
            catch_evaluation_errors=True,
        )

        self.assertEqual(result.decision.risk_flags, ("no_execute",))
        self.assertEqual(result.metadata["snapshot_guard_decision"], "fail_closed")
        self.assertEqual(
            result.metadata["fail_reason"],
            "feature_snapshot_compute_failed:RuntimeError:boom",
        )

    def test_raises_entrypoint_errors_by_default(self) -> None:
        entrypoint = CallableStrategyEntrypoint(
            manifest=StrategyManifest(
                profile="feature_snapshot_strategy",
                domain="us_equity",
                display_name="Feature Snapshot Strategy",
                description="test",
                required_inputs=frozenset({"feature_snapshot"}),
            ),
            _evaluate=lambda _ctx: (_ for _ in ()).throw(RuntimeError("boom")),
        )

        def snapshot_loader(_path: str, **_kwargs: Any):
            return type(
                "GuardResult",
                (),
                {
                    "frame": [{"symbol": "AAPL", "close": 100.0}],
                    "metadata": {"snapshot_guard_decision": "proceed"},
                },
            )()

        with self.assertRaisesRegex(RuntimeError, "boom"):
            evaluate_feature_snapshot_strategy(
                entrypoint=entrypoint,
                runtime_adapter=StrategyRuntimeAdapter(status_icon="📏"),
                runtime_settings=FeatureSnapshotRuntimeSettings(feature_snapshot_path="/tmp/snapshot.csv"),
                runtime_config={},
                merged_runtime_config={},
                snapshot_loader=snapshot_loader,
            )


if __name__ == "__main__":
    unittest.main()
