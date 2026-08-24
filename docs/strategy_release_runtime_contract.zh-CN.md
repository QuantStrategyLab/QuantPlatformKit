# 策略发布与运行时回执契约（v1）

`StrategyReleaseManifest` 是策略、配置、风险规则、证据和插件包的不可变发布记录。它不是一次回测结果，也不能单独授权交易。

每个运行实例仅接收精简的 `StrategyReleaseIdentity`。运行报告始终包含 `runtime_release_receipt`：

- `self_attested`：该进程已加载完整 release identity；这不是跨平台一致性的结论。
- `legacy_unattested`：旧运行实例没有 release identity。监控必须将其作为迁移缺口，而不能把空版本当成正常。

在后续命令门上线前，旧实例仍保持现有执行语义；但是任何风险增加型的新发布不得以 `legacy_unattested` 状态进入 ACTIVE。

插件 V2 可以把影子信号提供给策略做展示、诊断和研究。共享库注入快照的副本会把所有下单、仓位和 allocation 授权明确降为 `false`，原始 artifact 仍由 `StrategyPluginSignal.payload` 保留用于审计。插件自身不能借由 metadata 授权策略改仓。

跨平台发布必须依次满足：所有目标预装同一 release、所有运行时回传相同 identity、统一交易日生效、观察期完成。任何一个目标缺回执或 digest 不符，发布不得进入 ACTIVE。
