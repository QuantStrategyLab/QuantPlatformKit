"""
AWS provider implementation — follows the same Protocol interface as the GCP provider.

All *Provider classes are stateless singletons (lazy-init boto3 client).
Activate via: export QSL_CLOUD_PROVIDER=aws

Requires boto3 and appropriate AWS credentials
(env vars, ~/.aws/credentials, or IAM role).

URI format:
  s3://bucket-name/path/to/blob  — ObjectStore
"""

from __future__ import annotations

import json
import os

from . import ports


# ══════════════════════════════════════════════════════════════════════
#  Secret Store — AWS Secrets Manager
# ══════════════════════════════════════════════════════════════════════


class AwsSecretStore:
    """Read-only secret access via AWS Secrets Manager."""

    _client = None

    @property
    def client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client("secretsmanager", region_name=_resolve_aws_region())
        return self._client

    def get_secret(self, secret_name: str, *, project_id: str | None = None) -> str:
        response = self.client.get_secret_value(SecretId=secret_name)
        return response["SecretString"]


class AwsSecretStoreReadWrite:
    """Read-write secret access for token rotation scenarios."""

    _client = None

    @property
    def client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client("secretsmanager", region_name=_resolve_aws_region())
        return self._client

    def get_secret(self, secret_name: str, *, project_id: str | None = None) -> str:
        response = self.client.get_secret_value(SecretId=secret_name)
        return response["SecretString"]

    def create_secret(self, secret_name: str, payload: str, *, project_id: str | None = None) -> str:
        response = self.client.create_secret(Name=secret_name, SecretString=payload)
        return response["ARN"]

    def update_secret(self, secret_name: str, payload: str, *, project_id: str | None = None) -> str:
        response = self.client.put_secret_value(SecretId=secret_name, SecretString=payload)
        return response["ARN"]

    def destroy_latest_secret(self, secret_name: str, *, project_id: str | None = None) -> None:
        try:
            self.client.delete_secret(SecretId=secret_name, ForceDeleteWithoutRecovery=True)
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════
#  Object Store — S3
# ══════════════════════════════════════════════════════════════════════


class AwsObjectStore:
    """Amazon S3 implementation.

    URI format: s3://bucket-name/path/to/blob
    """

    _client = None

    @property
    def client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client("s3", region_name=_resolve_aws_region())
        return self._client

    def _parse_uri(self, uri: str) -> tuple[str, str]:
        """Return (bucket_name, object_key)."""
        if not uri.startswith("s3://"):
            raise ValueError(f"AwsObjectStore requires s3:// URI, got: {uri!r}")
        path = uri[5:]
        bucket, _, key = path.partition("/")
        if not bucket or not key:
            raise ValueError(f"Invalid s3:// URI: {uri!r}")
        return bucket, key

    def read_text(self, uri: str) -> str:
        bucket, key = self._parse_uri(uri)
        response = self.client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read().decode("utf-8")

    def read_bytes(self, uri: str) -> bytes:
        bucket, key = self._parse_uri(uri)
        response = self.client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()

    def write_text(self, uri: str, data: str, content_type: str = "text/plain") -> str:
        bucket, key = self._parse_uri(uri)
        self.client.put_object(Bucket=bucket, Key=key, Body=data.encode("utf-8"), ContentType=content_type)
        return uri

    def write_bytes(self, uri: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        bucket, key = self._parse_uri(uri)
        self.client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
        return uri

    def exists(self, uri: str) -> bool:
        bucket, key = self._parse_uri(uri)
        try:
            self.client.head_object(Bucket=bucket, Key=key)
            return True
        except self.client.exceptions.ClientError:
            return False

    def list(self, prefix: str) -> list[str]:
        """List objects under a prefix. Format: s3://bucket/prefix"""
        bucket, key_prefix = self._parse_uri(prefix)
        response = self.client.list_objects_v2(Bucket=bucket, Prefix=key_prefix)
        if "Contents" not in response:
            return []
        return [f"s3://{bucket}/{obj['Key']}" for obj in response["Contents"]]


# ══════════════════════════════════════════════════════════════════════
#  Document Store — DynamoDB
# ══════════════════════════════════════════════════════════════════════


class AwsDocumentStore:
    """DynamoDB implementation (collection/document model).

    Table name = collection name, document_id as primary key 'id'.
    """

    _client = None
    _table_cache: dict[str, object] = {}

    @property
    def client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client("dynamodb", region_name=_resolve_aws_region())
        return self._client

    def _get_table(self, table_name: str):
        if table_name not in self._table_cache:
            import boto3
            dynamodb = boto3.resource("dynamodb", region_name=_resolve_aws_region())
            self._table_cache[table_name] = dynamodb.Table(table_name)
        return self._table_cache[table_name]

    def get(self, collection: str, document_id: str) -> dict | None:
        table = self._get_table(collection)
        response = table.get_item(Key={"id": document_id})
        item = response.get("Item")
        if item is None:
            return None
        return {k: _dynamodb_deserialize(v) for k, v in item.items()}

    def set(self, collection: str, document_id: str, data: dict) -> None:
        table = self._get_table(collection)
        item = {"id": document_id, **{k: _dynamodb_serialize(v) for k, v in data.items()}}
        table.put_item(Item=item)

    def update(self, collection: str, document_id: str, fields: dict) -> None:
        table = self._get_table(collection)
        update_expr = "SET " + ", ".join(f"#{k} = :{k}" for k in fields)
        expr_attr_names = {f"#{k}": k for k in fields}
        expr_attr_values = {f":{k}": _dynamodb_serialize(v) for k, v in fields.items()}
        table.update_item(
            Key={"id": document_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_values,
        )

    def delete(self, collection: str, document_id: str) -> None:
        table = self._get_table(collection)
        table.delete_item(Key={"id": document_id})


# ══════════════════════════════════════════════════════════════════════
#  Compute Discovery — EC2
# ══════════════════════════════════════════════════════════════════════


class AwsComputeDiscovery:
    """Resolve EC2 instance IP via EC2 API."""

    _client = None

    @property
    def client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client("ec2", region_name=_resolve_aws_region())
        return self._client

    def resolve_instance_ip(
        self,
        instance_name: str,
        zone: str,
        *,
        project_id: str | None = None,
        prefer_internal: bool = True,
    ) -> str:
        filters = [{"Name": "tag:Name", "Values": [instance_name]}]
        response = self.client.describe_instances(Filters=filters)

        for reservation in response.get("Reservations", []):
            for instance in reservation.get("Instances", []):
                if instance["State"]["Name"] != "running":
                    continue
                if prefer_internal:
                    return instance.get("PrivateIpAddress", "")
                return instance.get("PublicIpAddress", "")

        raise RuntimeError(f"No running EC2 instance found with Name={instance_name}")


# ══════════════════════════════════════════════════════════════════════
#  Deployment Context — ECS / EC2 / Lambda
# ══════════════════════════════════════════════════════════════════════


class AwsDeploymentContext:
    """AWS deployment context."""

    @property
    def project_id(self) -> str:
        return os.environ.get("AWS_ACCOUNT_ID", "")

    @property
    def region(self) -> str | None:
        return _resolve_aws_region()

    def fetch_id_token(self, audience: str) -> str:
        raise NotImplementedError(
            "AWS DeploymentContext.fetch_id_token is not implemented. "
            "Use a service-specific mechanism (e.g., Cognito, STS, or IAM roles)."
        )


# ══════════════════════════════════════════════════════════════════════
#  Internal helpers
# ══════════════════════════════════════════════════════════════════════


def _resolve_aws_region() -> str:
    """Resolve AWS region from env vars or boto3 session, default us-east-1."""
    env_region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
    if env_region:
        return env_region
    try:
        import boto3
        region = boto3.Session().region_name
        if region:
            return region
    except Exception:
        pass
    return "us-east-1"


def _dynamodb_serialize(value):
    """Convert Python values to DynamoDB-compatible format."""
    if isinstance(value, (str, bool, int, float, type(None))):
        return value
    if isinstance(value, (list, tuple)):
        return list(value)
    if isinstance(value, dict):
        return {k: _dynamodb_serialize(v) for k, v in value.items()}
    return str(value)


def _dynamodb_deserialize(value):
    """DynamoDB values are returned as-is by boto3 resource API."""
    return value
