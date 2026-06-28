from __future__ import annotations

from app.core.config import Settings
from app.providers.azure_foundry import AzureFoundryProvider
from app.providers.base import CompletionResult, ProviderStatus
from app.providers.ollama import OllamaProvider


class ProviderRouter:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.ollama = OllamaProvider(settings)
        self.azure = AzureFoundryProvider(settings)

    async def health(self) -> list[ProviderStatus]:
        return [await self.ollama.health(), await self.azure.health()]

    async def complete(
        self,
        prompt: str,
        *,
        allow_fallback: bool = True,
        preferred_provider: str | None = None,
    ) -> tuple[CompletionResult, bool]:
        provider = (preferred_provider or self.settings.primary_ai_provider).lower()
        if provider in {"azure", "azure_foundry", "azure-ai-foundry"}:
            result = await self.azure.complete(prompt)
            return result, False
        if provider not in {"ollama", "hermes"}:
            provider = "ollama"
        try:
            result = await self.ollama.complete(prompt)
            return result, False
        except Exception:
            if not (allow_fallback and self.settings.enable_azure_foundry_fallback):
                raise
            result = await self.azure.complete(prompt)
            return result, True
