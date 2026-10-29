# Specification index

[English README](../README.md) · [中文 README](../README.zh-CN.md)

Read documents at the library revision used by your consumer. These are source-level specifications and design references, not evidence of deployed versions or permission to trade.

## Architecture and implementation

- [Architecture](ARCHITECTURE.md) ([中文](ARCHITECTURE.zh-CN.md)): [layers](ARCHITECTURE.md#2-layer-descriptions), [data flow](ARCHITECTURE.md#3-data-flow), [design patterns](ARCHITECTURE.md#4-design-patterns), [naming](ARCHITECTURE.md#5-naming-conventions), [dependencies](ARCHITECTURE.md#6-dependency-graph) and [cross-cutting concerns](ARCHITECTURE.md#7-cross-cutting-concerns).
- [Development standard: English overview](design-spec-overview.md) · [complete Chinese v1.0 standard](design-spec.md): platform/strategy development, configuration, monitoring, security and checklists. The v1.0 plugin examples are historical; see the compatibility section below before reading mount examples.
- [Strategy-platform configuration](strategy-platform-spec.md): [source of truth](strategy-platform-spec.md#single-source-of-truth), [strategies](strategy-platform-spec.md#adding-a-new-strategy), [platforms](strategy-platform-spec.md#adding-a-new-platform), [validation](strategy-platform-spec.md#configuration-validation) and [scheduler timezones](strategy-platform-spec.md#scheduler-timezone-rules). Legacy plugin/config-sync examples must be read with the historical boundary below.

## Runtime contracts

- [Platform repository boundaries](platform-repo-boundaries.md) ([中文](platform-repo-boundaries.zh-CN.md)).
- [Lifecycle policy](strategy-lifecycle-policy.md) ([中文](strategy-lifecycle-policy.zh-CN.md)).
- [Paper execution consumer](paper-execution-command-consumer.md), [portfolio action matrix](strategy-portfolio-action-matrix.md) and [evidence package](evidence-package-template.md).

## Historical compatibility

- [Legacy plugin runtime contract](strategy-plugin-runtime-contract.md) ([中文](strategy-plugin-runtime-contract.zh-CN.md)): **HISTORICAL / no authority effect**. Retained for replay and migration troubleshooting; not the current platform-mount specification.
- Automatic name-based `latest_signal.json` mounts are retired. V2 observation/notification evidence does not enable Paper/Live or establish P4–P6 eligibility. A runnable composite candidate needs its own bound revisions, inputs, portfolio rules and P1–P3/target-channel evidence, as stated in the linked contract.

Provider rights, credential restrictions, risk controls and the repository [license](../LICENSE) remain applicable.
