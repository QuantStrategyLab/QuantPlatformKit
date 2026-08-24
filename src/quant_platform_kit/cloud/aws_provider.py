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

import os



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

    def create_text(self, uri: str, data: str, content_type: str = "text/plain") -> bool:
        """Create an object only if it does not already exist."""
        bucket, key = self._parse_uri(uri)
        try:
            self.client.put_object(
                Bucket=bucket,
                Key=key,
                Body=data.encode("utf-8"),
                ContentType=content_type,
                IfNoneMatch="*",
            )
            return True
        except self.client.exceptions.ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in {"PreconditionFailed", "412", "ConditionalRequestConflict"}:
                return False
            raise

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
    """AWS deployment context.

    通过 ECS metadata / EC2 IMDSv2 获取运行时身份信息。

    注意：fetch_id_token 的语义与 GCP 不完全对等 ——
    AWS 没有 GCP ID Token 的标准替代品。
    此实现返回当前 EC2/ECS 实例的身份文档，
    或 STS GetCallerIdentity 作为 fallback。
    """

    @property
    def project_id(self) -> str:
        # ECS task ARN 解析 → account_id
        task_arn = os.environ.get("ECS_CONTAINER_METADATA_URI_V4", "")
        if task_arn:
            parts = task_arn.split(":") if ":" in task_arn else []
            if len(parts) >= 5:
                return parts[4]
        return _resolve_aws_account_id()

    @property
    def region(self) -> str | None:
        return _resolve_aws_region()

    def fetch_id_token(self, audience: str) -> str:
        """获取当前 AWS 环境的身份凭证。

        在 ECS/EC2 上返回实例身份文档的 JSON string；
        本地开发环境 fallback 到 STS GetCallerIdentity。

        ``audience`` 参数在 AWS 无直接对应，此方法不会使用它。
        如果调用方依赖 audience 进行令牌验证，
        建议使用 Cognito 或自建 OIDC provider。
        """
        import json as _json
        try:
            return _fetch_ecs_identity()
        except Exception:
            pass
        try:
            return _fetch_ec2_identity()
        except Exception:
            pass
        try:
            import boto3
            sts = boto3.client("sts", region_name=_resolve_aws_region())
            identity = sts.get_caller_identity()
            return _json.dumps({
                "account": identity.get("Account", ""),
                "arn": identity.get("Arn", ""),
                "user_id": identity.get("UserId", ""),
            })
        except Exception as exc:
            raise RuntimeError(
                "AwsDeploymentContext.fetch_id_token: unable to resolve AWS identity. "
                "Ensure the process runs on EC2, ECS, or has valid AWS credentials. "
                "Note: GCP-style audience-based ID tokens are not natively supported on AWS; "
                "consider using Cognito or a custom OIDC setup for audienced tokens."
            ) from exc


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


def _resolve_aws_account_id() -> str:
    """Resolve AWS account ID from env vars, STS, or metadata."""
    env = os.environ.get("AWS_ACCOUNT_ID")
    if env:
        return env
    try:
        import boto3
        sts = boto3.client("sts", region_name=_resolve_aws_region())
        return sts.get_caller_identity().get("Account", "")
    except Exception:
        return ""


def _fetch_ecs_identity() -> str:
    """Fetch identity document from ECS container metadata endpoint (v4)."""
    import urllib.request
    metadata_uri = os.environ.get("ECS_CONTAINER_METADATA_URI_V4", "")
    if not metadata_uri:
        raise RuntimeError("Not running on ECS (ECS_CONTAINER_METADATA_URI_V4 not set)")
    req = urllib.request.Request(metadata_uri)
    with urllib.request.urlopen(req, timeout=3) as resp:
        return resp.read().decode("utf-8")


def _fetch_ec2_identity() -> str:
    """Fetch identity document from EC2 IMDSv2."""
    import urllib.request
    # Step 1: get IMDSv2 token
    token_req = urllib.request.Request(
        "http://169.254.169.254/latest/api/token",
        headers={"X-aws-ec2-metadata-token-ttl-seconds": "60"},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(token_req, timeout=2) as resp:
            token = resp.read().decode("utf-8")
    except Exception:
        raise RuntimeError("Not running on EC2 (IMDSv2 unreachable)")

    # Step 2: fetch identity document
    id_req = urllib.request.Request(
        "http://169.254.169.254/latest/dynamic/instance-identity/document",
        headers={"X-aws-ec2-metadata-token": token},
    )
    with urllib.request.urlopen(id_req, timeout=3) as resp:
        return resp.read().decode("utf-8")


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
