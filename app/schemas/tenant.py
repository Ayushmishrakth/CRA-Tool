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


class TenantDeploymentRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=64)
    graph_access_token: str = Field(..., min_length=20)


class TenantDeploymentResponse(BaseModel):
    tenant_id: str
    tenant_name: str | None
    status: str
    deployment_status: str
    consent_status: str
    app_registration_id: str | None
    app_client_id: str | None
    service_principal_id: str | None
    admin_consent_url: str | None
    granted_permissions: dict[str, Any] | list[Any] | None
    secret_expires_at: datetime | None
    deployment_error: str | None


class TenantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: str
    tenant_name: str | None
    consent_status: str
    deployment_status: str
    granted_permissions: dict[str, Any] | list[Any] | None
    status: str
    app_client_id: str | None = None
    service_principal_id: str | None = None
    admin_consent_url: str | None = None
    secret_expires_at: datetime | None = None
    deployment_error: str | None = None
    last_assessment_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TenantPermissionsResponse(BaseModel):
    tenant_id: str
    permissions: dict[str, Any] | list[Any]
    consent_status: str
    status: str
