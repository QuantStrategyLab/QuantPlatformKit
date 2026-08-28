# 策略生命周期门槛策略

[English](./strategy_lifecycle_policy.md)

本文定义量化仓库中策略 profile 的生命周期门槛。

## 设计目标

生命周期应当对研究和监控保持宽松，但对资金影响保持严格。

- AI 监控可以加快复核和暴露 drift。
- AI 监控不能绕过 live 启用门槛。
- 策略可以先被观察，再允许交易。
- live 启用仍然是平台决策，不只是回测结论。

跨仓库的研究控制面决策见
[ADR 0005](./adr/0005-research-control-plane.md)。它同样适用于参数修改、
策略重构/新策略和插件修订。

## 规范生命周期阶段

| 阶段 | 含义 | 资金影响 | 常见归属 |
| --- | --- | --- | --- |
| `research_active` | 回测、优化、证据收集和候选生成 | 无 | 策略仓库 |
| `shadow_active` | forward/shadow 观察和 drift 跟踪 | 无 | 策略生命周期 |
| `paper_active` | 平台支持时运行模拟账户 | 仅模拟 | 平台 |
| `live_candidate` | 已通过验证，等待平台启用 | 受门槛控制 | 平台 + 策略 |
| `live_enabled` | 仅在独立批准的部署权限范围内运行 | 已批准范围 | 部署控制面 |

### 实际含义

- `research_active` 适合作为所有新策略的默认起点，并会持续自动研究。
- AI 监控是各阶段可使用的能力，不再单列为晋级状态。
- `shadow_active` 应该要求重复 shadow 一致性，而不是只看一次漂亮回测。
- `live_candidate` 只适合证据足够支持平台启用的策略。
- `live_enabled` 只记录已经存在的部署授权，不能自行创建或扩大授权。

### 研究控制面边界

在 `research_active` 和 `shadow_active` 内，自动化可以发现异常、冻结研究/
优化规格、运行完整留痕的试验、创建候选和证据 PR、启动非实盘观察，以及暂停
不符合约束的目标。它不能合并会影响实盘的改动、启用或恢复 live、修改 live
参数、扩大资金/杠杆，或扩大 broker/IAM 权限。

每个候选必须保留版本化身份、来源/数据/成本/trial 溯源、基准规则和证据 digest。
任何有资金影响的人工批准都必须绑定候选及平台/账户范围；CI 成功或证据包本身
永远不产生资金权限。

### 旧 catalog 兼容

| 旧状态 | 新系统保守解释 |
| --- | --- |
| `research_backtest_only` | `research_active` |
| `ai_monitored_candidate` | `research_active` |
| `shadow_candidate` | `shadow_active` |
| `runtime_enabled` | `live_candidate` |

旧 `runtime_enabled` 经常只表示“策略包可被 runtime 选择”，不能证明 broker
下单已经获批。旧 live 策略只有在独立部署授权仍有效时才能报告
`live_enabled`。catalog、inventory 和 evidence 本身都不产生权限。

## 三道门槛

策略进入 live 之前，应同时通过三道门槛：

1. **策略门槛**
   - 是否具备足够的历史、风险画像和 drift 容忍度，能从研究阶段前进？
2. **插件门槛**
   - 如果策略依赖插件，这些插件是否至少是 `automation_approved`，
     或者被明确标记为 `notification_only`？
3. **平台门槛**
   - 目标平台是否接受该 profile 和运行时输入，并且部署控制面是否持有
     当前有效的明确授权？

任意一项不过关，都应该继续留在 live 之外。

### 发布前准入校验

镜像发布是独立的控制边界。平台替换已部署 runtime 镜像前，部署工作流必须只读取
已部署服务的非敏感目标身份；下列任一项发生漂移都必须 fail-closed：

- 目标服务身份；
- 规范化后的策略 profile 或其平台准入状态；
- 声明的 dry-run 权限；
- shadow 目标却被声明成 live 提交目标。

该校验不晋级、不启用、也不自动修复目标。已退役或不一致的目标必须保持隔离，重新
收集证据并走完生命周期后才能恢复；健康的 protected-live 目标则可在既有授权范围内继续运行。

## 推荐晋级策略

- 监控阈值可以相对低一些，让候选策略尽早可见。
- 如果组织已经有自动 AI 监控，就用它尽快把合适的 profile 推到
  `research_active`；自动监控只提高可见性，不产生资金权限。
- live 启用阈值要保持高一些，确保运行时暴露是明确决策。
- 以证据包晋级，而不是临时 override。证据包至少应包含回测摘要、
  drift 记录、风险复核和平台兼容性证据。
- 证据包建议结构见 [`evidence_package_template.zh-CN.md`](./evidence_package_template.zh-CN.md)。
- 如果策略是 wrapper / orchestrator，应先确认被包装组件稳定，再考虑给 wrapper 晋级。

## 候选与人工决定合同

`strategy_candidate.v1` 是研究工件，不是另一套生命周期状态。它记录一个边界清晰的
候选类型：`parameter_change`、`strategy_revision`、`new_strategy` 或
`plugin_revision`。其中研究子状态只描述候选的研究进度，不能让 profile 在上面的规范
生命周期阶段之间自动迁移。

每个候选都会用 SHA-256 绑定既有 `CandidateRiskIdentity`、对应的 `ResearchSpec`、
参数变更所需的 `OptimizationSpec`，以及完整、有序的 `SourceReceipt` 集合。来源回执
保留来源 URI、获取时间、内容哈希和许可证，但明确标记为 `untrusted`；网页内容不能
产生权限，也不能改写运行时设置。

`strategy_candidate.v2` 是面向研究工厂输出的只引用形式：它以完整、有序的
`{schema_version, receipt_sha256}` 列表替代内嵌的来源回执投影。唯一允许的来源 schema
是 `research_source_receipt.v1`。它不能携带原始内容、URL、许可证字段或转换后的
receipt digest；该生产者负责回执验证。`strategy_candidate.v1` 继续保持已有工件的可读
兼容，但新的研究工厂候选应写入 v2。

`promotion_decision.v1` 记录具名人工复核、精确候选哈希、非 live 范围
（`research`、`shadow` 或 `paper`）和过期时间。序列化字段 `grants_live` 与
`grants_execution_authority` 永远是 `false`。因此它不能启用实盘、增加风险预算，
也不能替代独立的平台、Risk Gate 和 broker 控制。

自动系统可以提出候选、回测、收集证据和创建人工复核 PR；不得自动批准、自动合并、
部署或 live 启用任何可能影响资金的变更。旧 CLI 参数 `--auto-approve` 仅为兼容而
保留，并会被忽略。

## 仓库级建议

- **美股**：长历史趋势 / 轮动策略可以更早进入生命周期推进；wrapper combo 应优先保持 candidate 状态。
- **港股**：保持 live 暴露范围窄，只晋级稳定的 runtime profile。
- **A 股**：把 QMT 专用的可选 runtime profile 和主 live catalog 分开看待。
- **加密货币**：监控阶段可以宽松一些，但 live 门槛应更严格，因为 regime 切换更快。

## 运行规则

`get_runtime_enabled_profiles()` 保留为旧兼容 API，只表示 runtime 可选择。
未被返回的 profile 必须留在 runtime 之外；被返回的 profile 仍必须通过明确部署授权、
当前 Risk Gate 以及 broker/account 权限检查，才能产生订单。
