"""
Tenant API schemas.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TenantConnectRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=64)
    tenant_name: str | None = Field(default=None, max_length=255)
    granted_permissions: list[str] | None = None


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: str
    tenant_name: str | None
    consent_status: str
    granted_permissions: dict[str, Any] | list[Any] | None
    status: str
    last_assessment_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TenantPermissionsResponse(BaseModel):
    tenant_id: str
    permissions: dict[str, Any] | list[Any]
    consent_status: str
    status: str
