# 离线 dry-run 迁移检查

`quant_platform_kit.common.runtime_control_checks.validate_dry_run_consistency`
是显式调用的纯函数。目前没有平台采用它；本次不改变运行解析器、部署工作流、依赖 pin 或交易准入路径。

```python
from quant_platform_kit.common.runtime_control_checks import validate_dry_run_consistency

validate_dry_run_consistency(
    declared_dry_run_only=True,
    env={"EXAMPLE_DRY_RUN_ONLY": "true"},
    flag_name="EXAMPLE_DRY_RUN_ONLY",
)
```

输入是已解析的目标布尔值和显式环境映射。变量缺失时默认 dry-run；显式空值或拼写错误抛出
`RuntimeControlError`。`FLAG` 和 `QSL_FLAG` 同时存在时必须一致，不通过优先级隐藏冲突。
最终变量必须与目标一致；提供 RuntimeControl 时还须与其 mode 一致。目标关闭时也保留检查。

`RuntimeControl.mode=paper` 表示券商模拟执行，对应 `dry_run_only=False`。
旧 `RuntimeTarget.execution_mode=paper` 是 `dry_run_only=True` 的历史别名，不能直接当作新 mode。

返回值仅说明配置一致，不授予执行权限。身份、policy 绑定、平台能力、预留现金和订单准入由调用方另外检查。
后续平台采用须单独提交，附 trading-diff 说明和真实调用链测试；现有旧解析器的优先级不变。

验证：`PYTHONPATH=src python3 -m pytest -q tests/test_runtime_control_checks.py tests/test_runtime_control.py`。

[English](runtime_control_checks.md)
