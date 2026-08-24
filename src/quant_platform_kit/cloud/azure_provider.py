"""
Azure provider implementation — follows the same Protocol interface as GCP/AWS.

All *Provider classes are stateless singletons (lazy-init Azure SDK clients).
Activate via: export QSL_CLOUD_PROVIDER=azure

Requires:
  azure-identity          — DefaultAzureCredential
  azure-keyvault-secrets  — SecretClient
  azure-storage-blob      — BlobServiceClient
  azure-cosmos            — CosmosClient (optional, for DocumentStore)

URI format:
  az://storageaccount/container/path/to/blob  — ObjectStore
"""

from __future__ import annotations

import os



# ══════════════════════════════════════════════════════════════════════
#  Secret Store — Azure Key Vault
# ══════════════════════════════════════════════════════════════════════


def _resolve_keyvault_name() -> str:
    """Resolve Key Vault name from env var. Required for secret operations."""
    name = os.environ.get("AZURE_KEY_VAULT_NAME") or os.environ.get("KEY_VAULT_NAME")
    if not name:
        raise RuntimeError(
            "AZURE_KEY_VAULT_NAME env var is required for Azure SecretStore. "
            "Set it to your Key Vault name (not the full URL)."
        )
    return name


def _keyvault_url(vault_name: str) -> str:
    return f"https://{vault_name}.vault.azure.net"


class AzureSecretStore:
    """Read-only secret access via Azure Key Vault."""

    _client = None

    @property
    def client(self):
        if self._client is None:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient

            vault = _resolve_keyvault_name()
            credential = DefaultAzureCredential()
            self._client = SecretClient(vault_url=_keyvault_url(vault), credential=credential)
        return self._client

    def get_secret(self, secret_name: str, *, project_id: str | None = None) -> str:
        return self.client.get_secret(secret_name).value


class AzureSecretStoreReadWrite:
    """Read-write secret access for token rotation scenarios."""

    _client = None

    @property
    def client(self):
        if self._client is None:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient

            vault = _resolve_keyvault_name()
            credential = DefaultAzureCredential()
            self._client = SecretClient(vault_url=_keyvault_url(vault), credential=credential)
        return self._client

    def get_secret(self, secret_name: str, *, project_id: str | None = None) -> str:
        return self.client.get_secret(secret_name).value

    def create_secret(self, secret_name: str, payload: str, *, project_id: str | None = None) -> str:
        result = self.client.set_secret(secret_name, payload)
        return result.id or secret_name

    def update_secret(self, secret_name: str, payload: str, *, project_id: str | None = None) -> str:
        result = self.client.set_secret(secret_name, payload)
        return result.id or secret_name

    def destroy_latest_secret(self, secret_name: str, *, project_id: str | None = None) -> None:
        try:
            poller = self.client.begin_delete_secret(secret_name)
            poller.result()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════
#  Object Store — Azure Blob Storage
# ══════════════════════════════════════════════════════════════════════


def _resolve_storage_account() -> str:
    """Resolve Storage Account name from env var."""
    name = os.environ.get("AZURE_STORAGE_ACCOUNT") or os.environ.get("AZURE_STORAGE_ACCOUNT_NAME")
    if not name:
        raise RuntimeError(
            "AZURE_STORAGE_ACCOUNT env var is required for Azure ObjectStore. "
            "Set it to your Storage Account name."
        )
    return name


class AzureObjectStore:
    """Azure Blob Storage implementation.

    URI format: az://<account>/<container>/path/to/blob
    """

    _client = None

    @property
    def client(self):
        if self._client is None:
            from azure.identity import DefaultAzureCredential
            from azure.storage.blob import BlobServiceClient

            account = _resolve_storage_account()
            url = f"https://{account}.blob.core.windows.net"
            credential = DefaultAzureCredential()
            self._client = BlobServiceClient(account_url=url, credential=credential)
        return self._client

    def _parse_uri(self, uri: str) -> tuple[str, str, str]:
        """Return (account, container, blob_path)."""
        if not uri.startswith("az://"):
            raise ValueError(f"AzureObjectStore requires az:// URI, got: {uri!r}")
        path = uri[5:]
        parts = path.split("/", 2)
        if len(parts) < 3:
            raise ValueError(
                f"Invalid az:// URI: {uri!r}. Expected az://account/container/blob/path"
            )
        return parts[0], parts[1], parts[2]

    def _get_blob_client(self, container: str, blob: str):
        return self.client.get_blob_client(container=container, blob=blob)

    def read_text(self, uri: str) -> str:
        _, container, blob = self._parse_uri(uri)
        return self._get_blob_client(container, blob).download_blob().content_as_text()

    def read_bytes(self, uri: str) -> bytes:
        _, container, blob = self._parse_uri(uri)
        return self._get_blob_client(container, blob).download_blob().content_as_bytes()

    def write_text(self, uri: str, data: str, content_type: str = "text/plain") -> str:
        account, container, blob = self._parse_uri(uri)
        self._get_blob_client(container, blob).upload_blob(
            data.encode("utf-8"), overwrite=True, content_settings={"content_type": content_type}
        )
        return uri

    def create_text(self, uri: str, data: str, content_type: str = "text/plain") -> bool:
        """Create a blob only if it does not already exist."""
        _, container, blob = self._parse_uri(uri)
        try:
            self._get_blob_client(container, blob).upload_blob(
                data.encode("utf-8"),
                overwrite=False,
                content_settings={"content_type": content_type},
            )
            return True
        except Exception as exc:
            from azure.core.exceptions import ResourceExistsError

            if isinstance(exc, ResourceExistsError):
                return False
            raise

    def write_bytes(self, uri: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        account, container, blob = self._parse_uri(uri)
        self._get_blob_client(container, blob).upload_blob(
            data, overwrite=True, content_settings={"content_type": content_type}
        )
        return uri

    def exists(self, uri: str) -> bool:
        _, container, blob = self._parse_uri(uri)
        try:
            return self._get_blob_client(container, blob).exists()
        except Exception:
            return False

    def list(self, prefix: str) -> list[str]:
        """List blobs under az:// URI prefix."""
        account, container, path_prefix = self._parse_uri(prefix)
        container_client = self.client.get_container_client(container)
        results = []
        for blob in container_client.list_blobs(name_starts_with=path_prefix):
            results.append(f"az://{account}/{container}/{blob.name}")
        return results


# ══════════════════════════════════════════════════════════════════════
#  Document Store — Cosmos DB
# ══════════════════════════════════════════════════════════════════════


def _resolve_cosmos_endpoint() -> str:
    """Resolve Cosmos DB endpoint from env var."""
    endpoint = os.environ.get("AZURE_COSMOS_ENDPOINT") or os.environ.get("COSMOS_ENDPOINT")
    if not endpoint:
        raise RuntimeError(
            "AZURE_COSMOS_ENDPOINT env var is required for Azure DocumentStore. "
            "Set it to your Cosmos DB account endpoint URL."
        )
    return endpoint


class AzureDocumentStore:
    """Cosmos DB implementation (collection/document model).

    Each collection name maps to a Cosmos container.
    Database name defaults to 'quant-platform' unless overridden
    via AZURE_COSMOS_DATABASE env var.

    document_id maps to item 'id' field (Cosmos requirement).
    """

    _client = None

    @property
    def client(self):
        if self._client is None:
            from azure.cosmos import CosmosClient
            from azure.identity import DefaultAzureCredential

            endpoint = _resolve_cosmos_endpoint()
            credential = DefaultAzureCredential()
            self._client = CosmosClient(endpoint, credential=credential)
        return self._client

    def _database_name(self) -> str:
        return os.environ.get("AZURE_COSMOS_DATABASE", "quant-platform")

    def _get_container(self, collection: str):
        db = self.client.get_database_client(self._database_name())
        return db.get_container_client(collection)

    def _ensure_container(self, collection: str):
        """Get or create the container for a collection."""
        db = self.client.get_database_client(self._database_name())
        try:
            return db.get_container_client(collection)
        except Exception:
            # Container may not exist yet; create it with /id partition key
            db.create_container_if_not_exists(
                id=collection,
                partition_key={"paths": ["/id"], "kind": "Hash"},
            )
            return db.get_container_client(collection)

    def get(self, collection: str, document_id: str) -> dict | None:
        container = self._get_container(collection)
        try:
            item = container.read_item(item=document_id, partition_key=document_id)
            # Remove Cosmos system fields
            return {k: v for k, v in item.items() if not k.startswith("_")}
        except Exception:
            return None

    def set(self, collection: str, document_id: str, data: dict) -> None:
        container = self._ensure_container(collection)
        item = {"id": document_id, **data}
        container.upsert_item(item)

    def update(self, collection: str, document_id: str, fields: dict) -> None:
        container = self._get_container(collection)
        try:
            item = container.read_item(item=document_id, partition_key=document_id)
            item.update(fields)
            container.upsert_item(item)
        except Exception:
            # Item doesn't exist yet; create it
            container.upsert_item({"id": document_id, **fields})

    def delete(self, collection: str, document_id: str) -> None:
        container = self._get_container(collection)
        try:
            container.delete_item(item=document_id, partition_key=document_id)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════
#  Compute Discovery — Azure VM
# ══════════════════════════════════════════════════════════════════════


class AzureComputeDiscovery:
    """Resolve Azure VM IP via Azure Resource Management API.

    Uses DefaultAzureCredential — works with managed identity on VMs,
    or service principal via env vars (AZURE_CLIENT_ID / AZURE_TENANT_ID / AZURE_CLIENT_SECRET).
    """

    _client = None

    @property
    def client(self):
        if self._client is None:
            from azure.identity import DefaultAzureCredential
            from azure.mgmt.compute import ComputeManagementClient

            subscription = os.environ.get("AZURE_SUBSCRIPTION_ID", "")
            if not subscription:
                raise RuntimeError(
                    "AZURE_SUBSCRIPTION_ID env var is required for Azure ComputeDiscovery."
                )
            credential = DefaultAzureCredential()
            self._client = ComputeManagementClient(credential, subscription)
        return self._client

    def resolve_instance_ip(
        self,
        instance_name: str,
        zone: str,
        *,
        project_id: str | None = None,
        prefer_internal: bool = True,
    ) -> str:
        resource_group = os.environ.get("AZURE_RESOURCE_GROUP", "")
        if not resource_group:
            raise RuntimeError(
                "AZURE_RESOURCE_GROUP env var is required for Azure ComputeDiscovery."
            )

        vm = self.client.virtual_machines.get(
            resource_group_name=resource_group,
            vm_name=instance_name,
            expand="instanceView",
        )

        for iface_ref in vm.network_profile.network_interfaces:
            iface_id = iface_ref.id
            iface_name = iface_id.split("/")[-1] if iface_id else ""
            if iface_name:
                from azure.mgmt.network import NetworkManagementClient
                from azure.identity import DefaultAzureCredential

                subscription = os.environ.get("AZURE_SUBSCRIPTION_ID", "")
                net_client = NetworkManagementClient(
                    DefaultAzureCredential(), subscription
                )
                nic = net_client.network_interfaces.get(
                    resource_group_name=resource_group,
                    network_interface_name=iface_name,
                )
                for ip_cfg in nic.ip_configurations:
                    if prefer_internal and ip_cfg.private_ip_address:
                        return ip_cfg.private_ip_address
                    if ip_cfg.public_ip_address and ip_cfg.public_ip_address.id:
                        pip_name = ip_cfg.public_ip_address.id.split("/")[-1]
                        pip = net_client.public_ip_addresses.get(
                            resource_group_name=resource_group,
                            public_ip_address_name=pip_name,
                        )
                        if pip.ip_address:
                            return pip.ip_address

        raise RuntimeError(
            f"No IP address found for Azure VM '{instance_name}' "
            f"in resource group '{resource_group}'"
        )


# ══════════════════════════════════════════════════════════════════════
#  Deployment Context — Azure VM / Container Apps
# ══════════════════════════════════════════════════════════════════════


class AzureDeploymentContext:
    """Azure deployment context.

    Resolves identity via Azure Instance Metadata Service (IMDS)
    when running on Azure VM or Container Apps.
    """

    @property
    def project_id(self) -> str:
        """Resolve subscription ID from env or IMDS."""
        env = os.environ.get("AZURE_SUBSCRIPTION_ID", "")
        if env:
            return env
        try:
            return _fetch_azure_metadata("instance/compute/subscriptionId")
        except Exception:
            return ""

    @property
    def region(self) -> str | None:
        """Resolve region from env or IMDS."""
        env = os.environ.get("AZURE_REGION") or os.environ.get("AZURE_LOCATION")
        if env:
            return env
        try:
            return _fetch_azure_metadata("instance/compute/location")
        except Exception:
            return None

    def fetch_id_token(self, audience: str) -> str:
        """Fetch a managed identity token for the given audience.

        On Azure, this returns an OAuth2 access token from IMDS
        for the system-assigned managed identity.

        The ``audience`` should be the resource URI of the target service,
        e.g. ``https://vault.azure.net`` or ``https://storage.azure.com``.
        """
        try:
            return _fetch_azure_managed_identity_token(audience)
        except Exception as exc:
            raise RuntimeError(
                "AzureDeploymentContext.fetch_id_token: unable to fetch managed identity token. "
                "Ensure the process runs on an Azure VM or Container App with managed identity enabled, "
                "or set the AZURE_CLIENT_ID / AZURE_CLIENT_SECRET / AZURE_TENANT_ID env vars "
                "for service principal fallback."
            ) from exc


# ══════════════════════════════════════════════════════════════════════
#  Internal helpers
# ══════════════════════════════════════════════════════════════════════


def _fetch_azure_metadata(path: str) -> str:
    """Fetch a value from the Azure Instance Metadata Service (IMDS)."""
    import urllib.request

    req = urllib.request.Request(
        f"http://169.254.169.254/metadata/{path}?api-version=2021-02-01&format=text",
        headers={"Metadata": "true"},
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return resp.read().decode("utf-8").strip()


def _fetch_azure_managed_identity_token(audience: str) -> str:
    """Fetch an OAuth2 access token from Azure IMDS for managed identity.

    Returns the raw access_token string (JWT).
    """
    import urllib.request
    import json as _json

    identity_endpoint = os.environ.get("IDENTITY_ENDPOINT")
    identity_header = os.environ.get("IDENTITY_HEADER")

    if identity_endpoint and identity_header:
        # Azure Container Apps / App Service
        url = f"{identity_endpoint}?resource={audience}&api-version=2019-08-01"
        req = urllib.request.Request(url, headers={"X-IDENTITY-HEADER": identity_header})
    else:
        # Azure VM (IMDS)
        url = (
            f"http://169.254.169.254/metadata/identity/oauth2/token"
            f"?resource={audience}&api-version=2018-02-01"
        )
        req = urllib.request.Request(url, headers={"Metadata": "true"})

    with urllib.request.urlopen(req, timeout=10) as resp:
        body = _json.loads(resp.read().decode("utf-8"))
        return body["access_token"]
