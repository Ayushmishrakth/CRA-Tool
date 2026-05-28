from __future__ import annotations

from typing import Any

import httpx


class GraphClient:
    def __init__(self, *, access_token: str) -> None:
        self.access_token = access_token

    async def get(self, path: str, *, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = path if path.startswith("https://") else f"https://graph.microsoft.com/v1.0/{path.lstrip('/')}"
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {self.access_token}"},
            )
            response.raise_for_status()
            return response.json()
