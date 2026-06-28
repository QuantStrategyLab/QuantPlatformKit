"""
Local filesystem provider — 无云服务依赖，用于开发/测试/离线环境。

数据存储在:
  ~/.qsl/secrets/       — 密钥（纯文本文件，文件名=密钥名）
  ~/.qsl/data/          — 文档（{collection}/{doc_id}.json）
  ~/.qsl/storage/       — 对象存储（按 URI 路径映射到文件系统）

设置 QSL_CLOUD_PROVIDER=local 即可启用。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import ports

QSL_DIR = Path.home() / ".qsl"
SECRETS_DIR = QSL_DIR / "secrets"
DATA_DIR = QSL_DIR / "data"
STORAGE_DIR = QSL_DIR / "storage"


def _ensure_dirs():
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)


# ══════════════════════════════════════════════════════════════════════
#  Secret Store — ~/.qsl/secrets/<name>
# ══════════════════════════════════════════════════════════════════════

class LocalSecretStore:
    """密钥存储在 ~/.qsl/secrets/<secret_name>，fallback 到环境变量。"""

    def get_secret(self, secret_name: str, *, project_id: str | None = None) -> str:
        _ensure_dirs()
        file = SECRETS_DIR / secret_name
        if file.exists():
            return file.read_text().strip()
        # fallback to env var: CSYMBOL-NAME → CSYMBOL_NAME (大写)
        env_name = secret_name.upper().replace("-", "_").replace(".", "_")
        val = os.environ.get(env_name)
        if val is not None:
            return val
        raise FileNotFoundError(
            f"Secret '{secret_name}' not found in {SECRETS_DIR} or env var '{env_name}'"
        )


class LocalSecretStoreReadWrite:
    """读写版本，用于令牌刷新场景。"""

    def get_secret(self, secret_name: str, *, project_id: str | None = None) -> str:
        return LocalSecretStore().get_secret(secret_name, project_id=project_id)

    def create_secret(self, secret_name: str, payload: str, *, project_id: str | None = None) -> str:
        _ensure_dirs()
        (SECRETS_DIR / secret_name).write_text(payload)
        return "local-v1"

    def update_secret(self, secret_name: str, payload: str, *, project_id: str | None = None) -> str:
        return self.create_secret(secret_name, payload, project_id=project_id)

    def destroy_latest_secret(self, secret_name: str, *, project_id: str | None = None) -> None:
        file = SECRETS_DIR / secret_name
        if file.exists():
            file.unlink()


# ══════════════════════════════════════════════════════════════════════
#  Object Store — ~/.qsl/storage/<uri-path>
# ══════════════════════════════════════════════════════════════════════

class LocalObjectStore:
    """对象存储映射到本地文件系统。

    URI 支持:
      /absolute/path        → /absolute/path
      file:///absolute/path → /absolute/path
      gs://bucket/key       → ~/.qsl/storage/gs/bucket/key
      s3://bucket/key       → ~/.qsl/storage/s3/bucket/key
    """

    def _to_local_path(self, uri: str) -> Path:
        if uri.startswith("file://"):
            return Path(uri[7:])
        if uri.startswith("gs://") or uri.startswith("s3://"):
            scheme = uri.split(":")[0]
            path_part = uri[len(scheme) + 3 :]  # skip "s3://"
            return STORAGE_DIR / scheme / path_part
        if uri.startswith("/"):
            return Path(uri)
        raise ValueError(f"Cannot resolve local path for URI: {uri}")

    def read_text(self, uri: str) -> str:
        return self._to_local_path(uri).read_text()

    def read_bytes(self, uri: str) -> bytes:
        return self._to_local_path(uri).read_bytes()

    def write_text(self, uri: str, data: str, content_type: str = "text/plain") -> str:
        path = self._to_local_path(uri)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data)
        return uri

    def write_bytes(self, uri: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        path = self._to_local_path(uri)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return uri

    def exists(self, uri: str) -> bool:
        return self._to_local_path(uri).exists()

    def list(self, prefix: str) -> list[str]:
        path = self._to_local_path(prefix)
        if not path.exists():
            return []
        return [str(p) for p in path.iterdir() if p.is_file()]


# ══════════════════════════════════════════════════════════════════════
#  Document Store — ~/.qsl/data/{collection}/{doc_id}.json
# ══════════════════════════════════════════════════════════════════════

class LocalDocumentStore:
    """文档存储为 JSON 文件。"""

    def get(self, collection: str, document_id: str) -> dict | None:
        _ensure_dirs()
        file = DATA_DIR / collection / f"{document_id}.json"
        if not file.exists():
            return None
        return json.loads(file.read_text())

    def set(self, collection: str, document_id: str, data: dict) -> None:
        _ensure_dirs()
        file = DATA_DIR / collection / f"{document_id}.json"
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(data, indent=2, default=str))

    def update(self, collection: str, document_id: str, fields: dict) -> None:
        existing = self.get(collection, document_id) or {}
        existing.update(fields)
        self.set(collection, document_id, existing)

    def delete(self, collection: str, document_id: str) -> None:
        file = DATA_DIR / collection / f"{document_id}.json"
        if file.exists():
            file.unlink()


# ══════════════════════════════════════════════════════════════════════
#  Compute Discovery — env vars
# ══════════════════════════════════════════════════════════════════════

class LocalComputeDiscovery:
    """从环境变量解析实例 IP（开发用）。"""

    def resolve_instance_ip(
        self,
        instance_name: str,
        zone: str,
        *,
        project_id: str | None = None,
        prefer_internal: bool = True,
    ) -> str:
        env_key = f"{instance_name.upper().replace('-', '_')}_IP"
        ip = os.environ.get(env_key) or os.environ.get("QSL_MOCK_IP", "127.0.0.1")
        return ip


# ══════════════════════════════════════════════════════════════════════
#  Deployment Context — env vars
# ══════════════════════════════════════════════════════════════════════

class LocalDeploymentContext:
    @property
    def project_id(self) -> str:
        return os.environ.get("QSL_PROJECT_ID", "local-dev")

    @property
    def region(self) -> str | None:
        return os.environ.get("QSL_REGION")

    def fetch_id_token(self, audience: str) -> str:
        return os.environ.get("QSL_ID_TOKEN", "mock-id-token")
