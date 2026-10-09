# B06 / N05：value-target 执行 API 与展示布局分离

## 已做

### 第一刀（QPK #654）
- 新增 `quant_platform_kit.common.presentation`：
  - `ValueTargetExecutionSemantics`（阈值/时序/数值）
  - `ValueTargetDisplayAnnotations`（文案）
  - `ValueTargetPlanPresentation`（`portfolio_rows_layout` / `execution_fields`）
- 新增 `build_value_target_execution_runtime_plan`：**不**在签名上接收 dashboard 布局 kwargs
- 保留 `build_value_target_runtime_plan` 为兼容 facade（旧 kwargs → Presentation）

### 第二刀（本 PR：annotations 展示字段归属）
- 明确 `VALUE_TARGET_DISPLAY_FIELD_NAMES` 为展示字段真源
- 新增 `split_value_target_annotation_parts` / `resolve_value_target_execution_annotations`
- `build_value_target_execution_runtime_plan` 支持首选 `semantics=` + `display=`
- `build_value_target_execution_annotations` 内部改为 split→merge（行为等价）
- `ValueTargetExecutionAnnotations` **仍保留混合字段**作为 wire/compat aggregate（batch-upgrade-then-remove；删字段等 B12 采用证据）

## 未做
- 未从 `ValueTargetExecutionAnnotations` **删除**展示字段（B03：消费者迁移未齐前禁止）
- 未迁移 LongBridge / Firstrade `decision_mapper`（禁区）
- 未把 SOXL 公式移出 `runtime_inputs.py`（B03/B07）

## 验证
`pytest tests/test_strategy_contracts.py tests/test_value_target_presentation_facade.py`

## B12
见 `docs/b12_consumer_adoption.zh-CN.md`（消费者采用矩阵；LB/Firstrade 剩余）。
