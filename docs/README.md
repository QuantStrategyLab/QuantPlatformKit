# Specification index

[English README](../README.md) · [中文 README](../README.zh-CN.md)

Read documents at the library revision used by your consumer. These are source-level specifications and design references, not evidence of deployed versions or permission to trade.

## Architecture and implementation

- [Architecture](ARCHITECTURE.md) ([中文](ARCHITECTURE.zh-CN.md)): [layers](ARCHITECTURE.md#2-layer-descriptions), [data flow](ARCHITECTURE.md#3-data-flow), [design patterns](ARCHITECTURE.md#4-design-patterns), [naming](ARCHITECTURE.md#5-naming-conventions), [dependencies](ARCHITECTURE.md#6-dependency-graph) and [cross-cutting concerns](ARCHITECTURE.md#7-cross-cutting-concerns).
- [Development standard: English overview](DESIGN_SPEC.en.md) · [complete Chinese v1.0 standard](DESIGN_SPEC.md): platform/strategy development, configuration, monitoring, security and checklists. The v1.0 plugin examples are historical; see the compatibility section below before reading mount examples.
- [Strategy-platform configuration](STRATEGY_PLATFORM_SPEC.md): [source of truth](STRATEGY_PLATFORM_SPEC.md#single-source-of-truth), [strategies](STRATEGY_PLATFORM_SPEC.md#adding-a-new-strategy), [platforms](STRATEGY_PLATFORM_SPEC.md#adding-a-new-platform), [validation](STRATEGY_PLATFORM_SPEC.md#configuration-validation) and [scheduler timezones](STRATEGY_PLATFORM_SPEC.md#scheduler-timezone-rules). Legacy plugin/config-sync examples must be read with the historical boundary below.

## Runtime contracts

- [Platform repository boundaries](platform_repo_boundaries.md) ([中文](platform_repo_boundaries.zh-CN.md)).
- [Lifecycle policy](strategy_lifecycle_policy.md) ([中文](strategy_lifecycle_policy.zh-CN.md)).
- [Paper execution consumer](paper_execution_command_consumer.md), [portfolio action matrix](strategy_portfolio_action_matrix.md) and [evidence package](evidence_package_template.md).

## Historical compatibility

- [Legacy plugin runtime contract](strategy_plugin_runtime_contract.md) ([中文](strategy_plugin_runtime_contract.zh-CN.md)): **HISTORICAL / no authority effect**. Retained for replay and migration troubleshooting; not the current platform-mount specification.
- Automatic name-based `latest_signal.json` mounts are retired. V2 observation/notification evidence does not enable Paper/Live or establish P4–P6 eligibility. A runnable composite candidate needs its own bound revisions, inputs, portfolio rules and P1–P3/target-channel evidence, as stated in the linked contract.

Provider rights, credential restrictions, risk controls and the repository [license](../LICENSE) remain applicable.
