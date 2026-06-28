"""Common Flask app utilities for platform Runner services."""

from __future__ import annotations

import os


def resolve_project_id() -> str:
    """从部署环境解析 GCP project ID。"""
    try:
        from quant_platform_kit.cloud import get_deployment_context
        return get_deployment_context().project_id
    except Exception:
        return os.getenv("GOOGLE_CLOUD_PROJECT") or ""
