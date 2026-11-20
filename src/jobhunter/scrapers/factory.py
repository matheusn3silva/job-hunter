"""Criação de scrapers a partir da configuração."""

from __future__ import annotations

import httpx

from jobhunter.config.settings import SourceConfig
from jobhunter.scrapers.base import BaseScraper, ScraperError
from jobhunter.scrapers.gupy import GupyScraper
from jobhunter.scrapers.remotive import RemotiveScraper


class ScraperFactory:
    """Escolhe a classe de scraper pelo ``name`` da fonte no sources.yaml.

    Para adicionar um site novo: crie a classe e registre-a em ``REGISTRY``.
    """

    REGISTRY: dict[str, type[BaseScraper]] = {
        "gupy": GupyScraper,
        "remotive": RemotiveScraper,
    }

    @classmethod
    def create(cls, source: SourceConfig, client: httpx.Client | None = None) -> BaseScraper:
        try:
            scraper_cls = cls.REGISTRY[source.name]
        except KeyError:
            raise ScraperError(
                f"Sem scraper para a fonte '{source.name}'. "
                f"Disponíveis: {sorted(cls.REGISTRY)}"
            ) from None
        return scraper_cls(source, client)