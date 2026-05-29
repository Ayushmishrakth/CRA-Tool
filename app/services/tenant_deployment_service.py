from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AuthException, BusinessLogicException, TenantAccessException
from app.db.models.tenant import ConnectedTenant
from app.db.models.user import User
from app.services.audit_service import AuditEvent, audit_service
from app.services.graph.graph_client import GraphClient
from app.services.graph_app_registration_service import (
    create_application,
    create_client_secret,
    create_service_principal,
)
from app.services.graph_consent_service import build_admin_consent_url
from app.services.graph_permission_service import (
    REQUIRED_APPLICATION_PERMISSIONS,
    REQUIRED_DELEGATED_PERMISSIONS,
    build_required_resource_access,
)
from app.services.tenant_secret_service import store_client_secret


def _decode_unverified_token(access_token: str) -> dict[str, Any]:
    try:
        return jwt.decode(access_token, options={"verify_signature": False, "verify_aud": False})
    except jwt.PyJWTError as exc:
        raise AuthException("Graph access token is not a valid JWT") from exc


async def _assert_graph_token(
    client: GraphClient,
    *,
    access_token: str,
    tenant_id: str,
) -> dict[str, Any]:
    claims = _decode_unverified_token(access_token)
    token_tid = claims.get("tid")
    if token_tid != tenant_id:
        raise TenantAccessException("Graph access token tenant does not match the requested tenant")
    scopes = set(str(claims.get("scp") or "").split())
    missing = [scope for scope in REQUIRED_DELEGATED_PERMISSIONS if scope not in scopes]
    if missing:
        raise AuthException(
            "Graph access token is missing required delegated scopes",
            details={"missing_scopes": missing},
        )
    me = await client.get("/me", params={"$select": "id,userPrincipalName,displayName"})
    org = await client.get("/organization", params={"$select": "id,displayName,verifiedDomains"})
    values = org.get("value") or []
    if not values or values[0].get("id") != tenant_id:
        raise TenantAccessException("Graph organization validation failed for requested tenant")
    return {"claims": claims, "me": me, "organization": values[0], "scopes": sorted(scopes)}


async def _get_or_create_tenant(
    db: AsyncSession,
    *,
    tenant_id: str,
    tenant_name: str | None,
) -> ConnectedTenant:
    result = await db.execute(select(ConnectedTenant).where(ConnectedTenant.tenant_id == tenant_id))
    tenant = result.scalars().first()
    if tenant is None:
        tenant = ConnectedTenant(
            tenant_id=tenant_id,
            tenant_name=tenant_name or tenant_id,
            consent_status="pending",
            deployment_status="pending",
            status="pending",
        )
        db.add(tenant)
        await db.flush()
    return tenant


async def deploy_tenant_access(
    db: AsyncSession,
    *,
    current_user: User,
    tenant_id: str,
    graph_access_token: str,
) -> dict[str, Any]:
    if tenant_id != current_user.microsoft_tid:
        raise TenantAccessException("Tenant is not available to the current user")

    client = GraphClient(access_token=graph_access_token)
    tenant = await _get_or_create_tenant(db, tenant_id=tenant_id, tenant_name=tenant_id)
    tenant.deployment_status = "validating_graph_token"
    tenant.deployment_error = None
    await db.commit()

    try:
        validation = await _assert_graph_token(client, access_token=graph_access_token, tenant_id=tenant_id)
        organization = validation["organization"]
        tenant.tenant_name = organization.get("displayName") or tenant.tenant_name
        tenant.deployment_status = "creating_app_registration"
        await db.commit()

        required_access = await build_required_resource_access(client)
        app = await create_application(
            client,
            display_name=f"CRA Runtime Collectors - {tenant.tenant_name or tenant_id}",
            required_resource_access=required_access,
        )
        tenant.app_registration_id = app["id"]
        tenant.app_client_id = app["appId"]
        tenant.deployment_status = "creating_service_principal"
        await db.commit()

        service_principal = await create_service_principal(client, app_id=app["appId"])
        tenant.service_principal_id = service_principal["id"]
        tenant.deployment_status = "creating_client_secret"
        await db.commit()

        secret = await create_client_secret(client, application_object_id=app["id"])
        expires_at = None
        if secret.get("endDateTime"):
            expires_at = datetime.fromisoformat(secret["endDateTime"].replace("Z", "+00:00"))
        store_client_secret(tenant, secret_text=secret["secretText"], expires_at=expires_at)

        tenant.granted_permissions = {
            "required_application_permissions": REQUIRED_APPLICATION_PERMISSIONS,
            "delegated_scopes_validated": validation["scopes"],
            "graph_service_principal_permissions_discovered": True,
        }
        tenant.admin_consent_url = build_admin_consent_url(
            tenant_id=tenant_id,
            client_id=tenant.app_client_id,
            redirect_uri=settings.azure_redirect_uri,
        )
        tenant.consent_status = "pending_admin_consent"
        tenant.deployment_status = "waiting_for_admin_consent"
        tenant.status = "pending"
        await audit_service.log_event(
            db,
            tenant_id=tenant_id,
            event=AuditEvent.TENANT_CONNECTED,
            action="tenant.deploy_access",
            user_id=current_user.id,
            resource="connected_tenants",
            metadata={
                "tenant_id": tenant_id,
                "app_registration_id": tenant.app_registration_id,
                "app_client_id": tenant.app_client_id,
                "service_principal_id": tenant.service_principal_id,
                "secret_version": tenant.secret_version,
            },
        )
        await db.commit()
        await db.refresh(tenant)
        return deployment_payload(tenant)
    except Exception as exc:
        tenant.deployment_status = "failed"
        tenant.deployment_error = str(exc)
        tenant.status = "pending"
        await audit_service.log_event(
            db,
            tenant_id=tenant_id,
            event=AuditEvent.TENANT_DISCONNECTED,
            action="tenant.deploy_access_failed",
            user_id=current_user.id,
            resource="connected_tenants",
            metadata={"error": str(exc), "failure_id": str(uuid.uuid4())},
        )
        await db.commit()
        if isinstance(exc, (AuthException, TenantAccessException, BusinessLogicException)):
            raise
        raise BusinessLogicException("Tenant deployment failed", details={"error": str(exc)}) from exc


async def validate_admin_consent(
    db: AsyncSession,
    *,
    current_user: User,
    tenant_id: str,
    graph_access_token: str,
) -> dict[str, Any]:
    if tenant_id != current_user.microsoft_tid:
        raise TenantAccessException("Tenant is not available to the current user")
    result = await db.execute(select(ConnectedTenant).where(ConnectedTenant.tenant_id == tenant_id))
    tenant = result.scalars().first()
    if tenant is None or not tenant.service_principal_id:
        raise BusinessLogicException("Tenant deployment has not created a service principal")
    client = GraphClient(access_token=graph_access_token)
    await _assert_graph_token(client, access_token=graph_access_token, tenant_id=tenant_id)
    assignments = await client.get(
        f"/servicePrincipals/{tenant.service_principal_id}/appRoleAssignments",
        params={"$select": "id,appRoleId,resourceDisplayName"},
    )
    granted = assignments.get("value") or []
    if not granted:
        tenant.consent_status = "pending_admin_consent"
        tenant.deployment_status = "waiting_for_admin_consent"
        await db.commit()
        raise BusinessLogicException("Admin consent has not been granted yet")
    tenant.consent_status = "connected"
    tenant.deployment_status = "active"
    tenant.status = "active"
    tenant.consent_granted_by = current_user.email
    tenant.consent_granted_at = datetime.utcnow()
    await audit_service.log_event(
        db,
        tenant_id=tenant_id,
        event=AuditEvent.TENANT_CONNECTED,
        action="tenant.admin_consent_validated",
        user_id=current_user.id,
        resource="connected_tenants",
        metadata={"app_role_assignment_count": len(granted)},
    )
    await db.commit()
    await db.refresh(tenant)
    return deployment_payload(tenant)


def deployment_payload(tenant: ConnectedTenant) -> dict[str, Any]:
    return {
        "tenant_id": tenant.tenant_id,
        "tenant_name": tenant.tenant_name,
        "status": tenant.status,
        "deployment_status": tenant.deployment_status,
        "consent_status": tenant.consent_status,
        "app_registration_id": tenant.app_registration_id,
        "app_client_id": tenant.app_client_id,
        "service_principal_id": tenant.service_principal_id,
        "admin_consent_url": tenant.admin_consent_url,
        "granted_permissions": tenant.granted_permissions,
        "secret_expires_at": tenant.secret_expires_at,
        "deployment_error": tenant.deployment_error,
    }
