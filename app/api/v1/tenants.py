"""
Tenant API routes.
"""

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_active_user
from app.core.pagination import PaginationParams, get_pagination_params
from app.core.responses import SuccessResponse, success_response
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.tenant import (
    TenantConnectRequest,
    TenantPermissionsResponse,
    TenantResponse,
)
from app.services import tenant_service

router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.post(
    "/connect",
    response_model=SuccessResponse[TenantResponse],
    status_code=status.HTTP_201_CREATED,
)
async def connect_tenant(
    payload: TenantConnectRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[TenantResponse]:
    tenant = await tenant_service.connect_tenant(
        db, current_user=current_user, payload=payload
    )
    return success_response(
        message="Tenant connected",
        data=TenantResponse.model_validate(tenant),
        request_id=request.state.request_id,
    )


@router.get("", response_model=SuccessResponse[list[TenantResponse]])
async def list_tenants(
    request: Request,
    pagination: PaginationParams = Depends(get_pagination_params),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[list[TenantResponse]]:
    tenants = await tenant_service.list_tenants(
        db, current_user=current_user, pagination=pagination
    )
    return success_response(
        message="Tenants retrieved",
        data=[TenantResponse.model_validate(tenant) for tenant in tenants],
        request_id=request.state.request_id,
    )


@router.get("/{tenant_id}", response_model=SuccessResponse[TenantResponse])
async def get_tenant(
    tenant_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[TenantResponse]:
    tenant = await tenant_service.get_tenant(
        db, current_user=current_user, tenant_id=tenant_id
    )
    return success_response(
        message="Tenant retrieved",
        data=TenantResponse.model_validate(tenant),
        request_id=request.state.request_id,
    )


@router.delete("/{tenant_id}", response_model=SuccessResponse[TenantResponse])
async def disconnect_tenant(
    tenant_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[TenantResponse]:
    tenant = await tenant_service.disconnect_tenant(
        db, current_user=current_user, tenant_id=tenant_id
    )
    return success_response(
        message="Tenant disconnected",
        data=TenantResponse.model_validate(tenant),
        request_id=request.state.request_id,
    )


@router.get(
    "/{tenant_id}/permissions",
    response_model=SuccessResponse[TenantPermissionsResponse],
)
async def get_tenant_permissions(
    tenant_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> SuccessResponse[TenantPermissionsResponse]:
    tenant = await tenant_service.get_permissions(
        db, current_user=current_user, tenant_id=tenant_id
    )
    return success_response(
        message="Tenant permissions retrieved",
        data=TenantPermissionsResponse(
            tenant_id=tenant.tenant_id,
            permissions=tenant.granted_permissions or [],
            consent_status=tenant.consent_status,
            status=tenant.status,
        ),
        request_id=request.state.request_id,
    )
