# 生命周期 AI 任务接口迁移

本地升级基线：QuantPlatformKit `350dd38ece0952beef096893a7dcf8ae3871609a`。尚未提交、发布或部署；调用方的现有远端依赖固定版本不会自动包含这些改动。

`strategy_lifecycle/ai_provider.py` 现在使用 `ai_service.client.TaskClient`，只调用 V2 的提交和查询接口。已经删除该模块的旧 HTTP 客户端、CLI/VPS 路由、内置模型、provider chain 和付费 fallback。`AiProviderConfig` 接收 `label`、`mode`、`model`、`profile`；不再提供旧的 `codex_vps()`、`claude()`、`gpt()` 工厂。

依赖由批准环境安装本次 PersonalAIService 2.0 源码构建的 wheel。这个包尚未公开发布，不能从公共索引安装同名包代替。QuantPlatformKit 的基础功能不会主动加载 AI 客户端；开启 AI 路径前需要准备该 wheel 和 `AI_SERVICE_URL`、`AI_SERVICE_AUDIENCE`，身份使用批准的 token 客户端或 GitHub Actions OIDC。旧的 `CODEX_AUDIT_SERVICE_*` 和 `AI_GATEWAY_RESEARCH_PROVIDERS` 不再用于本模块。

## 路由与结果

普通执行读取 `AI_SERVICE_MODE`（默认 agent）、`AI_SERVICE_MODEL`（必须显式设置）、`AI_SERVICE_PROFILE`（默认 default）。审查从 `AI_SERVICE_REVIEWERS_JSON` 读取明确的路由列表；可选的核对路径由 `AI_SERVICE_VERIFIER_JSON` 指定，默认没有核对助手。例如：

```json
[
  {"label": "reviewer-primary", "mode": "agent", "model": "configured-dot", "profile": "default"},
  {"label": "reviewer-secondary", "mode": "agent", "model": "configured-grok", "profile": "second-opinion"}
]
```

服务端决定实际 provider 和项目权限。这里的 label 是审查角色，不证明模型厂商或实际模型。同一 mode/profile 不能作为两个不同审查路径，但不同 profile 仍不证明云电脑、账户或工具权限隔离；正式独立审查需要产品端完成独立连接及权限隔离。

任务请求只含通用目标、材料、输出 schema、超时、模式和 profile。生命周期输出被封装为一个 `report` 字符串，里面的业务 JSON 仍由生命周期调用方验证。读取结果必须匹配任务 ID 和原始请求，完成且标记 advisory 后才进入业务解析。API 路由核对接口报告的模型；常驻助手必须明确标记 `model_verification=unavailable`，不伪造旧 Codex 的模型或 reasoning-effort 证明。

## 重试与研究权限

调用方提供操作幂等键，或在 Actions 中使用同一 run ID；角色、材料、模型和路由参与摘要。生命周期研究决定使用冻结输入构造的完整 prompt 摘要作为操作身份。客户端超时及已知任务读取失败保留任务 ID，结果保持 outcome_unknown，没有自动回退或重新触发助手。

研究流程将 ai_task_pending 保存为 deferred，不把它当作负面研究建议。后续通过专门的 pending reader 查询原任务；`resume_task_id` 路径不会提交新任务，并重新核对原始请求绑定。如果没有 reader，维持等待；配置或材料不一致时不能采用原结果。既有历史 Codex 容量延后记录的解析保留，以免改写既有研究证据；这不提供旧服务接口兼容。

AI 的完成与推荐不授予数值研究、交易、资金或发布权限。原有来源新鲜度、冻结输入、Python 数值检验、回测、paired shadow、风险条件及人工候选决策继续生效。历史 `codex_integration.py` 文件名及既有证据记录没有机械改名。

## 本地验收

测试只使用 synthetic 数据与假任务客户端，未调用真实模型或读取真实市场、账户数据。当前已覆盖任务结果绑定、API 模型不匹配、常驻模型不可验证、幂等键、未知结果、超时、原任务恢复、双审查角色、研究恢复及风险准入。离线验证不代表 Dot/Grok 连接或生产研究已恢复。

## 通用材料与审查

`ai_patch.py` 只允许调用方显式允许的现有文件、基准摘要匹配且唯一定位的有界替换；业务语法或领域校验由调用方提供，全部预检通过才写候选。共享实现没有平台或策略路径白名单。

`research_task.py` 保留已有 watcher wire schema，校验完整来源和严格类型的研究权限；不含 SOXL 的固定参数。非空参数边界摘要需要调用方明确提供允许值。策略仓库再检查其业务来源是否有资格使用该边界。

`research_summary.py` 的短解释默认 API 模式，模型和 profile 明确配置；没有配置时返回 unavailable。`task_review.py` 接收调用方要求的审查角色，校验任务身份、角色唯一、任务唯一及完整意见格式；所有角色完成才能形成 advisory quorum，意见不一致需人工判断。它不发送外部消息，也不批准交易、部署或发布。角色和不同 profile 仍不证明产品端账号与工具隔离，正式采用前需要核对真实连接边界。
