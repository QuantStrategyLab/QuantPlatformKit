"""
quant-platform-kit 云服务抽象层。

通过环境变量 QSL_CLOUD_PROVIDER 选择后端：
  "gcp"   — Google Cloud（默认，保持现有行为）
  "aws"   — Amazon Web Services
  "azure" — Microsoft Azure
  "local" — 本地文件系统（开发/测试，无需云账号）
  "env"   — 环境变量 + 本地文件系统（CI）

用法:
    from quant_platform_kit.cloud import get_secret_store, get_object_store

    secret = get_secret_store().get_secret("my_key")
    data = get_object_store().read_text("gs://bucket/path")
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .ports import (
        SecretStore,
        SecretStoreReadWrite,
        ObjectStore,
        DocumentStore,
        ComputeDiscovery,
        DeploymentContext,
    )

_PROVIDER: str | None = None


def _resolve_provider() -> str:
    global _PROVIDER
    if _PROVIDER is None:
        _PROVIDER = os.environ.get("QSL_CLOUD_PROVIDER", "gcp").lower().strip()
    return _PROVIDER


def set_provider(provider: str) -> None:
    """运行时切换 provider（主要用于测试）。"""
    global _PROVIDER
    _PROVIDER = provider.lower().strip()


def reset_provider() -> None:
    """清除缓存，下次调用重新读取环境变量。"""
    global _PROVIDER
    _PROVIDER = None


# ──────────────────────────────────────────────────────────────────────
#  Factory functions
# ──────────────────────────────────────────────────────────────────────

def get_secret_store() -> SecretStore:
    """获取 SecretStore 实例（只读）。"""
    p = _resolve_provider()
    if p == "gcp":
        from .gcp_provider import GcpSecretStore
        return GcpSecretStore()
    elif p == "aws":
        from .aws_provider import AwsSecretStore
        return AwsSecretStore()
    elif p == "azure":
        from .azure_provider import AzureSecretStore
        return AzureSecretStore()
    elif p == "local":
        from .local_provider import LocalSecretStore
        return LocalSecretStore()
    elif p == "env":
        from .env_provider import EnvSecretStore
        return EnvSecretStore()
    else:
        raise ValueError(f"Unknown QSL_CLOUD_PROVIDER: {p}")


def get_secret_store_rw() -> SecretStoreReadWrite:
    """获取 SecretStore 读写实例（用于令牌刷新等场景）。"""
    p = _resolve_provider()
    if p == "gcp":
        from .gcp_provider import GcpSecretStoreReadWrite
        return GcpSecretStoreReadWrite()
    elif p == "aws":
        from .aws_provider import AwsSecretStoreReadWrite
        return AwsSecretStoreReadWrite()
    elif p == "azure":
        from .azure_provider import AzureSecretStoreReadWrite
        return AzureSecretStoreReadWrite()
    elif p == "local":
        from .local_provider import LocalSecretStoreReadWrite
        return LocalSecretStoreReadWrite()
    elif p == "env":
        from .env_provider import EnvSecretStoreReadWrite
        return EnvSecretStoreReadWrite()
    else:
        raise ValueError(f"Unknown QSL_CLOUD_PROVIDER: {p}")


def get_object_store(project_id: str | None = None) -> ObjectStore:
    """获取 ObjectStore 实例。

    Args:
        project_id: 仅 GCP provider 使用，传递给 GCS Client 构造函数。
    """
    p = _resolve_provider()
    if p == "gcp":
        from .gcp_provider import GcpObjectStore
        return GcpObjectStore(project_id=project_id)
    elif p == "aws":
        from .aws_provider import AwsObjectStore
        return AwsObjectStore()
    elif p == "azure":
        from .azure_provider import AzureObjectStore
        return AzureObjectStore()
    elif p in ("local", "env"):
        from .local_provider import LocalObjectStore
        return LocalObjectStore()
    else:
        raise ValueError(f"Unknown QSL_CLOUD_PROVIDER: {p}")


def get_document_store() -> DocumentStore:
    """获取 DocumentStore 实例。"""
    p = _resolve_provider()
    if p == "gcp":
        from .gcp_provider import GcpDocumentStore
        return GcpDocumentStore()
    elif p == "aws":
        from .aws_provider import AwsDocumentStore
        return AwsDocumentStore()
    elif p == "azure":
        from .azure_provider import AzureDocumentStore
        return AzureDocumentStore()
    elif p in ("local", "env"):
        from .local_provider import LocalDocumentStore
        return LocalDocumentStore()
    else:
        raise ValueError(f"Unknown QSL_CLOUD_PROVIDER: {p}")


def get_compute_discovery() -> ComputeDiscovery:
    """获取 ComputeDiscovery 实例。"""
    p = _resolve_provider()
    if p == "gcp":
        from .gcp_provider import GcpComputeDiscovery
        return GcpComputeDiscovery()
    elif p == "aws":
        from .aws_provider import AwsComputeDiscovery
        return AwsComputeDiscovery()
    elif p == "azure":
        from .azure_provider import AzureComputeDiscovery
        return AzureComputeDiscovery()
    elif p in ("local", "env"):
        from .local_provider import LocalComputeDiscovery
        return LocalComputeDiscovery()
    else:
        raise ValueError(f"Unknown QSL_CLOUD_PROVIDER: {p}")


def get_deployment_context() -> DeploymentContext:
    """获取 DeploymentContext 实例。"""
    p = _resolve_provider()
    if p == "gcp":
        from .gcp_provider import GcpDeploymentContext
        return GcpDeploymentContext()
    elif p == "aws":
        from .aws_provider import AwsDeploymentContext
        return AwsDeploymentContext()
    elif p == "azure":
        from .azure_provider import AzureDeploymentContext
        return AzureDeploymentContext()
    elif p in ("local", "env"):
        from .local_provider import LocalDeploymentContext
        return LocalDeploymentContext()
    else:
        raise ValueError(f"Unknown QSL_CLOUD_PROVIDER: {p}")


# ──────────────────────────────────────────────────────────────────────
#  Re-export ports for convenience
# ──────────────────────────────────────────────────────────────────────

from .ports import (
    SecretStore,
    SecretStoreReadWrite,
    ObjectStore,
    DocumentStore,
    ComputeDiscovery,
    DeploymentContext,
)

__all__ = [
    "SecretStore",
    "SecretStoreReadWrite",
    "ObjectStore",
    "DocumentStore",
    "ComputeDiscovery",
    "DeploymentContext",
    "get_secret_store",
    "get_secret_store_rw",
    "get_object_store",
    "get_document_store",
    "get_compute_discovery",
    "get_deployment_context",
    "set_provider",
    "reset_provider",
]
