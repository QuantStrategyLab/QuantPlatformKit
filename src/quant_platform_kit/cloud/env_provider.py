"""
Environment Variable provider — 从 os.environ 读取配置。

适合简单部署场景或 CI 环境，无需任何云服务 SDK。

用法:
  QSL_CLOUD_PROVIDER=env
  密钥通过环境变量注入（大写+下划线格式）
  对象存储通过本地文件系统（与 local_provider 共享实现）

设计说明:
  - SecretStore: 从环境变量读取（优先 QSL_SECRET_<NAME>，其次 <NAME>）
  - SecretStoreReadWrite: 只读，写操作 noop（env vars 不可运行时写入）
  - ObjectStore / DocumentStore / ComputeDiscovery / DeploymentContext:
    直接复用 local_provider 实现。原因：env provider 的定位是"零依赖"，
    不引入任何云 SDK。对象存储和文档数据库不适合通过环境变量操作，
    local 文件系统是开发者/CI 场景下最合理的后端。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .local_provider import (
    LocalObjectStore,
    LocalDocumentStore,
    LocalComputeDiscovery,
    LocalDeploymentContext,
)

# Re-use local implementations — by design, not a gap.
# In CI and local dev, a real cloud bucket is unnecessary; a tmp dir suffices.
ObjectStore = LocalObjectStore
DocumentStore = LocalDocumentStore
ComputeDiscovery = LocalComputeDiscovery
DeploymentContext = LocalDeploymentContext


class EnvSecretStore:
    """密钥从环境变量读取。

    环境变量命名规则:
      secret-name → SECRET_NAME（大写 + 下划线）
      如 longport_token_hk → LONGPORT_TOKEN_HK

    可选前缀: QSL_SECRET_ 可防止与其他 env var 冲突。
    """

    def get_secret(self, secret_name: str, *, project_id: str | None = None) -> str:
        candidates = [
            f"QSL_SECRET_{secret_name.upper().replace('-', '_').replace('.', '_')}",
            secret_name.upper().replace("-", "_").replace(".", "_"),
        ]
        for key in candidates:
            val = os.environ.get(key)
            if val is not None:
                return val
        raise KeyError(
            f"Secret '{secret_name}' not found. "
            f"Tried env vars: {', '.join(candidates)}"
        )


class EnvSecretStoreReadWrite:
    """只读 + 占位写操作（env var 不支持运行时写入）。"""

    def get_secret(self, secret_name: str, *, project_id: str | None = None) -> str:
        return EnvSecretStore().get_secret(secret_name, project_id=project_id)

    def create_secret(self, secret_name: str, payload: str, *, project_id: str | None = None) -> str:
        import logging
        logging.getLogger(__name__).warning(
            "EnvSecretStore: create_secret is a no-op (env vars cannot be written at runtime). "
            "Set env var '%s' manually.",
            secret_name.upper().replace("-", "_"),
        )
        return "env-noop"

    def update_secret(self, secret_name: str, payload: str, *, project_id: str | None = None) -> str:
        return self.create_secret(secret_name, payload, project_id=project_id)

    def destroy_latest_secret(self, secret_name: str, *, project_id: str | None = None) -> None:
        pass
