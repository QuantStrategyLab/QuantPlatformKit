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

import importlib
import os
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from .ports import (
        SecretStore,
        SecretStoreReadWrite,
        ObjectStore,
        DocumentStore,
        ComputeDiscovery,
        DeploymentContext,
    )

_T = TypeVar("_T")

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
#  Lazy provider factories
# ──────────────────────────────────────────────────────────────────────

def _lazy_factory(module_name: str, class_name: str) -> Callable[[], Any]:
    """Return a callable that imports and instantiates *class_name* on demand."""

    def build() -> Any:
        module = importlib.import_module(module_name, package=__name__)
        return getattr(module, class_name)()

    return build


def _lazy_object_store_factory(
    module_name: str,
    class_name: str,
    *,
    accepts_project_id: bool = False,
) -> Callable[[str | None], Any]:
    """Return a callable that builds an object store, importing it on demand."""

    def build(project_id: str | None = None) -> Any:
        module = importlib.import_module(module_name, package=__name__)
        factory = getattr(module, class_name)
        return factory(project_id=project_id) if accepts_project_id else factory()

    return build


_SECRET_STORE_FACTORIES: dict[str, Callable[[], SecretStore]] = {
    "gcp": _lazy_factory(".gcp_provider", "GcpSecretStore"),
    "aws": _lazy_factory(".aws_provider", "AwsSecretStore"),
    "azure": _lazy_factory(".azure_provider", "AzureSecretStore"),
    "local": _lazy_factory(".local_provider", "LocalSecretStore"),
    "env": _lazy_factory(".env_provider", "EnvSecretStore"),
}

_SECRET_STORE_RW_FACTORIES: dict[str, Callable[[], SecretStoreReadWrite]] = {
    "gcp": _lazy_factory(".gcp_provider", "GcpSecretStoreReadWrite"),
    "aws": _lazy_factory(".aws_provider", "AwsSecretStoreReadWrite"),
    "azure": _lazy_factory(".azure_provider", "AzureSecretStoreReadWrite"),
    "local": _lazy_factory(".local_provider", "LocalSecretStoreReadWrite"),
    "env": _lazy_factory(".env_provider", "EnvSecretStoreReadWrite"),
}

_OBJECT_STORE_FACTORIES: dict[str, Callable[[str | None], ObjectStore]] = {
    "gcp": _lazy_object_store_factory(
        ".gcp_provider", "GcpObjectStore", accepts_project_id=True
    ),
    "aws": _lazy_object_store_factory(".aws_provider", "AwsObjectStore"),
    "azure": _lazy_object_store_factory(".azure_provider", "AzureObjectStore"),
    "local": _lazy_object_store_factory(".local_provider", "LocalObjectStore"),
    "env": _lazy_object_store_factory(".local_provider", "LocalObjectStore"),
}

_DOCUMENT_STORE_FACTORIES: dict[str, Callable[[], DocumentStore]] = {
    "gcp": _lazy_factory(".gcp_provider", "GcpDocumentStore"),
    "aws": _lazy_factory(".aws_provider", "AwsDocumentStore"),
    "azure": _lazy_factory(".azure_provider", "AzureDocumentStore"),
    "local": _lazy_factory(".local_provider", "LocalDocumentStore"),
    "env": _lazy_factory(".local_provider", "LocalDocumentStore"),
}

_COMPUTE_DISCOVERY_FACTORIES: dict[str, Callable[[], ComputeDiscovery]] = {
    "gcp": _lazy_factory(".gcp_provider", "GcpComputeDiscovery"),
    "aws": _lazy_factory(".aws_provider", "AwsComputeDiscovery"),
    "azure": _lazy_factory(".azure_provider", "AzureComputeDiscovery"),
    "local": _lazy_factory(".local_provider", "LocalComputeDiscovery"),
    "env": _lazy_factory(".local_provider", "LocalComputeDiscovery"),
}

_DEPLOYMENT_CONTEXT_FACTORIES: dict[str, Callable[[], DeploymentContext]] = {
    "gcp": _lazy_factory(".gcp_provider", "GcpDeploymentContext"),
    "aws": _lazy_factory(".aws_provider", "AwsDeploymentContext"),
    "azure": _lazy_factory(".azure_provider", "AzureDeploymentContext"),
    "local": _lazy_factory(".local_provider", "LocalDeploymentContext"),
    "env": _lazy_factory(".local_provider", "LocalDeploymentContext"),
}


def _factory_for(factories: dict[str, Callable[..., _T]], provider: str) -> Callable[..., _T]:
    try:
        return factories[provider]
    except KeyError:
        raise ValueError(f"Unknown QSL_CLOUD_PROVIDER: {provider}") from None


# ──────────────────────────────────────────────────────────────────────
#  Factory functions
# ──────────────────────────────────────────────────────────────────────

def get_secret_store() -> SecretStore:
    """获取 SecretStore 实例（只读）。"""
    p = _resolve_provider()
    return _factory_for(_SECRET_STORE_FACTORIES, p)()


def get_secret_store_rw() -> SecretStoreReadWrite:
    """获取 SecretStore 读写实例（用于令牌刷新等场景）。"""
    p = _resolve_provider()
    return _factory_for(_SECRET_STORE_RW_FACTORIES, p)()


def get_object_store(project_id: str | None = None) -> ObjectStore:
    """获取 ObjectStore 实例。

    Args:
        project_id: 仅 GCP provider 使用，传递给 GCS Client 构造函数。
    """
    p = _resolve_provider()
    return _factory_for(_OBJECT_STORE_FACTORIES, p)(project_id)


def get_document_store() -> DocumentStore:
    """获取 DocumentStore 实例。"""
    p = _resolve_provider()
    return _factory_for(_DOCUMENT_STORE_FACTORIES, p)()


def get_compute_discovery() -> ComputeDiscovery:
    """获取 ComputeDiscovery 实例。"""
    p = _resolve_provider()
    return _factory_for(_COMPUTE_DISCOVERY_FACTORIES, p)()


def get_deployment_context() -> DeploymentContext:
    """获取 DeploymentContext 实例。"""
    p = _resolve_provider()
    return _factory_for(_DEPLOYMENT_CONTEXT_FACTORIES, p)()



# ──────────────────────────────────────────────────────────────────────
#  Re-export ports for convenience
# ──────────────────────────────────────────────────────────────────────

from .ports import (
    SecretStore,
    SecretStoreReadWrite,
    ObjectStore,
    DocumentStore,
    DocumentStoreAtomicOwnership,
    ComputeDiscovery,
    DeploymentContext,
)

__all__ = [
    "SecretStore",
    "SecretStoreReadWrite",
    "ObjectStore",
    "DocumentStore",
    "DocumentStoreAtomicOwnership",
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
