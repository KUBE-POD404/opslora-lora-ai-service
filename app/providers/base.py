from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class CompletionResult:
    provider: str
    model: str | None
    text: str


@dataclass(slots=True)
class ProviderStatus:
    name: str
    configured: bool
    available: bool
    detail: str | None = None


class AIProvider(Protocol):
    name: str

    async def health(self) -> ProviderStatus: ...

    async def complete(self, prompt: str) -> CompletionResult: ...
