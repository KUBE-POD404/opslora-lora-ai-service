from __future__ import annotations

import httpx

from app.core.config import Settings
from app.providers.base import CompletionResult, ProviderStatus


class OllamaProvider:
    name = "ollama"

    def __init__(self, settings: Settings):
        self.settings = settings

    async def health(self) -> ProviderStatus:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                response = await client.get(f"{self.settings.hermes_base_url.rstrip('/')}/api/tags")
                response.raise_for_status()
            return ProviderStatus(self.name, configured=True, available=True, detail="reachable")
        except Exception as exc:  # pragma: no cover - detail depends on environment
            return ProviderStatus(self.name, configured=True, available=False, detail=str(exc))

    async def complete(self, prompt: str) -> CompletionResult:
        payload = {"model": self.settings.hermes_model, "prompt": prompt, "stream": False}
        headers = {}
        if self.settings.hermes_api_key:
            headers["Authorization"] = f"Bearer {self.settings.hermes_api_key}"
        async with httpx.AsyncClient(timeout=self.settings.hermes_timeout_seconds) as client:
            response = await client.post(
                f"{self.settings.hermes_base_url.rstrip('/')}/api/generate",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
        return CompletionResult(provider=self.name, model=self.settings.hermes_model, text=data.get("response", ""))
