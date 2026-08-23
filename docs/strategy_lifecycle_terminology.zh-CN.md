# 新量化系统生命周期术语

新系统不再把 `research-only` 理解为“停止开发”。它表示策略仍可由自动化研究系统持续处理，但尚未获得交易权限。

| 状态 | 允许 | 不允许 |
|---|---|---|
| `research_active` | 历史回测、参数优化、组合分析、AI 研究、候选版本 | 真实下单 |
| `shadow_active` | 使用未来数据运行 shadow/forward、漂移监测 | 真实资金和 broker order |
| `paper_active` | 模拟账户运行（平台支持时） | 真实资金 |
| `live_candidate` | 准备 live 包、风险检查和通知 | 自动开启真实交易 |
| `live_enabled` | 按已批准权限运行 | 超越 Risk Gate 或自动扩大权限 |

生命周期状态只是对阶段的描述，不是权限来源。即使 catalog 或 inventory
写着 `live_enabled`，执行层仍必须独立验证未过期的部署授权、账户与 broker
权限、中央 Risk Gate 和当前风险额度。任何清单都不得据此自动推导下单权限。

## 旧状态兼容映射

| 旧 catalog 状态 | 新系统读取结果 | 说明 |
|---|---|---|
| `research_backtest_only` | `research_active` | 研究持续进行，不代表停止 |
| `ai_monitored_candidate` | `research_active` | AI 监控是能力，不再单列生命周期 |
| `shadow_candidate` | `shadow_active` | 仍保持 `no_order=true` |
| `runtime_enabled` | `live_candidate` | 只表示旧 runtime 可选择，不能证明已有 live 授权 |

旧部署若确实已经 live，可以在独立部署授权保持有效时报告为
`live_enabled`；这个结论必须来自部署与账户控制面，不能由上述兼容映射生成。

旧文档中的 `research-only` 在新系统中统一解释为：

```text
research_active + 可自动推进 shadow/forward + no_order=true
```

没有 paper 能力的平台仍可直接运行 shadow，不应因此阻塞研究主线。

## 已经 live 的旧策略

已经获得 live 权限的旧策略继续作为生产基线运行，不需要因为迁移到新系统而停机或重做。新系统会：

- 持续记录每日表现、风险、数据质量和漂移；
- 自动生成参数优化、插件优化和候选重构版本；
- 先对改动运行历史验证和 shadow/forward；
- 发现硬风险时允许自动暂停、降仓或回滚到最近稳定版本。

自动化优化不能直接扩大 live 资金、杠杆、品种范围或 broker 权限。涉及这些权限变化时，仍然需要单独的人工 live 决策。
