"""
Tests for the cloud abstraction layer (quant_platform_kit.cloud).

Covers:
  - Factory functions (get_secret_store, get_object_store, ...)
  - Provider switching (QSL_CLOUD_PROVIDER env var / set_provider)
  - Local provider implementation (read/write/exists/list)
  - Port interface conformance (runtime_checkable)
  - Secret fallback behavior (local → env var)
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from quant_platform_kit.cloud import (
    get_secret_store,
    get_secret_store_rw,
    get_object_store,
    get_document_store,
    get_compute_discovery,
    get_deployment_context,
    set_provider,
    reset_provider,
    SecretStore,
    SecretStoreReadWrite,
    ObjectStore,
    DocumentStore,
    ComputeDiscovery,
    DeploymentContext,
)
from quant_platform_kit.cloud.local_provider import (
    LocalSecretStore,
    LocalSecretStoreReadWrite,
    LocalObjectStore,
    LocalDocumentStore,
    LocalComputeDiscovery,
    LocalDeploymentContext,
)
from quant_platform_kit.cloud.env_provider import EnvSecretStore


class CloudProviderSwitchTests(unittest.TestCase):
    """Test that factory functions respect the provider selection."""

    def setUp(self):
        reset_provider()

    def tearDown(self):
        reset_provider()
        for key in list(os.environ.keys()):
            if key.startswith("QSL_"):
                del os.environ[key]

    def test_default_provider_is_gcp(self):
        """Default QSL_CLOUD_PROVIDER should be 'gcp'."""
        from quant_platform_kit.cloud import _resolve_provider
        # should not raise
        self.assertEqual(_resolve_provider(), "gcp")

    def test_set_provider_local(self):
        """set_provider('local') should make factory return local instances."""
        set_provider("local")
        store = get_secret_store()
        self.assertIsInstance(store, LocalSecretStore)
        obj = get_object_store()
        self.assertIsInstance(obj, LocalObjectStore)

    def test_set_provider_gcp(self):
        """set_provider('gcp') should make factory return GCP instances."""
        set_provider("gcp")
        store = get_secret_store()
        # Verify it returns something that conforms to the protocol
        self.assertIsInstance(store, SecretStore)

    def test_env_var_respected(self):
        """Setting QSL_CLOUD_PROVIDER=local via env should be picked up after reset."""
        os.environ["QSL_CLOUD_PROVIDER"] = "local"
        reset_provider()
        store = get_secret_store()
        self.assertIsInstance(store, LocalSecretStore)

    def test_invalid_provider_raises(self):
        set_provider("nonexistent")
        with self.assertRaises(ValueError):
            get_secret_store()

    def test_secret_store_readwrite(self):
        """get_secret_store_rw returns a SecretStoreReadWrite-compatible instance."""
        set_provider("local")
        rw = get_secret_store_rw()
        self.assertIsInstance(rw, SecretStoreReadWrite)


class SecretStoreInterfaceTests(unittest.TestCase):
    """Test that SecretStore implementations correctly handle get_secret."""

    def setUp(self):
        reset_provider()
        self._tmpdir = tempfile.mkdtemp()
        self._orig_qsl = Path.home() / ".qsl"
        # Monkey-patch QSL_DIR for LocalSecretStore
        import quant_platform_kit.cloud.local_provider as lp
        self._orig_secrets_dir = lp.SECRETS_DIR
        lp.SECRETS_DIR = Path(self._tmpdir) / "secrets"
        lp.SECRETS_DIR.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        import quant_platform_kit.cloud.local_provider as lp
        lp.SECRETS_DIR = self._orig_secrets_dir
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)
        reset_provider()

    def _write_secret_file(self, name: str, value: str):
        (Path(self._tmpdir) / "secrets" / name).write_text(value)

    def test_local_get_secret(self):
        self._write_secret_file("test-key", "hello-world")
        store = LocalSecretStore()
        self.assertEqual(store.get_secret("test-key"), "hello-world")

    def test_local_get_secret_fallback_to_env(self):
        """LocalSecretStore falls back to env var when file not found."""
        os.environ["TEST_SECRET_KEY"] = "from-env"
        store = LocalSecretStore()
        self.assertEqual(store.get_secret("test-secret-key"), "from-env")
        del os.environ["TEST_SECRET_KEY"]

    def test_local_get_secret_missing_raises(self):
        store = LocalSecretStore()
        with self.assertRaises(FileNotFoundError):
            store.get_secret("nonexistent-key")

    def test_local_secret_readwrite(self):
        rw = LocalSecretStoreReadWrite()
        rw.create_secret("new-key", "new-value")
        self.assertEqual(rw.get_secret("new-key"), "new-value")
        rw.update_secret("new-key", "updated")
        self.assertEqual(rw.get_secret("new-key"), "updated")
        rw.destroy_latest_secret("new-key")
        with self.assertRaises(FileNotFoundError):
            rw.get_secret("new-key")


class ObjectStoreInterfaceTests(unittest.TestCase):
    """Test LocalObjectStore implementation."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        import quant_platform_kit.cloud.local_provider as lp
        self._orig_storage_dir = lp.STORAGE_DIR
        lp.STORAGE_DIR = Path(self._tmpdir) / "storage"

    def tearDown(self):
        import quant_platform_kit.cloud.local_provider as lp
        lp.STORAGE_DIR = self._orig_storage_dir
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_write_and_read_text(self):
        store = LocalObjectStore()
        uri = store.write_text(f"{self._tmpdir}/hello.txt", "world")
        self.assertEqual(store.read_text(uri), "world")

    def test_write_and_read_bytes(self):
        store = LocalObjectStore()
        uri = store.write_bytes(f"{self._tmpdir}/data.bin", b"binary")
        self.assertEqual(store.read_bytes(uri), b"binary")

    def test_exists(self):
        store = LocalObjectStore()
        uri = store.write_text(f"{self._tmpdir}/existent.txt", "yes")
        self.assertTrue(store.exists(uri))
        self.assertFalse(store.exists(f"{self._tmpdir}/missing.txt"))

    def test_list(self):
        store = LocalObjectStore()
        store.write_text(f"{self._tmpdir}/a.txt", "a")
        store.write_text(f"{self._tmpdir}/b.txt", "b")
        listing = store.list(self._tmpdir)
        self.assertIn(f"{self._tmpdir}/a.txt", listing)
        self.assertIn(f"{self._tmpdir}/b.txt", listing)

    def test_gs_uri_mapping(self):
        store = LocalObjectStore()
        uri = store.write_text("gs://bucket/key.txt", "cloud-data")
        self.assertTrue(store.exists("gs://bucket/key.txt"))
        self.assertEqual(store.read_text("gs://bucket/key.txt"), "cloud-data")

    def test_s3_uri_mapping(self):
        store = LocalObjectStore()
        uri = store.write_text("s3://bucket/key.txt", "aws-data")
        self.assertTrue(store.exists("s3://bucket/key.txt"))
        self.assertEqual(store.read_text("s3://bucket/key.txt"), "aws-data")


class DocumentStoreInterfaceTests(unittest.TestCase):
    """Test LocalDocumentStore implementation."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()
        import quant_platform_kit.cloud.local_provider as lp
        self._orig_data_dir = lp.DATA_DIR
        lp.DATA_DIR = Path(self._tmpdir) / "data"

    def tearDown(self):
        import quant_platform_kit.cloud.local_provider as lp
        lp.DATA_DIR = self._orig_data_dir
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_set_and_get(self):
        store = LocalDocumentStore()
        store.set("test_coll", "doc1", {"key": "value", "num": 42})
        doc = store.get("test_coll", "doc1")
        self.assertEqual(doc["key"], "value")
        self.assertEqual(doc["num"], 42)

    def test_get_missing(self):
        store = LocalDocumentStore()
        self.assertIsNone(store.get("test_coll", "nonexistent"))

    def test_update(self):
        store = LocalDocumentStore()
        store.set("test_coll", "doc1", {"a": 1})
        store.update("test_coll", "doc1", {"b": 2})
        doc = store.get("test_coll", "doc1")
        self.assertEqual(doc["a"], 1)
        self.assertEqual(doc["b"], 2)

    def test_delete(self):
        store = LocalDocumentStore()
        store.set("test_coll", "doc1", {"key": "value"})
        store.delete("test_coll", "doc1")
        self.assertIsNone(store.get("test_coll", "doc1"))

    def test_update_creates_if_missing(self):
        store = LocalDocumentStore()
        store.update("test_coll", "new_doc", {"a": 1})
        doc = store.get("test_coll", "new_doc")
        self.assertEqual(doc["a"], 1)


class ComputeDiscoveryInterfaceTests(unittest.TestCase):
    """Test LocalComputeDiscovery."""

    def test_local_returns_env_var(self):
        os.environ["MY_INSTANCE_IP"] = "10.0.0.1"
        discoverer = LocalComputeDiscovery()
        ip = discoverer.resolve_instance_ip("my-instance", "us-east1")
        self.assertEqual(ip, "10.0.0.1")
        del os.environ["MY_INSTANCE_IP"]

    def test_local_fallback_to_qsl_mock(self):
        os.environ["QSL_MOCK_IP"] = "127.0.0.1"
        discoverer = LocalComputeDiscovery()
        ip = discoverer.resolve_instance_ip("unknown-instance", "us-east1")
        self.assertEqual(ip, "127.0.0.1")
        del os.environ["QSL_MOCK_IP"]


class DeploymentContextInterfaceTests(unittest.TestCase):
    """Test LocalDeploymentContext."""

    def test_project_id_from_env(self):
        os.environ["QSL_PROJECT_ID"] = "test-project"
        ctx = LocalDeploymentContext()
        self.assertEqual(ctx.project_id, "test-project")
        del os.environ["QSL_PROJECT_ID"]

    def test_project_id_default(self):
        ctx = LocalDeploymentContext()
        self.assertEqual(ctx.project_id, "local-dev")

    def test_region(self):
        os.environ["QSL_REGION"] = "us-central1"
        ctx = LocalDeploymentContext()
        self.assertEqual(ctx.region, "us-central1")
        del os.environ["QSL_REGION"]

    def test_id_token(self):
        os.environ["QSL_ID_TOKEN"] = "mock-token"
        ctx = LocalDeploymentContext()
        self.assertEqual(ctx.fetch_id_token("aud"), "mock-token")
        del os.environ["QSL_ID_TOKEN"]


class EnvSecretStoreTests(unittest.TestCase):
    """Test EnvSecretStore (env var provider)."""

    def setUp(self):
        self._env_keys = []

    def tearDown(self):
        for k in self._env_keys:
            os.environ.pop(k, None)

    def _set_env(self, key: str, value: str):
        os.environ[key] = value
        self._env_keys.append(key)

    def test_direct_env_var(self):
        self._set_env("MY_API_KEY", "secret123")
        store = EnvSecretStore()
        self.assertEqual(store.get_secret("my-api-key"), "secret123")

    def test_qsl_prefixed_env_var_takes_priority(self):
        self._set_env("QSL_SECRET_MY_KEY", "preferred")
        self._set_env("MY_KEY", "fallback")
        store = EnvSecretStore()
        self.assertEqual(store.get_secret("my-key"), "preferred")

    def test_missing_raises(self):
        store = EnvSecretStore()
        with self.assertRaises(KeyError):
            store.get_secret("completely-unknown-key")


class PortInterfaceConformanceTests(unittest.TestCase):
    """Verify that all implementations conform to the port Protocols."""

    def test_local_secret_store_is_secret_store(self):
        self.assertIsInstance(LocalSecretStore(), SecretStore)
        self.assertIsInstance(LocalSecretStoreReadWrite(), SecretStoreReadWrite)
        self.assertIsInstance(LocalSecretStoreReadWrite(), SecretStore)

    def test_env_secret_store_is_secret_store(self):
        self.assertIsInstance(EnvSecretStore(), SecretStore)

    def test_local_object_store_is_object_store(self):
        self.assertIsInstance(LocalObjectStore(), ObjectStore)

    def test_local_document_store_is_document_store(self):
        self.assertIsInstance(LocalDocumentStore(), DocumentStore)

    def test_local_compute_discovery_is_compute_discovery(self):
        self.assertIsInstance(LocalComputeDiscovery(), ComputeDiscovery)

    def test_local_deployment_context_is_deployment_context(self):
        self.assertIsInstance(LocalDeploymentContext(), DeploymentContext)


class FactoryIntegrationTests(unittest.TestCase):
    """End-to-end tests using the factory with local provider."""

    def setUp(self):
        set_provider("local")
        self._tmpdir = tempfile.mkdtemp()
        import quant_platform_kit.cloud.local_provider as lp
        self._orig_secrets = lp.SECRETS_DIR
        self._orig_storage = lp.STORAGE_DIR
        self._orig_data = lp.DATA_DIR
        lp.SECRETS_DIR = Path(self._tmpdir) / "secrets"
        lp.STORAGE_DIR = Path(self._tmpdir) / "storage"
        lp.DATA_DIR = Path(self._tmpdir) / "data"
        lp.SECRETS_DIR.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        import quant_platform_kit.cloud.local_provider as lp
        lp.SECRETS_DIR = self._orig_secrets
        lp.STORAGE_DIR = self._orig_storage
        lp.DATA_DIR = self._orig_data
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)
        reset_provider()

    def test_secret_store_roundtrip(self):
        rw = get_secret_store_rw()
        rw.create_secret("integration-key", "integration-value")
        ro = get_secret_store()
        self.assertEqual(ro.get_secret("integration-key"), "integration-value")

    def test_object_store_roundtrip(self):
        store = get_object_store()
        uri = store.write_text(f"{self._tmpdir}/test.txt", "hello-storage")
        self.assertEqual(store.read_text(uri), "hello-storage")
        self.assertTrue(store.exists(uri))

    def test_document_store_roundtrip(self):
        store = get_document_store()
        store.set("integration_coll", "test_doc", {"field": "value"})
        doc = store.get("integration_coll", "test_doc")
        self.assertEqual(doc, {"field": "value"})

    def test_secret_store_readwrite_only(self):
        """Verify get_secret_store returns read-only interface (no write methods)."""
        ro = get_secret_store()
        # should not have create/update/destroy
        self.assertFalse(hasattr(ro, "create_secret"))
        self.assertFalse(hasattr(ro, "update_secret"))
        self.assertFalse(hasattr(ro, "destroy_latest_secret"))


class AwsProviderRegistrationTests(unittest.TestCase):
    """Verify AWS provider is correctly registered in factory functions."""

    def setUp(self):
        set_provider("aws")

    def tearDown(self):
        reset_provider()

    def test_aws_secret_store_resolves(self):
        from quant_platform_kit.cloud.aws_provider import AwsSecretStore
        store = get_secret_store()
        self.assertIsInstance(store, AwsSecretStore)

    def test_aws_secret_store_rw_resolves(self):
        from quant_platform_kit.cloud.aws_provider import AwsSecretStoreReadWrite
        rw = get_secret_store_rw()
        self.assertIsInstance(rw, AwsSecretStoreReadWrite)

    def test_aws_object_store_resolves(self):
        from quant_platform_kit.cloud.aws_provider import AwsObjectStore
        store = get_object_store()
        self.assertIsInstance(store, AwsObjectStore)

    def test_aws_document_store_resolves(self):
        from quant_platform_kit.cloud.aws_provider import AwsDocumentStore
        store = get_document_store()
        self.assertIsInstance(store, AwsDocumentStore)

    def test_aws_compute_discovery_resolves(self):
        from quant_platform_kit.cloud.aws_provider import AwsComputeDiscovery
        disc = get_compute_discovery()
        self.assertIsInstance(disc, AwsComputeDiscovery)

    def test_aws_deployment_context_resolves(self):
        from quant_platform_kit.cloud.aws_provider import AwsDeploymentContext
        ctx = get_deployment_context()
        self.assertIsInstance(ctx, AwsDeploymentContext)

    def test_aws_providers_satisfy_port_interfaces(self):
        """All AWS providers should pass runtime_checkable Protocol checks."""
        from quant_platform_kit.cloud.ports import (
            SecretStore,
            SecretStoreReadWrite,
            ObjectStore,
            DocumentStore,
            ComputeDiscovery,
            DeploymentContext,
        )
        self.assertIsInstance(get_secret_store(), SecretStore)
        self.assertIsInstance(get_secret_store_rw(), SecretStoreReadWrite)
        self.assertIsInstance(get_object_store(), ObjectStore)
        self.assertIsInstance(get_document_store(), DocumentStore)
        self.assertIsInstance(get_compute_discovery(), ComputeDiscovery)
        self.assertIsInstance(get_deployment_context(), DeploymentContext)


class AzureProviderRegistrationTests(unittest.TestCase):
    """Verify Azure provider is correctly registered in factory functions."""

    def setUp(self):
        set_provider("azure")

    def tearDown(self):
        reset_provider()

    def test_azure_secret_store_resolves(self):
        from quant_platform_kit.cloud.azure_provider import AzureSecretStore
        store = get_secret_store()
        self.assertIsInstance(store, AzureSecretStore)

    def test_azure_secret_store_rw_resolves(self):
        from quant_platform_kit.cloud.azure_provider import AzureSecretStoreReadWrite
        rw = get_secret_store_rw()
        self.assertIsInstance(rw, AzureSecretStoreReadWrite)

    def test_azure_object_store_resolves(self):
        from quant_platform_kit.cloud.azure_provider import AzureObjectStore
        store = get_object_store()
        self.assertIsInstance(store, AzureObjectStore)

    def test_azure_document_store_resolves(self):
        from quant_platform_kit.cloud.azure_provider import AzureDocumentStore
        store = get_document_store()
        self.assertIsInstance(store, AzureDocumentStore)

    def test_azure_compute_discovery_resolves(self):
        from quant_platform_kit.cloud.azure_provider import AzureComputeDiscovery
        disc = get_compute_discovery()
        self.assertIsInstance(disc, AzureComputeDiscovery)

    def test_azure_deployment_context_resolves(self):
        from quant_platform_kit.cloud.azure_provider import AzureDeploymentContext
        ctx = get_deployment_context()
        self.assertIsInstance(ctx, AzureDeploymentContext)

    def test_azure_providers_satisfy_port_interfaces(self):
        """All Azure providers should pass runtime_checkable Protocol checks."""
        self.assertIsInstance(get_secret_store(), SecretStore)
        self.assertIsInstance(get_secret_store_rw(), SecretStoreReadWrite)
        self.assertIsInstance(get_object_store(), ObjectStore)
        self.assertIsInstance(get_document_store(), DocumentStore)
        self.assertIsInstance(get_compute_discovery(), ComputeDiscovery)
        self.assertIsInstance(get_deployment_context(), DeploymentContext)


if __name__ == "__main__":
    unittest.main()


class GcpDocumentOwnershipTests(unittest.TestCase):
    """Deterministic SDK conflict simulations, not real Firestore validation."""

    def setUp(self):
        import sys
        from types import SimpleNamespace
        from unittest.mock import MagicMock, patch
        from quant_platform_kit.cloud.gcp_provider import GcpDocumentStore

        self.store = GcpDocumentStore()
        self.other = GcpDocumentStore()
        self.client = MagicMock()
        self.store._client = self.other._client = self.client
        self.document = self.client.collection.return_value.document.return_value
        self.data = None
        self.version = 0
        self.before_create = None
        self.before_commit = None
        self.create_error = None
        self.commit_error = None
        self.after_commit_error = None
        self.Conflict = type("Conflict", (Exception,), {})
        self.AlreadyExists = type("AlreadyExists", (self.Conflict,), {})
        self.after_create_error = None

        def create(data, *, retry):
            self.assertIsNone(retry)
            if self.before_create:
                hook, self.before_create = self.before_create, None
                hook()
            if self.create_error:
                raise self.create_error
            if self.data is not None:
                raise self.AlreadyExists("already exists")
            self.data = dict(data)
            self.version += 1
            if self.after_create_error:
                raise self.after_create_error

        def get(*, transaction, retry):
            self.assertIsNone(retry)
            transaction.read_version = self.version
            data = dict(self.data) if self.data is not None else None
            return SimpleNamespace(exists=data is not None, to_dict=lambda: data)

        def transactional(callback):
            def run(transaction):
                result = callback(transaction)
                if self.before_commit:
                    self.before_commit()
                if self.commit_error:
                    raise self.commit_error
                if transaction.read_version != self.version:
                    raise self.Conflict("transaction conflict")
                if transaction.delete.called:
                    transaction.delete.assert_called_once_with(self.document)
                    self.data = None
                    self.version += 1
                if self.after_commit_error:
                    raise self.after_commit_error
                return result
            return run

        self.document.create.side_effect = create
        self.document.get.side_effect = get
        self.client.transaction.side_effect = lambda **kwargs: MagicMock()
        firestore = SimpleNamespace(transactional=transactional)
        modules = {
            "google": SimpleNamespace(),
            "google.cloud": SimpleNamespace(firestore=firestore),
            "google.api_core": SimpleNamespace(),
            "google.api_core.exceptions": SimpleNamespace(Conflict=self.Conflict, AlreadyExists=self.AlreadyExists),
        }
        self.patch = patch.dict(sys.modules, modules)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_optional_protocol_leaves_existing_providers_compatible(self):
        from quant_platform_kit.cloud import DocumentStoreAtomicOwnership
        from quant_platform_kit.cloud.aws_provider import AwsDocumentStore
        from quant_platform_kit.cloud.azure_provider import AzureDocumentStore

        self.assertIsInstance(self.store, DocumentStore)
        self.assertIsInstance(self.store, DocumentStoreAtomicOwnership)
        for store in (LocalDocumentStore(), AwsDocumentStore(), AzureDocumentStore()):
            with self.subTest(provider=type(store).__name__):
                self.assertIsInstance(store, DocumentStore)
                self.assertNotIsInstance(store, DocumentStoreAtomicOwnership)

    def test_create_does_not_reacquire_even_for_same_owner(self):
        self.assertTrue(self.store.create_if_absent("locks", "state", {"owner_id": "one"}))
        self.assertFalse(self.store.create_if_absent("locks", "state", {"owner_id": "one"}))
        self.assertFalse(self.other.create_if_absent("locks", "state", {"owner_id": "two"}))
        self.assertEqual(self.data, {"owner_id": "one"})
        self.document.get.assert_not_called()
        self.document.set.assert_not_called()

    def test_interleaved_claims_have_one_winner(self):
        outcomes = []
        self.before_create = lambda: outcomes.append(
            self.other.create_if_absent("locks", "state", {"owner_id": "two"})
        )
        outcomes.append(self.store.create_if_absent("locks", "state", {"owner_id": "one"}))
        self.assertEqual(outcomes, [True, False])
        self.assertEqual(self.data, {"owner_id": "two"})

    def test_delete_requires_current_owner_and_committed_transaction(self):
        self.assertFalse(self.store.delete_if_owner("locks", "state", "one"))
        self.store.create_if_absent("locks", "state", {"owner_id": "one"})
        self.assertFalse(self.store.delete_if_owner("locks", "state", "two"))
        self.assertTrue(self.store.delete_if_owner("locks", "state", "one"))
        self.other.create_if_absent("locks", "state", {"owner_id": "two"})
        self.assertFalse(self.store.delete_if_owner("locks", "state", "one"))
        self.assertEqual(self.data, {"owner_id": "two"})
        self.client.transaction.assert_called_with(max_attempts=1)
        self.document.delete.assert_not_called()

    def test_owner_change_between_read_and_commit_cannot_delete_new_owner(self):
        self.store.create_if_absent("locks", "state", {"owner_id": "one"})
        def replace_owner():
            self.data = {"owner_id": "two"}
            self.version += 1
        self.before_commit = replace_owner
        with self.assertRaises(self.Conflict):
            self.store.delete_if_owner("locks", "state", "one")
        self.assertEqual(self.data, {"owner_id": "two"})

    def test_empty_or_invalid_owner_is_rejected_before_io(self):
        for owner in (None, "", "  ", 1, True):
            with self.subTest(owner=owner):
                with self.assertRaises(ValueError):
                    self.store.create_if_absent("locks", "state", {"owner_id": owner})
                with self.assertRaises(ValueError):
                    self.store.delete_if_owner("locks", "state", owner)
        with self.assertRaises(ValueError):
            self.store.create_if_absent("locks", "state", {})
        self.client.collection.assert_not_called()

    def test_create_errors_are_not_competition_results(self):
        for error in (TimeoutError("unknown outcome"), PermissionError("denied"), self.Conflict("aborted")):
            with self.subTest(error=type(error).__name__):
                self.create_error = error
                with self.assertRaises(type(error)):
                    self.store.create_if_absent("locks", "state", {"owner_id": "one"})

    def test_transaction_errors_never_return_success(self):
        self.store.create_if_absent("locks", "state", {"owner_id": "one"})
        for error in (TimeoutError("unknown outcome"), PermissionError("denied"), self.Conflict("aborted")):
            with self.subTest(error=type(error).__name__):
                self.commit_error = error
                with self.assertRaises(type(error)):
                    self.store.delete_if_owner("locks", "state", "one")
                self.assertEqual(self.data, {"owner_id": "one"})

    def test_delete_ack_loss_raises_even_when_server_deleted(self):
        self.store.create_if_absent("locks", "state", {"owner_id": "one"})
        self.after_commit_error = TimeoutError("unknown outcome")
        with self.assertRaises(TimeoutError):
            self.store.delete_if_owner("locks", "state", "one")
        self.assertIsNone(self.data)

    def test_create_ack_loss_does_not_authorize_same_owner_retry(self):
        self.after_create_error = TimeoutError("unknown outcome")
        with self.assertRaises(TimeoutError):
            self.store.create_if_absent("locks", "state", {"owner_id": "one"})
        self.assertEqual(self.data, {"owner_id": "one"})
        self.after_create_error = None
        self.assertFalse(self.store.create_if_absent("locks", "state", {"owner_id": "one"}))

    def test_transaction_read_error_propagates_without_delete(self):
        self.document.get.side_effect = TimeoutError("read unavailable")
        with self.assertRaises(TimeoutError):
            self.store.delete_if_owner("locks", "state", "one")
        self.document.delete.assert_not_called()

    def test_normal_document_operations_keep_original_sdk_calls(self):
        from types import SimpleNamespace
        self.document.get.side_effect = None
        self.document.get.return_value = SimpleNamespace(exists=True, to_dict=lambda: {"value": 1})
        self.assertEqual(self.store.get("items", "one"), {"value": 1})
        self.document.get.assert_called_once_with()
        self.store.set("items", "one", {"value": 2})
        self.document.set.assert_called_once_with({"value": 2})
        self.store.update("items", "one", {"value": 3})
        self.document.update.assert_called_once_with({"value": 3})
        self.store.delete("items", "one")
        self.document.delete.assert_called_once_with()
        self.client.transaction.assert_not_called()
