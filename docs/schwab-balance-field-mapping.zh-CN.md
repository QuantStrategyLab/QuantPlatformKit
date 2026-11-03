# Schwab 资金字段对照（研究快照）

> 状态：部分可执行。`developer.schwab.com` 规格正文本轮仍无法公开抓取（HTTP 403）。
> 下列映射以社区 OpenAPI / schwab-sdk 字段注释为**次级证据**，并在代码中 fail-closed：
> 有专用字段则用之；缺失才回退；绝不把现金乘杠杆冒充购买力。

## PortfolioSnapshot 映射

| 我方字段 | 优先券商字段 | 回退 | 证据等级 | 备注 |
|---|---|---|---|---|
| `cash_balance` | `cashAvailableForTrading` | 无（缺失/非法则拒绝快照） | 次级 + 既有契约 | 可交易现金，可为 0/负 |
| `buying_power` | `buyingPower` → `availableFunds` | `cashAvailableForTrading`（floor≥0） | 次级 | 现金户常缺专用字段 |
| `total_equity` | `liquidationValue` | cash + 全部持仓市值 | 次级 + 既有契约 | 回退不代表完整保证金权益 |
| metadata 提现 | `cashAvailableForWithdrawal` | `null`（缺失保持未知） | 次级 | 不并入 buying_power |

## 明确不做

- 不猜测 `buying_power = 2×cash`
- 不在 CharlesSchwabPlatform 复制第二套 adapter
- 不把旧 cash≡buying_power 双写标成 PASS

## 关闭条件

取得 Schwab Retail Trader API 官方 `currentBalances` 字段定义正文后，复核本表并在需要时收紧/改名；在此之前保持 source metadata 可审计。
