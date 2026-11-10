"""Nirbhar AI SDK for autonomous agent integration."""
from typing import Dict, Any, Optional
import httpx

class Nirbhar AIClient:
    def __init__(self, base_url: str = "http://localhost:8000", api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    async def get_health(self) -> Dict[str, Any]:
        """Fetch live system health for all connected providers."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            resp = await client.get(f"{self.base_url}/health", headers=headers)
            resp.raise_for_status()
            return resp.json()

