# 平台仓库职责边界

## 为什么要有这份文档

现在实际有三层东西同时存在：

1. `QuantPlatformKit`
2. broker 平台运行仓库
3. 未来可能出现、但现在还没真正拆出来的策略仓库

当前还处在过渡期，所以这份文档只回答一个问题：

> 哪些东西该放在哪一层，哪些东西不该放？

如果要看当前的平台 / 策略大类 / live profile 对照表，请看 [`platform_strategy_matrix.zh-CN.md`](./platform_strategy_matrix.zh-CN.md)。

## 1. `QuantPlatformKit`

`QuantPlatformKit` 是共享依赖包。

它应该负责：

- 统一领域模型
- 统一 ports / interfaces
- broker 适配层
- 通用通知能力
- 公共策略契约
  - 策略大类
  - profile 定义
  - 平台兼容规则

它**不应该**负责：

- Cloud Run 服务本身
- GitHub Actions 的部署编排
- scheduler 定义
- 某个项目自己的 secret 名
- 某个平台自己的运行时 env 结构
- 某个策略自己的调度周期

## 2. 平台运行仓库

当前例子：

- `InteractiveBrokersPlatform`
- `CharlesSchwabPlatform`
- `LongBridgePlatform`
- `BinancePlatform`

这些仓库就是实际部署单元。

它们应该负责：

- 运行入口
- 执行编排
- 部署 workflow
- Cloud Run / scheduler / Oracle 运行配置
- runtime secret 选择
- 账户或区域选择
- 当前仍然留在仓库里的平台侧策略实现

它们**不应该**变成：

- 所有 broker 的超级共享包
- 一个泛化过头的策略市场
- 一个靠参数在多个完全不同 broker 之间乱切的可部署仓库

## 3. 未来策略仓库

现在还不是必须做，但目标形态已经可以先定出来。

如果后面真的要拆，它们应该负责：

- 可复用的策略计算
- 某个策略域自己的参数
- 确实能跨平台复用的策略逻辑

它们**不应该**负责：

- broker 登录
- Cloud Run 入口
- GitHub 部署配置
- scheduler
- 平台运行身份

## 现在允许存在的重复

过渡期里，有些重复是可以接受的。

### 现在可以接受

- 每个运行仓库各有一个 `strategy_registry.py`
- 每个运行仓库各有一个 `runtime_config_support.py`
- 策略实现暂时还留在平台运行仓库里

这是合理的，因为现在每个平台的运行约束还不一样：

- IBKR 有 account-group
- LongBridge 有 region
- Schwab 有 token refresh
- Binance 根本不是 Cloud Run

### 现在不值得硬抽

不要现在就强行统一：

- 所有 runtime env 解析
- 所有通知文案
- 所有策略执行入口

这种“先统一再说”的重构，通常只会让代码在真正出现共享收益前先变绕。

## 一个实用判断标准

如果一段代码回答的是：

- **这个 broker 平台怎么跑、怎么部署？**
  - 放平台运行仓库

- **这个能力是不是跨多个 broker / runtime 都能复用？**
  - 放 `QuantPlatformKit`

- **这段逻辑是不是不依赖某个平台的运行时接线，只是策略本身可复用？**
  - 这是未来策略仓库候选

## 当前更推荐的下一步

现在**不要**先做大规模策略拆分。

更合理的顺序是：

1. 继续把共享策略契约放在 `QuantPlatformKit`
2. 真实策略实现暂时还放在各平台运行仓库里
3. 等至少有一个 `us_equity` 策略，真的准备在 IBKR / Schwab / LongBridge 之间复用
4. 再按策略大类去拆，而不是按 broker 去拆
