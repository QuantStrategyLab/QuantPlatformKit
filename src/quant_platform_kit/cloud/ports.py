"""
Cloud provider abstraction layer — quant-platform-kit 的云服务接口定义。

每个 Protocol 定义一个云服务品类（密钥管理、对象存储、文档数据库等），
GcpProvider 是默认实现（保持现有行为不变），
社区可通过 env PROVIDER=aws|local 切换到其他实现。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


# ──────────────────────────────────────────────────────────────────────
#  Secret Store — 密钥管理（Secret Manager / AWS Secrets Manager / env）
# ──────────────────────────────────────────────────────────────────────

@runtime_checkable
class SecretStore(Protocol):
    """密钥读取接口（最低必要操作集，不包含写权限）"""

    def get_secret(self, secret_name: str, *, project_id: str | None = None) -> str:
        """读取密钥的 latest version，返回明文。"""
        ...


@runtime_checkable
class SecretStoreReadWrite(SecretStore, Protocol):
    """密钥读写接口（用于需要轮换/刷新的场景，如令牌自动更新）"""

    def create_secret(self, secret_name: str, payload: str, *, project_id: str | None = None) -> str:
        """创建新密钥，返回版本名。"""
        ...

    def update_secret(self, secret_name: str, payload: str, *, project_id: str | None = None) -> str:
        """添加新版本，返回版本名。"""
        ...

    def destroy_latest_secret(self, secret_name: str, *, project_id: str | None = None) -> None:
        """销毁 latest 版本（用于令牌刷新时清理旧版）。"""
        ...


# ──────────────────────────────────────────────────────────────────────
#  Object Store — 对象存储（GCS / S3 / 本地文件系统）
# ──────────────────────────────────────────────────────────────────────

@runtime_checkable
class ObjectStore(Protocol):
    """对象存储接口。URI 格式由实现方决定：
    - GCP:   gs://bucket/key
    - AWS:   s3://bucket/key
    - Local: file:///absolute/path 或 /absolute/path
    """

    def read_text(self, uri: str) -> str:
        """读取文本对象。"""
        ...

    def read_bytes(self, uri: str) -> bytes:
        """读取二进制对象。"""
        ...

    def write_text(self, uri: str, data: str, content_type: str = "text/plain") -> str:
        """写入文本对象，返回 URI。"""
        ...

    def write_bytes(self, uri: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """写入二进制对象，返回 URI。"""
        ...

    def exists(self, uri: str) -> bool:
        """检查对象是否存在。"""
        ...

    def list(self, prefix: str) -> list[str]:
        """列出指定前缀下的所有对象。"""
        ...


# ──────────────────────────────────────────────────────────────────────
#  Document Store — 文档型 KV（Firestore / DynamoDB）
# ──────────────────────────────────────────────────────────────────────

@runtime_checkable
class DocumentStore(Protocol):
    """文档型键值存储接口（collection / document 模型）。"""

    def get(self, collection: str, document_id: str) -> dict | None:
        """读取文档，不存在返回 None。"""
        ...

    def set(self, collection: str, document_id: str, data: dict) -> None:
        """写入文档（覆盖写）。"""
        ...

    def update(self, collection: str, document_id: str, fields: dict) -> None:
        """合并更新指定字段。"""
        ...

    def delete(self, collection: str, document_id: str) -> None:
        """删除文档。"""
        ...


# ──────────────────────────────────────────────────────────────────────
#  Compute Discovery — 计算资源发现（GCE / EC2）
# ──────────────────────────────────────────────────────────────────────

@runtime_checkable
class ComputeDiscovery(Protocol):
    """解析计算实例网络地址。"""

    def resolve_instance_ip(
        self,
        instance_name: str,
        zone: str,
        *,
        project_id: str | None = None,
        prefer_internal: bool = True,
    ) -> str:
        """返回实例的 IP 地址。"""
        ...


# ──────────────────────────────────────────────────────────────────────
#  Deployment Context — 部署上下文（Cloud Run / ECS / 自托管）
# ──────────────────────────────────────────────────────────────────────

@runtime_checkable
class DeploymentContext(Protocol):
    """当前部署环境的元信息。"""

    @property
    def project_id(self) -> str:
        """当前项目/账号 ID。"""
        ...

    @property
    def region(self) -> str | None:
        """当前区域，未知则返回 None。"""
        ...

    def fetch_id_token(self, audience: str) -> str:
        """获取面向 audience 的身份令牌（用于服务间认证）。"""
        ...
