"""Aplica vários filtros em sequência."""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Iterable

from jobhunter.filters.base import BaseFilter
from jobhunter.filters.rules import (
    ExcludedKeywordFilter,
    KeywordFilter,
    LocationFilter,
    SalaryFilter,
    SeniorityFilter,
)
from jobhunter.models import Job, SearchCriteria

log = logging.getLogger(__name__)

DEFAULT_FILTERS: tuple[type[BaseFilter], ...] = (
    KeywordFilter,
    ExcludedKeywordFilter,
    SeniorityFilter,
    LocationFilter,
    SalaryFilter,
)


class FilterChain:
    """Passa cada vaga por todos os filtros; só ficam as aprovadas em todos.

    A vaga é descartada no primeiro filtro que a reprovar. ``rejected``
    conta quantas vagas cada filtro descartou na última execução, o que
    ajuda a calibrar os critérios (ex.: "o filtro de salário cortou 40").

    Args:
        filters: filtros a aplicar, na ordem.
    """

    def __init__(self, filters: Iterable[BaseFilter]):
        self.filters = list(filters)
        self.rejected: Counter[str] = Counter()

    @classmethod
    def from_criteria(cls, criteria: SearchCriteria) -> FilterChain:
        """Monta a cadeia padrão com todos os filtros do projeto."""
        return cls(f(criteria) for f in DEFAULT_FILTERS)

    def apply(self, jobs: Iterable[Job]) -> list[Job]:
        """Retorna só as vagas aprovadas, mantendo a ordem original."""
        self.rejected = Counter()
        approved = []
        for job in jobs:
            failed = next((f for f in self.filters if not f.accepts(job)), None)
            if failed is None:
                approved.append(job)
            else:
                self.rejected[failed.name] += 1
        log.info("Filtros: %d aprovadas, descartes %s", len(approved), dict(self.rejected))
        return approved
