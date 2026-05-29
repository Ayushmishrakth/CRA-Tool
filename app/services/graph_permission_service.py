from __future__ import annotations

from typing import Any

from app.core.exceptions import BusinessLogicException
from app.services.graph.graph_client import GraphClient


MICROSOFT_GRAPH_APP_ID = "00000003-0000-0000-c000-000000000000"

REQUIRED_APPLICATION_PERMISSIONS = [
    "Directory.Read.All",
    "Policy.Read.All",
    "Application.Read.All",
    "RoleManagement.Read.Directory",
    "AuditLog.Read.All",
    "UserAuthenticationMethod.Read.All",
    "Reports.Read.All",
    "Group.Read.All",
    "Team.ReadBasic.All",
    "Sites.Read.All",
    "Files.Read.All",
]

REQUIRED_DELEGATED_PERMISSIONS = [
    "User.Read",
    "Application.ReadWrite.All",
    "AppRoleAssignment.ReadWrite.All",
    "Directory.Read.All",
]


async def get_graph_service_principal(client: GraphClient) -> dict[str, Any]:
    response = await client.get(
        "/servicePrincipals",
        params={"$filter": f"appId eq '{MICROSOFT_GRAPH_APP_ID}'", "$select": "id,appId,appRoles,oauth2PermissionScopes"},
    )
    values = response.get("value") or []
    if not values:
        raise BusinessLogicException("Microsoft Graph service principal was not found in tenant")
    return values[0]


async def build_required_resource_access(client: GraphClient) -> list[dict[str, Any]]:
    graph_sp = await get_graph_service_principal(client)
    app_roles = {
        role.get("value"): role
        for role in graph_sp.get("appRoles") or []
        if role.get("isEnabled") and role.get("value")
    }
    missing = [name for name in REQUIRED_APPLICATION_PERMISSIONS if name not in app_roles]
    if missing:
        raise BusinessLogicException(
            "Microsoft Graph application permissions unavailable",
            details={"missing_permissions": missing},
        )
    return [
        {
            "resourceAppId": MICROSOFT_GRAPH_APP_ID,
            "resourceAccess": [
                {"id": app_roles[name]["id"], "type": "Role"}
                for name in REQUIRED_APPLICATION_PERMISSIONS
            ],
        }
    ]
