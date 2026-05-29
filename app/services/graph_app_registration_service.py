from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.services.graph.graph_client import GraphClient


async def create_application(
    client: GraphClient,
    *,
    display_name: str,
    required_resource_access: list[dict[str, Any]],
) -> dict[str, Any]:
    return await client.post(
        "/applications",
        json={
            "displayName": display_name,
            "signInAudience": "AzureADMyOrg",
            "requiredResourceAccess": required_resource_access,
        },
    )


async def create_service_principal(client: GraphClient, *, app_id: str) -> dict[str, Any]:
    return await client.post("/servicePrincipals", json={"appId": app_id})


async def create_client_secret(
    client: GraphClient,
    *,
    application_object_id: str,
    display_name: str = "CRA runtime collector secret",
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    return await client.post(
        f"/applications/{application_object_id}/addPassword",
        json={
            "passwordCredential": {
                "displayName": display_name,
                "startDateTime": now.isoformat(),
            }
        },
    )
