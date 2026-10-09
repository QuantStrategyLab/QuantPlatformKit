# B06：value-target 执行 API 与展示布局分离（第一刀）

## 做了什么
- 新增 `quant_platform_kit.common.presentation`：
  - `ValueTargetExecutionSemantics`（阈值/时序/数值）
  - `ValueTargetDisplayAnnotations`（文案）
  - `ValueTargetPlanPresentation`（`portfolio_rows_layout` / `execution_fields`）
- 新增 `build_value_target_execution_runtime_plan`：**不**在签名上接收 dashboard 布局 kwargs
- 保留 `build_value_target_runtime_plan` 为兼容 facade（旧 kwargs → Presentation）

## 未做（follow-up）
- 未删除 `ValueTargetExecutionAnnotations` 混合字段；未迁移平台 `decision_mapper` 调用方
- 未把 SOXL 公式移出 `runtime_inputs.py`（属 B03/B07）
- 未改阈值/数量/时序数值行为

## 验证
`pytest tests/test_strategy_contracts.py tests/test_value_target_presentation_facade.py`
