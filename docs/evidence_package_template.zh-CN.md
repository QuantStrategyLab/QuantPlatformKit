# 策略晋级证据包

这份模板定义了请求 `live_candidate` 复核时最少应提交的内容。

## 必要内容

- 策略 profile 名称
- 目标平台
- 回测摘要
- drift / regime 观察
- 平台兼容性证据
- 插件门槛状态（如适用）
- 操作备注与 rollout 限制

## 建议结构

```text
profile: cn_chinext_growth_momentum_quality
market: cn_equity
requested_stage: live_candidate

1. 回测摘要
2. drift 与 regime 观察
3. 风险复核
4. 平台兼容性证据
5. 插件门槛状态
6. rollout 备注
```

## 接受规则

如果缺少以下任一项，就应继续留在 live 之外：

- profile 与目标平台不兼容
- 插件门槛不是明确 approved 或 notification-only
- 证据没有同时覆盖收益表现和 regime 敏感性
- 只依赖单一好窗口

## 责任划分

- 策略仓库：产出证据包
- 平台仓库：验证 runtime 兼容性和门槛状态
- 操作审批：做最终 live 决策
