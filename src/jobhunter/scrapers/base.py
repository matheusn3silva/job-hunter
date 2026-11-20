"""Classe base de todos os scrapers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import httpx

from jobhunter.config.settings import SourceConfig
from jobhunter.models import Job, SearchCriteria

USER_AGENT = "jobhunter/0.1 (uso pessoal)"


class ScraperError(RuntimeError):
    """Falha ao coletar uma fonte (rede, status HTTP ou resposta inválida)."""


class BaseScraper(ABC):
    """Contrato dos scrapers: receba uma fonte e devolva uma lista de ``Job``.

    Para criar um scraper novo, herde desta classe e implemente ``_fetch``.
    Quem usa o scraper chama apenas ``fetch``, que converte qualquer erro
    de rede/JSON em ``ScraperError``; assim uma fonte quebrada não derruba
    as demais.

    Args:
        source: configuração da fonte (nome, tipo, url).
        client: cliente HTTP. Injetável para facilitar testes sem internet.
    """

    def __init__(self, source: SourceConfig, client: httpx.Client | None = None):
        self.source = source
        self._client = client or httpx.Client(
            timeout=15, follow_redirects=True, headers={"User-Agent": USER_AGENT}
        )

    def fetch(self, criteria: SearchCriteria) -> list[Job]:
        """Coleta as vagas da fonte. Levanta ``ScraperError`` se falhar."""
        try:
            return self._fetch(criteria)
        except httpx.HTTPError as exc:
            raise ScraperError(f"[{self.source.name}] falha HTTP: {exc}") from exc
        except (ValueError, TypeError, AttributeError) as exc:
            raise ScraperError(f"[{self.source.name}] resposta inválida: {exc}") from exc

    @abstractmethod
    def _fetch(self, criteria: SearchCriteria) -> list[Job]:
        """Implementação específica de cada fonte."""

    def _get_json(self, url: str, params: dict[str, Any] | None = None) -> Any:
        """GET que devolve o JSON; levanta erro para status 4xx/5xx."""
        response = self._client.get(url, params=params)
        response.raise_for_status()
        return response.json()