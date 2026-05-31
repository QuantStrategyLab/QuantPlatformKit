# QuantConnect Connector


## 中文摘要

- 用途：本文档围绕 `QuantConnect Connector`，用于理解 `QuantPlatformKit` 的配置、运行、部署、研究或验收边界。
- 主要覆盖：`Example`、`References`。
- 阅读顺序：先确认边界、输入输出和权限要求，再执行文档里的命令、CI、dry-run、发布或切换步骤。
- 风险提示：涉及实盘、密钥、权限、Cloud Run、交易所或券商 API 的变更，必须先在测试环境或 dry-run 验证；不要只凭示例直接修改生产。
- 英文正文保留更完整的命令、字段名和配置键；如果摘要和正文不一致，以正文中的实际命令和配置为准。
`quant_platform_kit.quantconnect` contains small, dependency-free helpers for platform repositories that deploy a strategy to QuantConnect Cloud while keeping account wiring and secrets outside this public repository.

The connector supports:

- QuantConnect REST API authentication headers from a user id and API token
- live algorithm management calls for authenticate, create, read, list, stop, and liquidate
- QuantConnect live deployment payloads
- Interactive Brokers brokerage payloads for QuantConnect Cloud
- redacted payload helpers for logs and notifications

It intentionally does not contain production account ids, usernames, passwords, node ids, or project ids. Private platform configuration should provide those values from Secret Manager, GitHub Actions secrets, or another deployment secret store.

## Example

```python
from quant_platform_kit.quantconnect import (
    InteractiveBrokersBrokerageSettings,
    QuantConnectCredentials,
    QuantConnectLiveConnector,
    QuantConnectLiveDeployment,
    QuantConnectRestClient,
)

credentials = QuantConnectCredentials.from_env(env)
brokerage = InteractiveBrokersBrokerageSettings.from_env(env)

deployment = QuantConnectLiveDeployment(
    project_id=12345678,
    compile_id="compile-id-from-quantconnect",
    node_id="LN-node-id-from-quantconnect",
    brokerage=brokerage,
    data_providers={
        "InteractiveBrokersBrokerage": brokerage,
    },
    parameters={
        "strategy_profile": "example_strategy",
        "runtime_target": "quantconnect-cloud-slot-a",
    },
)

client = QuantConnectRestClient(credentials=credentials)
connector = QuantConnectLiveConnector(client)

# Use deployment.redacted_payload() for logs. Do not log deployment.to_payload().
result = connector.deploy(deployment)
```

The default environment variable names are:

```text
QUANTCONNECT_USER_ID
QUANTCONNECT_API_TOKEN
QUANTCONNECT_ORGANIZATION_ID

QUANTCONNECT_IB_USER_NAME
QUANTCONNECT_IB_ACCOUNT
QUANTCONNECT_IB_PASSWORD
QUANTCONNECT_IB_WEEKLY_RESTART_UTC_TIME
QUANTCONNECT_IB_FINANCIAL_ADVISORS_GROUP_FILTER
```

For a hybrid deployment, keep the target routing in a private platform repository or deployment secret:

```json
{
  "self_hosted": [
    {
      "strategy_profile": "tqqq_growth_income",
      "platform": "interactive_brokers",
      "account_selector": ["U00000000"]
    }
  ],
  "quantconnect_cloud": [
    {
      "strategy_profile": "example_strategy",
      "project_id": 12345678,
      "node_id": "LN-placeholder",
      "brokerage_secret": "qc-ibkr-slot-b"
    }
  ]
}
```

The public example above uses placeholders only. Real account mappings and brokerage credentials must stay in private runtime configuration.

## References

- QuantConnect Cloud API live management: <https://www.quantconnect.com/docs/v2/cloud-platform/api-reference/live-management>
- QuantConnect create live algorithm API: <https://www.quantconnect.com/docs/v2/cloud-platform/api-reference/live-management/create-live-algorithm>
- Lean CLI cloud live deploy: <https://www.quantconnect.com/docs/v2/lean-cli/api-reference/lean-cloud-live-deploy>
