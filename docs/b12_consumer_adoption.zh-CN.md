# B12：value-target 消费者采用矩阵（2026-10-09）

依据：本地 clone `rg`（gh code search 本会话 rate-limit；Alpaca 等未 clone 仓标 incomplete）。  
策略：batch-upgrade-then-remove-compat；**保留** `build_value_target_runtime_plan` 与混合 `ValueTargetExecutionAnnotations` facade，直至剩余生产消费者清零。

## 1. 已迁到 `semantics` + `display` / execution API

| 仓 | 路径 | 证据 |
| --- | --- | --- |
| CharlesSchwabPlatform | `decision_mapper.py` | [#501](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/pull/501) → `build_value_target_execution_runtime_plan` + `ValueTargetPlanPresentation`；[#504](https://github.com/QuantStrategyLab/CharlesSchwabPlatform/pull/504) → `semantics=` + `display=`（pin QPK #655） |
| QuantPlatformKit | `tests/test_value_target_presentation_facade.py` + `tests/test_strategy_contracts.py` | #654/#655；本 PR 将 contracts 单测改为 modern 优先 + legacy 等价 |

## 2. 无 `ValueTargetExecutionAnnotations` / `build_value_target_runtime_plan` 生产调用（本批本地）

| 仓 | 说明 |
| --- | --- |
| InteractiveBrokersPlatform | `decision_mapper` 用 `translate_decision_to_target_mode`；annotations 为 dict metadata，非 ValueTarget 类型 |
| BinancePlatform | `decision_mapper` 无 value-target plan builder |
| QmtPlatform（本地） | 无上述符号 |
| UsEquityStrategies | 无上述符号（dashboard 走 diagnostics dict） |
| QuantRuntimeSettings | JS Worker；不消费该 Python API |

## 3. 剩余生产消费者（**本侧不迁**）

| 仓 | 符号 | 原因 |
| --- | --- | --- |
| LongBridgePlatform | `build_value_target_runtime_plan` + `ValueTargetExecutionAnnotations(...)` | LB-HK 禁区；归 quant |
| FirstradePlatform | 同上 | Firstrade Environment/ingress 禁区；归 quant |

## 4. Facade 保留条件

- 新代码：`build_value_target_execution_runtime_plan(semantics=, display=, presentation=)`  
- 旧代码：`build_value_target_runtime_plan` / `annotations=ValueTargetExecutionAnnotations(...)`  
- **删除混合字段 / 撤 facade**：仅当 §3 清零且 B12 矩阵绿灯（N14）

## 5. incomplete

- gh `search/code` org 查询本会话 **0 / rate-limit**；未对 AlpacaPlatform / 未 clone 仓做全文确认。限流恢复后补扫：`org:QuantStrategyLab build_value_target_runtime_plan`。
