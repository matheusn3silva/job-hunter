"""Executa todos os scrapers e junta o resultado."""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable

from jobhunter.config.settings import SourceConfig
from jobhunter.models import Job, SearchCriteria
from jobhunter.scrapers.base import BaseScraper, ScraperError
from jobhunter.scrapers.factory import ScraperFactory

log = logging.getLogger(__name__)


class ScraperRunner:
    """Roda cada fonte ativa, isolando falhas e removendo duplicatas.

    Se uma fonte falhar, o erro é registrado em ``errors`` e as outras
    continuam. A mesma vaga vinda de fontes diferentes aparece uma vez só.

    Args:
        sources: fontes ativas.
        scraper_factory: função ``SourceConfig -> BaseScraper`` (injetável em testes).
    """

    def __init__(
        self,
        sources: Iterable[SourceConfig],
        scraper_factory: Callable[[SourceConfig], BaseScraper] = ScraperFactory.create,
    ):
        self._sources = list(sources)
        self._factory = scraper_factory
        self.errors: list[str] = []

    def run(self, criteria: SearchCriteria) -> list[Job]:
        self.errors = []
        jobs: dict[str, Job] = {}
        for source in self._sources:
            try:
                found = self._factory(source).fetch(criteria)
            except ScraperError as exc:
                log.warning("%s", exc)
                self.errors.append(str(exc))
                continue
            log.info("%s: %d vagas", source.name, len(found))
            for job in found:
                jobs.setdefault(job.uid, job)
        return list(jobs.values())