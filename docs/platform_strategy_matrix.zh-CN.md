# 平台策略矩阵

_核对时间：2026-04-14_

这页只回答一个问题：

> 现在各个平台分别属于哪个策略大类，线上实际在跑什么 profile，哪些只是后续扩展接口？

如果要看 live 的 GCP 项目、Cloud Run service、scheduler、runtime identity、secret 名，请看 [`platform_runtime_inventory.zh-CN.md`](./platform_runtime_inventory.zh-CN.md)。

如果要看仓库职责边界，请看 [`platform_repo_boundaries.zh-CN.md`](./platform_repo_boundaries.zh-CN.md)。

## 总结

- 当前只有两个策略大类：
  - `us_equity`
  - `crypto`
- 各个平台仓库现在都已经保留了 `STRATEGY_PROFILE` 入口，但这**还不是**真正的多策略平台。
- 现在每个美股平台仓库都可以通过 rollout allowlist 在已启用的 live `us_equity` profile 之间切换。
- 共享契约在 `QuantPlatformKit`；真实的 `us_equity` 策略实现现在放在 `UsEquityStrategies`，平台仓库负责运行时适配和券商执行。

## 当前平台矩阵

| 平台 | 仓库 | 策略大类 | 当前 live profile | 运行模型 | 现在能否真实切换？ |
|---|---|---|---|---|---|
| IBKR | `QuantStrategyLab/InteractiveBrokersPlatform` | `us_equity` | `soxl_soxx_trend_income` | Cloud Run | 可以，rollout allowlist 可在受支持 profile 间切换 |
| Charles Schwab | `QuantStrategyLab/CharlesSchwabPlatform` | `us_equity` | `tqqq_growth_income` | Cloud Run | 可以，rollout allowlist 可在受支持 profile 间切换 |
| LongBridge | `QuantStrategyLab/LongBridgePlatform` | `us_equity` | `HK: tech_communication_pullback_enhancement / SG: tqqq_growth_income` | Cloud Run | 可以，rollout allowlist 可在受支持 profile 间切换 |
| Binance | `QuantStrategyLab/BinancePlatform` | `crypto` | `crypto_leader_rotation` | Oracle Cloud + self-hosted runner | 不能，当前只支持这个 profile |

## 这张表现在该怎么理解

### `us_equity`

当前属于这个大类的平台有：

- `InteractiveBrokersPlatform`
- `CharlesSchwabPlatform`
- `LongBridgePlatform`

但要注意：

- 这**不等于**任何一个 `us_equity` 策略现在都能直接在这三个平台上切换运行。
- 它只表示这些平台已经共享同一层“策略大类 + 兼容性”抽象。
- 真正的具体策略，仍然要单独声明自己支持哪些平台、是否真的适合那个运行时。

当前 `us_equity` 域里线上在跑的 profile 有：

- `soxl_soxx_trend_income`
- `tqqq_growth_income`
- `tech_communication_pullback_enhancement`

### `crypto`

当前属于这个大类的平台有：

- `BinancePlatform`

当前 `crypto` 域里线上在跑的 profile：

- `crypto_leader_rotation`

当前实际规则：

- Binance 现在是唯一一个 live 的 `crypto` 平台。
- Binance 也不应该被当成 Cloud Run 平台来理解；它仍然是 Oracle Cloud + self-hosted runner 这条运行链。

## 已经落地的部分

这些现在已经是实的：

- `QuantPlatformKit` 里已经有共享的策略大类 / profile 契约
- 每个平台仓库里已经有自己的薄策略注册表
- `STRATEGY_PROFILE` 不支持时会 fail-fast

## 还没完成的部分

下面这些现在都**还不是真的**：

- 只改一个 env 就能让任意未来 `us_equity` 策略在任意 `us_equity` 平台上跑起来
- 每条策略都完整覆盖每个券商适配器
- `UsEquityStrategies` 之外已经投入生产使用的独立策略仓库

## 当前推荐理解方式

现在先按这个顺序理解：

- 先选 **平台仓库**
- 再选 **这个平台当前支持的策略 profile**
- 不要把“同属一个策略大类”直接理解成“实现已经共享”

## 推荐下一步

在真正拆策略实现之前，建议继续按这个顺序推进：

1. 先保持运行命名和文档一致
2. 持续更新这份平台 / 大类 / profile 矩阵
3. 把策略层行为和频率继续放在 `UsEquityStrategies`
4. 平台文档只保留运行时适配、profile 启用状态和券商执行说明
