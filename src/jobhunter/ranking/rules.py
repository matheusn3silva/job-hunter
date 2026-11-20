"""Regras de pontuação: cada uma avalia um aspecto da vaga de 0 a 1."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone

from jobhunter.filters.rules import has_accepted_level
from jobhunter.models import Job, SearchCriteria
from jobhunter.utils.text import contains_term

# Quantos "acertos" de tecnologia valem nota máxima (cada palavra-chave
# citada conta 1; citada também no título conta mais 1).
KEYWORD_HITS_FOR_MAX = 4

# Vaga recente: nota máxima até FRESH_DAYS, cai até zero em STALE_DAYS.
FRESH_DAYS = 7
STALE_DAYS = 30

# Nota para informação desconhecida (sem nível, sem salário, sem data).
UNKNOWN = 0.5


class BaseScoreRule(ABC):
    """Contrato das regras de ranking.

    Cada regra devolve um valor entre 0 e 1 para UM aspecto da vaga e tem
    um ``weight`` (peso). O ranking combina as regras em média ponderada,
    então dá para ajustar a importância de cada aspecto mudando só o peso.

    Para criar uma regra: herda desta classe, define ``name`` e ``weight``,
    implementa ``score`` e adiciona em ``DEFAULT_RULES`` (ranker.py).
    """

    name: str = "base"
    weight: float = 1.0

    def __init__(self, criteria: SearchCriteria):
        self.criteria = criteria

    @abstractmethod
    def score(self, job: Job) -> float:
        """Nota de 0 a 1 para este aspecto da vaga."""


class KeywordScore(BaseScoreRule):
    """Quanto mais tecnologias desejadas a vaga cita, maior a nota.

    Tecnologia no título vale em dobro: indica o foco principal da vaga.
    """

    name = "keywords"
    weight = 4.0

    def score(self, job: Job) -> float:
        if not self.criteria.keywords:
            return UNKNOWN
        text = job.searchable_text
        hits = sum(contains_term(text, kw) + contains_term(job.title, kw)
                   for kw in self.criteria.keywords)
        return min(1.0, hits / KEYWORD_HITS_FOR_MAX)


class SeniorityScore(BaseScoreRule):
    """Nível desejado no título vale 1; vaga sem nível informado vale 0,5.

    Vagas de outros níveis já foram descartadas pelo filtro.
    """

    name = "seniority"
    weight = 3.0

    def score(self, job: Job) -> float:
        if not self.criteria.seniority:
            return UNKNOWN
        return 1.0 if has_accepted_level(job, self.criteria) else UNKNOWN


class LocationScore(BaseScoreRule):
    """Remota ou na cidade desejada vale 1; local desconhecido vale 0,5."""

    name = "location"
    weight = 1.0

    def score(self, job: Job) -> float:
        if job.remote:
            return 1.0
        location = job.location.lower()
        if location and any(city in location for city in self.criteria.locations):
            return 1.0
        return UNKNOWN


class SalaryScore(BaseScoreRule):
    """Salário divulgado (que já passou no filtro) vale 1; desconhecido 0,5."""

    name = "salary"
    weight = 1.0

    def score(self, job: Job) -> float:
        known = job.salary_min is not None or job.salary_max is not None
        return 1.0 if known else UNKNOWN


class RecencyScore(BaseScoreRule):
    """Vagas novas recebem menos candidatos: nota 1 até 7 dias, 0 aos 30.

    Args:
        now: "agora" usado no cálculo; injetável para testes.
    """

    name = "recency"
    weight = 1.0

    def __init__(self, criteria: SearchCriteria, now: datetime | None = None):
        super().__init__(criteria)
        self.now = now or datetime.now(timezone.utc)

    def score(self, job: Job) -> float:
        if job.posted_at is None:
            return UNKNOWN
        age_days = (self.now - job.posted_at).total_seconds() / 86400
        if age_days <= FRESH_DAYS:
            return 1.0
        if age_days >= STALE_DAYS:
            return 0.0
        return 1.0 - (age_days - FRESH_DAYS) / (STALE_DAYS - FRESH_DAYS)
