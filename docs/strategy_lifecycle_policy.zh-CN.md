# 策略生命周期门槛策略

[English](./strategy_lifecycle_policy.md)

本文定义量化仓库中策略 profile 的生命周期门槛。

## 设计目标

生命周期应当对研究和监控保持宽松，但对资金影响保持严格。

- AI 监控可以加快复核和暴露 drift。
- AI 监控不能绕过 live 启用门槛。
- 策略可以先被观察，再允许交易。
- live 启用仍然是平台决策，不只是回测结论。

## 推荐生命周期阶段

| 阶段 | 含义 | 资金影响 | 常见归属 |
| --- | --- | --- | --- |
| `research_backtest_only` | 仅回测、特征开发或证据收集 | 无 | 策略仓库 |
| `ai_monitored_candidate` | 可进入 AI 复核、drift 打分和 shadow 跟踪 | 无 | 策略生命周期 |
| `shadow_candidate` | shadow 运行已经稳定，可做重复对比 | 无 | 策略生命周期 |
| `live_candidate` | 已通过验证，等待平台启用 | 受门槛控制 | 平台 + 策略 |
| `runtime_enabled` | 会被 `get_runtime_enabled_profiles()` 暴露并允许进入运行时设置 | 有 | 平台仓库 |

### 实际含义

- `research_backtest_only` 适合作为所有新策略的默认起点。
- 如果组织已经有自动监控，`ai_monitored_candidate` 可以作为最低摩擦的复核阶段。
- `shadow_candidate` 应该要求重复 shadow 一致性，而不是只看一次漂亮回测。
- `live_candidate` 只适合证据足够支持平台启用的策略。
- `runtime_enabled` 才应该影响 live 配置默认值。

## 三道门槛

策略进入 live 之前，应同时通过三道门槛：

1. **策略门槛**
   - 是否具备足够的历史、风险画像和 drift 容忍度，能从研究阶段前进？
2. **插件门槛**
   - 如果策略依赖插件，这些插件是否至少是 `automation_approved`，
     或者被明确标记为 `notification_only`？
3. **平台门槛**
   - 目标平台是否通过 `get_runtime_enabled_profiles()` 暴露该 profile，
     并接受所需运行时输入？

任意一项不过关，都应该继续留在 live 之外。

## 推荐晋级策略

- 监控阈值可以相对低一些，让候选策略尽早可见。
- 如果组织已经有自动 AI 监控，就用它尽快把合适的 profile 推到
  `ai_monitored_candidate`；这一层只为可见性，不为资金。
- live 启用阈值要保持高一些，确保运行时暴露是明确决策。
- 以证据包晋级，而不是临时 override。证据包至少应包含回测摘要、
  drift 记录、风险复核和平台兼容性证据。
- 证据包建议结构见 [`evidence_package_template.zh-CN.md`](./evidence_package_template.zh-CN.md)。
- 如果策略是 wrapper / orchestrator，应先确认被包装组件稳定，再考虑给 wrapper 晋级。

## 仓库级建议

- **美股**：长历史趋势 / 轮动策略可以更早进入生命周期推进；wrapper combo 应优先保持 candidate 状态。
- **港股**：保持 live 暴露范围窄，只晋级稳定的 runtime profile。
- **A 股**：把 QMT 专用的可选 runtime profile 和主 live catalog 分开看待。
- **加密货币**：监控阶段可以宽松一些，但 live 门槛应更严格，因为 regime 切换更快。

## 运行规则

如果某个 profile 没有被 `get_runtime_enabled_profiles()` 返回，那么它就不应该进入 live runtime settings，
无论监控状态是否已经打开。
