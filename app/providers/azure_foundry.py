from __future__ import annotations

import asyncio

import httpx

from app.core.config import Settings
from app.providers.base import CompletionResult, ProviderStatus


class AzureFoundryProvider:
    name = "azure_foundry"

    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(
            self.settings.azure_ai_foundry_endpoint
            and self.settings.azure_ai_foundry_api_key
            and self.settings.azure_ai_foundry_deployment
        )

    async def health(self) -> ProviderStatus:
        await asyncio.sleep(0)
        if not self.configured:
            return ProviderStatus(self.name, configured=False, available=False, detail="missing endpoint/api key/deployment")
        return ProviderStatus(self.name, configured=True, available=True, detail="configured")

    async def complete(self, prompt: str) -> CompletionResult:
        if not self.configured:
            raise RuntimeError("Azure AI Foundry fallback is not configured")
        endpoint = self.settings.azure_ai_foundry_endpoint.rstrip("/")
        deployment = self.settings.azure_ai_foundry_deployment
        url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version=2025-01-01-preview"
        payload = {"messages": [{"role": "user", "content": prompt}], "temperature": 0.2}
        headers = {"api-key": self.settings.azure_ai_foundry_api_key}
        async with httpx.AsyncClient(timeout=self.settings.azure_ai_foundry_timeout_seconds) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        text = data["choices"][0]["message"].get("content", "")
        return CompletionResult(provider=self.name, model=deployment, text=text)
