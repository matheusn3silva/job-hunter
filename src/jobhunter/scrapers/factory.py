"""Criação de scrapers a partir da configuração."""

from __future__ import annotations

import httpx

from jobhunter.config.settings import SourceConfig
from jobhunter.scrapers.base import BaseScraper, ScraperError
from jobhunter.scrapers.github import GitHubVagasScraper
from jobhunter.scrapers.gupy import GupyScraper
from jobhunter.scrapers.jobicy import JobicyScraper
from jobhunter.scrapers.remotive import RemotiveScraper
from jobhunter.scrapers.weworkremotely import WeWorkRemotelyScraper


class ScraperFactory:
    """Escolhe a classe de scraper pelo ``name`` da fonte no sources.yaml.

    Para adicionar um site novo: crie a classe e registre-a em ``REGISTRY``.
    Fontes diferentes podem usar a mesma classe (ex.: repositórios do GitHub).
    """

    REGISTRY: dict[str, type[BaseScraper]] = {
        "gupy": GupyScraper,
        "remotive": RemotiveScraper,
        "jobicy": JobicyScraper,
        "weworkremotely": WeWorkRemotelyScraper,
        # Vários repositórios do GitHub usam o mesmo scraper.
        "github-frontendbr": GitHubVagasScraper,
        "github-backendbr": GitHubVagasScraper,
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