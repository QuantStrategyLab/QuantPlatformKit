# 新量化系统生命周期术语

新系统不再把 `research-only` 理解为“停止开发”。它表示策略仍可由自动化研究系统持续处理，但尚未获得交易权限。

| 状态 | 允许 | 不允许 |
|---|---|---|
| `research_active` | 历史回测、参数优化、组合分析、AI 研究、候选版本 | 真实下单 |
| `shadow_active` | 使用未来数据运行 shadow/forward、漂移监测 | 真实资金和 broker order |
| `paper_active` | 模拟账户运行（平台支持时） | 真实资金 |
| `live_candidate` | 准备 live 包、风险检查和通知 | 自动开启真实交易 |
| `live_enabled` | 按已批准权限运行 | 超越 Risk Gate 或自动扩大权限 |

旧文档中的 `research-only` 在新系统中统一解释为：

```text
research_active + 可自动推进 shadow/forward + no_order=true
```

没有 paper 能力的平台仍可直接运行 shadow，不应因此阻塞研究主线。
