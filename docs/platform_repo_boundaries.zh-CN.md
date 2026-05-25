# 平台仓库职责边界

这份文档说明 `QuantPlatformKit` 如何与策略仓库、券商平台仓库协作。

## QuantPlatformKit

`QuantPlatformKit` 是共享包，负责跨仓库复用的契约和 helper：

- 共享领域模型
- 市场数据、持仓快照、执行、通知、状态等 ports / interfaces
- 券商适配工具
- strategy manifest、context、decision、loader、validation 契约
- 策略插件解析、兼容性校验和告警文案 helper

它应该保持平台无关，不放券商 session、平台专属运行时接线、生成 artifact
或策略公式。

## 策略仓库

策略仓库负责可复用的策略行为：

- profile metadata 和 manifest
- 纯 `evaluate(ctx)` 入口
- 策略参数和 diagnostics
- 策略需要上游生成数据时，对 artifact schema 的要求

策略代码不导入券商 SDK，也不按券商平台分支。

## 平台仓库

平台仓库负责把券商和运行时输入接到共享契约上：

- 创建券商 session
- 加载运行时配置
- 组装 `StrategyContext`
- 调用策略入口
- 把 `StrategyDecision` 映射成券商原生执行
- 渲染并发送平台专属通知
- 持久化平台自己的运行状态和报告

券商专属 adapter、请求入口和 decision mapper 可以留在平台仓库本地。
如果某个 helper 在多个平台之间出现真实复用，再把共享部分移到
`QuantPlatformKit`，平台仓库只保留边缘接线。

## 实用判断

判断代码放哪里时，按这个拆分：

- 共享契约或可复用 adapter：放 `QuantPlatformKit`
- 策略公式或 profile 语义：放策略仓库
- 券商 session、运行时组装、执行、通知路由或状态：放平台仓库
