# 跨资产 Research Driver 契约

## 目标与边界

`research_driver_terminal.v1` 为 US、CN、HK、Crypto 提供相同的 P1–P3 研究终态。它只汇总已经生成并验证过的 artifact 身份，不抓取数据、不执行回测、不读取策略 catalog，也不接入 broker。

固定边界：

```text
P1 research input manifest
→ P2 strategy config freeze
→ P3 strategy evidence package
→ READY / DEFERRED / PARKED terminal artifact
```

每次有合法的 run/strategy/candidate 身份时都必须生成 terminal artifact：

- 三个阶段均有有效 artifact：`READY`；
- artifact 尚未生成或正常等待上游：`DEFERRED`；
- artifact 格式错误、摘要错误或越过上游依赖：`PARKED`；
- 任意结果始终为 `no_order=true`、`permission_effect=none`。

## 证据要求

| 阶段 | READY 所需 artifact | 说明 |
|---|---|---|
| P1 | `research_input_manifest.v1` | 由现有 P1 validator 校验后提供身份与 SHA-256 |
| P2 | `strategy_config_freeze.v1` | 冻结候选配置的身份与 SHA-256 |
| P3 | `strategy_evidence_package.v2` | 由现有 P3 validator 校验后提供身份与 SHA-256 |

`catalog_status`、`runtime_enabled`、inventory 条目或网页显示都不是证据。契约不接受这些字段，并固定输出 `catalog_status_used_as_evidence=false`。

## 生产者用法

```python
from quant_platform_kit.strategy_lifecycle import (
    build_ready_research_stage,
    build_research_driver_terminal_artifact,
)

terminal = build_research_driver_terminal_artifact(
    run_id="daily-2026-08-24",
    generated_at="2026-08-24T22:00:00+08:00",
    strategy_id="example_strategy",
    candidate_id="candidate-001",
    domain="cn_equity",
    p1_input=build_ready_research_stage(
        "p1_input", artifact_id="manifest-001", artifact_sha256="a" * 64
    ),
    p2_freeze=build_ready_research_stage(
        "p2_freeze", artifact_id="freeze-001", artifact_sha256="b" * 64
    ),
    p3_evidence=None,
)
assert terminal["terminal_status"] == "DEFERRED"
assert terminal["no_order"] is True
```

生产 workflow 应在正常、跳过、依赖缺失和失败分支的 finally/always 步骤中写出该 JSON。这个契约不会自动把 `READY` 提升为 shadow、paper 或 live；后续生命周期消费者仍需独立验证 artifact 与权限。

## 迁移风险

- 旧策略可先只写 `DEFERRED`，不需要伪造 P1/P2/P3 完成状态。
- domain 仅允许 `us_equity`、`cn_equity`、`hk_equity`、`crypto`。
- 该模块不替代 P1/P3 原始 validator；它只绑定验证后的不可变身份。
- 不允许用 catalog/inventory 状态填充 READY，也不允许从该 artifact 推导交易权限。
