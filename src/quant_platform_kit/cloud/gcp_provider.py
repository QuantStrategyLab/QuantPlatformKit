"""
Google Cloud 实现 — 完全兼容现有代码行为。
所有 *Provider 均为无状态单例（lazy-init client）。
"""

from __future__ import annotations

import os



# ══════════════════════════════════════════════════════════════════════
#  Secret Store — GCP Secret Manager
# ══════════════════════════════════════════════════════════════════════

class GcpSecretStore:
    """Read-only secret access via GCP Secret Manager."""

    def get_secret(self, secret_name: str, *, project_id: str | None = None) -> str:
        import google.cloud.secretmanager_v1 as secret_manager

        pid = project_id or _resolve_project_id()
        client = secret_manager.SecretManagerServiceClient()
        name = f"projects/{pid}/secrets/{secret_name}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("utf-8")


class GcpSecretStoreReadWrite:
    """Read-write secret access for token rotation scenarios."""

    _client = None

    @property
    def client(self):
        if self._client is None:
            import google.cloud.secretmanager_v1 as secret_manager

            self._client = secret_manager.SecretManagerServiceClient()
        return self._client

    def get_secret(self, secret_name: str, *, project_id: str | None = None) -> str:
        pid = project_id or _resolve_project_id()
        name = f"projects/{pid}/secrets/{secret_name}/versions/latest"
        response = self.client.access_secret_version(request={"name": name})
        return response.payload.data.decode("utf-8")

    def create_secret(self, secret_name: str, payload: str, *, project_id: str | None = None) -> str:
        pid = project_id or _resolve_project_id()
        parent = f"projects/{pid}"
        secret = {"replication": {"automatic": {}}}
        created = self.client.create_secret(
            request={"parent": parent, "secret_id": secret_name, "secret": secret}
        )
        version = self.client.add_secret_version(
            request={"parent": created.name, "payload": {"data": payload.encode("utf-8")}}
        )
        return version.name

    def update_secret(self, secret_name: str, payload: str, *, project_id: str | None = None) -> str:
        pid = project_id or _resolve_project_id()
        parent = f"projects/{pid}/secrets/{secret_name}"
        version = self.client.add_secret_version(
            request={"parent": parent, "payload": {"data": payload.encode("utf-8")}}
        )
        return version.name

    def destroy_latest_secret(self, secret_name: str, *, project_id: str | None = None) -> None:
        """销毁所有旧版本，保留 latest（最新且未销毁的版本）。"""
        pid = project_id or _resolve_project_id()
        parent = f"projects/{pid}/secrets/{secret_name}"
        try:
            versions = list(self.client.list_secret_versions(request={"parent": parent}))
            enabled = [v for v in versions if v.state.name == "ENABLED"]
            if len(enabled) <= 1:
                return
            enabled.sort(key=lambda v: v.name, reverse=True)
            for old in enabled[1:]:
                self.client.destroy_secret_version(request={"name": old.name})
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════
#  Object Store — GCS
# ══════════════════════════════════════════════════════════════════════

class GcpObjectStore:
    """Google Cloud Storage implementation.

    URI 格式: gs://bucket-name/path/to/blob
    """

    def __init__(self, project_id: str | None = None):
        self._project_id = project_id
        self._client = None

    @property
    def client(self):
        if self._client is None:
            from google.cloud import storage

            kwargs = {}
            if self._project_id:
                kwargs["project"] = self._project_id
            self._client = storage.Client(**kwargs)
        return self._client

    def _parse_uri(self, uri: str) -> tuple:
        """返回 (bucket_name, blob_path)。"""
        if uri.startswith("gs://"):
            path = uri[5:]
        else:
            path = uri
        bucket, _, blob = path.partition("/")
        return bucket, blob

    def read_text(self, uri: str) -> str:
        bucket, blob = self._parse_uri(uri)
        return self.client.bucket(bucket).blob(blob).download_as_text()

    def read_bytes(self, uri: str) -> bytes:
        bucket, blob = self._parse_uri(uri)
        return self.client.bucket(bucket).blob(blob).download_as_bytes()

    def write_text(self, uri: str, data: str, content_type: str = "text/plain") -> str:
        bucket, blob = self._parse_uri(uri)
        self.client.bucket(bucket).blob(blob).upload_from_string(data, content_type=content_type)
        return uri

    def write_bytes(self, uri: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        bucket, blob = self._parse_uri(uri)
        self.client.bucket(bucket).blob(blob).upload_from_string(data, content_type=content_type)
        return uri

    def exists(self, uri: str) -> bool:
        bucket, blob = self._parse_uri(uri)
        return self.client.bucket(bucket).blob(blob).exists()

    def list(self, prefix: str) -> list[str]:
        bucket, path = self._parse_uri(prefix)
        return [f"gs://{bucket}/{b.name}" for b in self.client.bucket(bucket).list_blobs(prefix=path)]


# ══════════════════════════════════════════════════════════════════════
#  Document Store — Firestore
# ══════════════════════════════════════════════════════════════════════

class GcpDocumentStore:
    """Firestore implementation (collection/document model)."""

    _client = None

    @property
    def client(self):
        if self._client is None:
            from google.cloud import firestore

            self._client = firestore.Client()
        return self._client

    def get(self, collection: str, document_id: str) -> dict | None:
        doc = self.client.collection(collection).document(document_id).get()
        return doc.to_dict() if doc.exists else None

    def set(self, collection: str, document_id: str, data: dict) -> None:
        self.client.collection(collection).document(document_id).set(data)

    def update(self, collection: str, document_id: str, fields: dict) -> None:
        self.client.collection(collection).document(document_id).update(fields)

    def delete(self, collection: str, document_id: str) -> None:
        self.client.collection(collection).document(document_id).delete()


# ══════════════════════════════════════════════════════════════════════
#  Compute Discovery — GCE Instance
# ══════════════════════════════════════════════════════════════════════

class GcpComputeDiscovery:
    """Resolve GCE instance IP via Compute Engine API."""

    def resolve_instance_ip(
        self,
        instance_name: str,
        zone: str,
        *,
        project_id: str | None = None,
        prefer_internal: bool = True,
    ) -> str:
        from google.cloud import compute_v1

        pid = project_id or _resolve_project_id()
        client = compute_v1.InstancesClient()
        instance = client.get(project=pid, zone=zone, instance=instance_name)

        for iface in instance.network_interfaces:
            if prefer_internal:
                return iface.network_i_p  # typo preserved from GCE API
            for access_config in iface.access_configs:
                if access_config.nat_i_p:
                    return access_config.nat_i_p
        return instance.network_interfaces[0].network_i_p


# ══════════════════════════════════════════════════════════════════════
#  Deployment Context — Cloud Run
# ══════════════════════════════════════════════════════════════════════

class GcpDeploymentContext:
    """Google Cloud deployment context (Cloud Run, GCE, etc.)."""

    @property
    def project_id(self) -> str:
        return _resolve_project_id()

    @property
    def region(self) -> str | None:
        return os.environ.get("CLOUD_RUN_REGION") or os.environ.get("GOOGLE_CLOUD_REGION")

    def fetch_id_token(self, audience: str) -> str:
        from google.auth.transport.requests import Request
        from google.oauth2 import id_token

        return id_token.fetch_id_token(Request(), audience)


# ══════════════════════════════════════════════════════════════════════
#  Internal helpers
# ══════════════════════════════════════════════════════════════════════

def _resolve_project_id() -> str:
    """从环境或 GCP metadata 获取 project_id。"""
    env = os.environ.get("GOOGLE_CLOUD_PROJECT") or os.environ.get("GCP_PROJECT")
    if env:
        return env
    try:
        import google.auth

        _, pid = google.auth.default()
        if pid:
            return pid
    except Exception:
        pass
    raise RuntimeError(
        "Cannot resolve GCP project ID. "
        "Set GOOGLE_CLOUD_PROJECT env var or configure application default credentials."
    )
