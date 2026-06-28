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

import json
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


if __name__ == "__main__":
    unittest.main()
