# QuantStrategyLab 架构设计

## 分层模型

```
┌─────────────────────────────────────────────────────────┐
│                    执行层                                │
│  SchwabPlatform  │ IBKRPlatform │ LongBridgePlatform    │
│  BinancePlatform │ FirstradePlatform                    │
│  (Cloud Run)     │ (Cloud Run)  │ (GitHub Actions+VPS)  │
├─────────────────────────────────────────────────────────┤
│                    策略层                                │
│  UsEquityStrategies │ HkEquityStrategies                │
│  CnEquityStrategies │ CryptoStrategies                  │
│  QuantUsComboStrategies │ QuantHkComboStrategies        │
│  (pip 包，版本锁定在 requirements.txt)                   │
├─────────────────────────────────────────────────────────┤
│                    快照层                                │
│  UsEquitySnapshotPipelines │ HkEquitySnapshotPipelines  │
│  CnEquitySnapshotPipelines │ CryptoLivePoolPipelines    │
│  (产出 GCS 产物，供执行层消费)                            │
├─────────────────────────────────────────────────────────┤
│                  基础设施层                               │
│  QuantPlatformKit │ QuantRuntimeSettings                │
│  QuantStrategyPlugins │ MarketSignalSources             │
│  (共享契约、适配器、运行时工具)                            │
└─────────────────────────────────────────────────────────┘
```

## 数据流

```
策略定义（pip 包）
  → 策略目录（STRATEGY_CATALOG）
    → 平台能力矩阵（此平台能跑吗？）
      → 快照管线（产出产物 → GCS）
        → 运行时适配器（加载策略入口）
          → 平台执行（拉数据 → 计算 → 下单）
            → 执行报告（GCS + 结构化日志）
              → 监控调度（probe + dry-run 检查）
```

## 配置唯一数据源

每个平台服务只有一个权威配置入口：

```json
RUNTIME_TARGET_JSON = {
  "platform_id": "...",
  "strategy_profile": "...",
  "execution_mode": "live",
  "scheduler": {
    "main_time": "45 15 * * *",
    "precheck_time": "45 9 * * *",
    "probe_time": "35 9,15 * * *",
    "timezone": "America/New_York"
  }
}
```

**所有其他引用策略/平台名称的配置值都从这里推导。** 自动同步层（config-sync）在启动时修正过期引用。

## 设计模式

### 1. 策略注册模式

每个平台有 `strategy_registry.py`：
- 从 pip 包导入共享策略目录
- 合并多个目录（US + HK + Combo）
- 通过能力矩阵过滤策略
- 路由到正确的运行时适配器

### 2. 运行时适配器模式

每个策略通过 `get_platform_runtime_adapter(profile, platform_id)` 暴露 `StrategyRuntimeAdapter`：
- `available_inputs` — 需要什么数据
- `managed_symbols_extractor` — 监控哪些标的
- `runtime_policy` — 执行时点契约

### 3. 配置自动同步模式

模块加载时，`config-sync` 层：
1. 从 `RUNTIME_TARGET_JSON` 读取 `STRATEGY_PROFILE`
2. 扫描插件挂载 JSON → 修正过期的 `strategy` 字段
3. 扫描监控目标 JSON → 修正过期的 `strategy_profile` 字段
4. 打印 `[config-sync]` 日志记录每次修正

### 4. 唯一数据源模式

- `RUNTIME_TARGET_JSON` = 权威策略+平台配置
- `STRATEGY_PROFILE` 环境变量 = 已废弃（已移除）
- 插件挂载 `strategy` 字段 = 自动同步
- 监控目标 `strategy_profile` = 自动同步

### 5. 执行时点契约

策略在运行时策略中声明 `signal_effective_after_trading_days` 和 `execution_timing_contract`。平台：
- 执行前检查市场日历
- 遵守时点契约（next_trading_day 等）
- 对多日窗口（月度 DCA）使用 `execution_dedup_enabled`

## Scheduler 规则

**Scheduler 时区 = 市场时区，不是服务区域。**

| 市场 | 日历 | 时区 | 执行窗口 |
|---|---|---|---|
| US Equity | NASDAQ | `America/New_York` | 3:45 PM ET |
| HK Equity | XHKG | `Asia/Hong_Kong` | 3:45 PM HKT |
| A股 | XSHG | `Asia/Shanghai` | 2:45 PM CST |
| Crypto | 24/7 | UTC | GitHub Actions |

## 新增平台规范

1. 从最相似现有模板创建平台仓库
2. 实现 `strategy_registry.py`
3. 实现 `runtime_config_support.py`（dataclass 必填字段在前）
4. 实现券商适配器、行情端口、执行端口
5. 添加 Flask 路由（`/run`, `/dry-run`, `/probe`, `/health`, `/monitor-dispatch`）
6. 添加 Cloud Scheduler 任务
7. 添加 `.env.example` 环境变量模板
8. 加入跨平台监控

## 新增策略规范

1. 在共享目录 pip 包中添加策略定义
2. 设置 `compatible_platforms`
3. 在 `runtime_adapters` 中实现适配器
4. 平台自动发现（无需改平台代码）
5. 部署：改 `RUNTIME_TARGET_JSON.strategy_profile`

## 部署安全检查

1. `python scripts/check_required_env.py --platform=<id>`
2. `python scripts/validate_platform_consistency.py`
3. 部署后用 `/health` 验证模块导入
4. `/dry-run` 验证全链路
5. 确认执行报告无错误后启用实盘
