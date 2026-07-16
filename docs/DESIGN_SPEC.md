# 平台、策略、插件开发规范

> 本文档是 QuantStrategyLab 所有开发工作必须遵守的规范。
> 违反本文档的 PR 不应合并。

## 目录

1. [平台开发规范](#1-平台开发规范)
2. [策略开发规范](#2-策略开发规范)
3. [插件开发规范](#3-插件开发规范)
4. [配置管理规范](#4-配置管理规范)
5. [调度与监控规范](#5-调度与监控规范)
6. [部署与安全规范](#6-部署与安全规范)
7. [检查清单](#7-检查清单)

---

## 1. 平台开发规范

### 1.1 新增平台

新建平台时，必须完成以下所有步骤：

**1.1.1 仓库结构**

```
{PlatformName}Platform/
├── main.py                          # Flask 入口, 定义所有路由
├── strategy_registry.py             # 策略注册: 导入 catalog, 能力矩阵, 启用列表
├── runtime_config_support.py        # PlatformRuntimeSettings dataclass, env var 加载
├── runtime_execution_policy.py      # 平台特定的执行策略 (DCA, fractional 等)
├── decision_mapper.py               # 策略决策 → 订单计划
├── requirements.txt                 # pip 依赖, 所有策略包版本锁定
├── Dockerfile                       # Cloud Run 容器定义
├── .env.example                     # 所有必需环境变量模板
├── application/
│   ├── runtime_broker_adapters.py   # 券商连接适配器
│   ├── runtime_composer.py          # 依赖注入和组件装配
│   ├── runtime_reporting_adapters.py# 执行报告和日志
│   ├── runtime_strategy_adapters.py # 策略运行时适配
│   └── rebalance_service.py         # 调仓执行核心
└── tests/                           # 单元测试
```

**1.1.2 `strategy_registry.py` 必须实现**

```python
# 1. 导入所有相关策略包
from us_equity_strategies import get_strategy_catalog, get_runtime_enabled_profiles
from quant_us_combo_strategies import get_strategy_catalog as get_combo_catalog

# 2. 合并多个 catalog (如有多个策略域)
STRATEGY_CATALOG = merge_catalogs(us_catalog, combo_catalog)

# 3. 定义平台能力矩阵
PLATFORM_CAPABILITY_MATRIX = PlatformCapabilityMatrix(
    platform_id=PLATFORM_ID,
    supported_domains={"us_equity", "quant_combo"},
    supported_target_modes={"weight", "value"},
    supported_inputs={"market_history", "portfolio_snapshot", ...},
    supported_capabilities={"fractional_share_execution"},
)

# 4. 定义排除列表 (未就绪的策略)
EXCLUDED_LIVE_PROFILES = frozenset({...})

# 5. 自动推导启用列表 (不要硬编码)
ENABLED_PROFILES = derive_enabled_profiles_for_platform(
    STRATEGY_CATALOG, capability_matrix=..., rollout_allowlist=...
)

# 6. 实现适配器路由
def get_platform_runtime_adapter(profile, *, platform_id):
    if profile in COMBO_PROFILES:
        return get_combo_runtime_adapter(profile, platform_id=platform_id)
    if profile in HK_PROFILES:
        return get_hk_runtime_adapter(profile, platform_id=platform_id)
    return get_us_runtime_adapter(profile, platform_id=platform_id)
```

**1.1.3 `runtime_config_support.py` Dataclass 字段顺序规则**

```python
@dataclass(frozen=True)
class PlatformRuntimeSettings:
    # ⚠️ 必填字段 (无默认值) 必须排在所有有默认值的字段之前
    strategy_profile: str           # 必填
    strategy_domain: str            # 必填
    dry_run_only: bool              # 必填

    # 有默认值的字段在后面
    notification_channel: str = "telegram"
    runtime_target_enabled: bool = True
    # ... 更多可选字段
```

违反此规则会导致 `TypeError: non-default argument follows default argument`。

**1.1.4 Flask 路由**

每个平台必须提供以下路由：

| 路由 | 方法 | 用途 |
|---|---|---|
| `/run` | POST | 执行策略 |
| `/dry-run` | POST/GET | 干跑验证（不下单） |
| `/probe` | POST/GET | 连接券商 + 账户状态检查 |
| `/health` | GET | 服务健康检查（含模块导入自检） |
| `/monitor-dispatch` | POST | 跨平台监控调度入口 |

**1.1.5 `/health` 端点的模块导入自检**

```python
@app.route("/health", methods=["GET"])
def health():
    errors = []
    for module in ("application.runtime_composer",
                   "application.runtime_reporting_adapters",
                   "application.runtime_strategy_adapters",
                   "runtime_execution_policy"):
        try:
            importlib.import_module(module)
        except Exception as e:
            errors.append(f"{module}: {e}")
    if errors:
        return json.dumps({"status": "unhealthy", "errors": errors}), 500
    return "OK", 200
```

---

## 2. 策略开发规范

### 2.1 新增策略

**2.1.1 在共享策略包中添加**

策略逻辑放在对应的共享 pip 包中（如 `us_equity_strategies`），不要放在平台仓库中。

```python
# 在 catalog.py 中注册
STRATEGY_PLATFORM_COMPATIBILITY = {
    "new_strategy_profile": frozenset({"schwab", "ibkr", "longbridge"}),
}

STRATEGY_METADATA = {
    "new_strategy_profile": StrategyMetadata(
        canonical_profile="new_strategy_profile",
        display_name="New Strategy",
        domain="us_equity",
        cadence="daily",          # daily / monthly / snapshot
        status="runtime_enabled", # 控制是否对平台可见
    ),
}
```

**2.1.2 平台兼容性声明**

策略的 `compatible_platforms` 必须包含所有预期支持的平台。平台侧不需要任何代码改动——策略自动通过 `derive_enabled_profiles_for_platform()` 被发现。

**2.1.3 执行时点契约**

策略通过 `StrategyRuntimeAdapter.runtime_policy` 声明执行时点：

- `signal_effective_after_trading_days=1` → 次日执行（标准）
- `signal_effective_after_trading_days=0` → 当日执行
- 月度策略使用 `feature_snapshot` 输入 + monthly cadence

### 2.2 策略分类

| 类型 | Domain | 调度 | 说明 |
|---|---|---|---|
| 每日直接 | `us_equity` / `hk_equity` | 每天 3:45 PM 市场时间 | 标准执行 |
| 月度快照 | `us_equity` + `feature_snapshot` 输入 | 每月 1-7 号重试窗口 | 依赖快照管线 |
| 月度 DCA | `us_equity` | 每月 1-7 号 + dedup | 定投策略 |
| 组合策略 | `quant_combo` | 跟随父平台 | 多策略组合 |

---

## 3. 插件开发规范

### 3.1 新增插件

**3.1.1 插件挂载配置**

```json
{
  "strategy_plugins": [{
    "strategy": "soxl_soxx_trend_income",
    "plugin": "market_regime_control",
    "signal_path": "gs://your-bucket/path/to/signal.json",
    "enabled": true,
    "expected_mode": "shadow"
  }]
}
```

**3.1.2 策略名字段自动同步**

插件配置中的 `strategy` 字段由 config-sync 层自动对齐到 `RUNTIME_TARGET_JSON.strategy_profile`。开发时填入正确的策略名作为文档，运行时如有不一致会自动修正并打印日志。

---

## 4. 配置管理规范

### 4.1 环境变量

**唯一数据源**: `RUNTIME_TARGET_JSON`

```json
{
  "platform_id": "schwab",
  "strategy_profile": "soxl_soxx_trend_income",
  "execution_mode": "live",
  "dry_run_only": false,
  "account_scope": "default",
  "scheduler": {
    "main_time": "45 15 * * *",
    "precheck_time": "45 9 * * *",
    "probe_time": "35 9,15 * * *",
    "timezone": "America/New_York"
  }
}
```

**已废弃**: `STRATEGY_PROFILE` 独立环境变量。所有平台必须从 `RUNTIME_TARGET_JSON` 读取策略名。

### 4.2 环境变量模板

每个平台必须提供 `.env.example` 文件，列出所有必需和可选的环境变量及其默认值。

### 4.3 配置同步机制

模块加载时自动执行：
1. 从 `RUNTIME_TARGET_JSON` 确定当前策略名
2. 扫描 `STRATEGY_PLUGIN_MOUNTS_JSON`，修正其中过期的 `strategy` 字段
3. 扫描 `MONITOR_DISPATCH_TARGETS_JSON`，修正其中过期的 `strategy_profile` 字段
4. 打印 `[config-sync]` 日志记录修正

---

## 5. 调度与监控规范

### 5.1 Scheduler 配置

| 市场 | 日历时区 | Cron | 说明 |
|---|---|---|---|
| US Equity | `America/New_York` | `45 15 * * *` | 收盘前 15 分钟 |
| HK Equity | `Asia/Hong_Kong` | `45 15 * * *` | 收盘前 15 分钟 |
| 月度 DCA | `America/New_York` | `45 15 1-7 * *` | 每月前 7 天重试 |
| Crypto | `UTC` | GitHub Actions `schedule` | 24/7 市场 |

**规则: Scheduler 时区 = 市场时区，不是服务区域。**

### 5.2 每个服务的 Scheduler 任务

| 用途 | 路径 | 典型 Cron |
|---|---|---|
| 主执行 | `/run` | `45 15 * * *` |
| 盘前验证 | `/dry-run` | `45 9 * * 1-5` |
| 备用执行 | `/run` | `52 15 * * 1-5` |
| 监控调度 | `/monitor-dispatch` | `*/5 * * * *` |

### 5.3 监控体系

| 检查层 | 频率 | 失败动作 |
|---|---|---|
| `/health` | Cloud Run 健康检查 (连续) | 不切换流量 |
| `/probe` | 监控调度触发 | Telegram 告警 |
| `/dry-run` | 盘前 9:45 AM | Telegram 告警 |
| 备用执行 | 收盘前 8 分钟 | 执行 (dedup 跳过已成功) |
| 执行报告 | 每次执行后 | GCS 持久化 |

---

## 6. 部署与安全规范

### 6.1 部署前检查

```bash
# 1. 环境变量完整性
python scripts/check_required_env.py --platform=schwab --json

# 2. 策略-平台一致性
python scripts/validate_platform_consistency.py

# 3. 部署 (Cloud Run)
gcloud run deploy {service} --source . --region={region} --project={project} --clear-base-image

# 4. 部署后验证
curl {service_url}/health          # → 200 OK (模块导入自检)
curl {service_url}/dry-run -X POST # → 200 (全链路通过)
```

### 6.2 环境变量更新

- **添加变量**: 使用 `--update-env-vars`（追加，不覆盖已有）
- **禁止**: 使用 `--set-env-vars`（会删除所有未列出的变量）
- **JSON 变量**: 使用 Python subprocess 传值，避免 shell 转义问题

### 6.3 安全要求

- 密钥和 token 只能存储在 Secret Manager 或 GitHub Secrets
- 不得在 Git 中提交任何凭证
- Cloud Run 服务的 `run.invoker` 权限仅限于 scheduler SA + runtime SA
- 禁止 `allUsers` 作为 `run.invoker`
- Service Account 遵循最小权限原则
- 所有 SA key 必须使用 SYSTEM_MANAGED 类型

---

## 7. 检查清单

### 新增平台

```
[ ] 仓库结构完整 (main.py / strategy_registry / runtime_config / Dockerfile / .env.example)
[ ] strategy_registry.py: 导入所有相关策略包, 合并 catalog
[ ] strategy_registry.py: 定义 PlatformCapabilityMatrix
[ ] strategy_registry.py: 实现 get_platform_runtime_adapter 路由
[ ] runtime_config_support.py: PlatformRuntimeSettings dataclass 字段顺序正确
[ ] runtime_config_support.py: 从 RUNTIME_TARGET_JSON 读取策略名 (不读 STRATEGY_PROFILE)
[ ] main.py: 实现 /run /dry-run /probe /health /monitor-dispatch
[ ] main.py: /health 包含 importlib 模块导入自检
[ ] main.py: 实现 _normalize_plugin_mounts_strategy 和 config-sync
[ ] 创建 Cloud Scheduler 任务: main + precheck + backup + monitor-dispatcher
[ ] Scheduler 时区 = 市场时区
[ ] .env.example 列出所有环境变量
[ ] Cloud Run IAM: scheduler SA + runtime SA 有 run.invoker
[ ] Secret Manager: 所有凭证通过 secret 挂载
[ ] 部署后验证: /health 200, /dry-run 200
```

### 新增策略

```
[ ] 策略逻辑放在共享 pip 包 (不在平台仓库)
[ ] catalog.py: 注册 STRATEGY_PLATFORM_COMPATIBILITY
[ ] catalog.py: 注册 STRATEGY_METADATA (含 domain, cadence, status)
[ ] runtime_adapters.py: 实现 get_platform_runtime_adapter
[ ] 声明 required_inputs 和 supported_platforms
[ ] 发布新版本 pip 包
[ ] 平台 requirements.txt 更新 pin
[ ] 平台不需要改 strategy_registry.py (自动发现)
```

### 新增插件

```
[ ] 定义插件逻辑
[ ] 配置 STRATEGY_PLUGIN_MOUNTS_JSON (strategy 字段自动对齐)
[ ] 定义 signal_path (GCS 路径)
[ ] 配置 enabled + expected_mode
```

---

## 版本历史

| 版本 | 日期 | 变更 |
|---|---|---|
| 1.0 | 2026-06-30 | 初始版本: 完整的平台/策略/插件开发规范 |
