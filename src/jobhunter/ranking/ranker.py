"""Ordena as vagas da mais para a menos aderente ao perfil."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from jobhunter.models import Job, SearchCriteria
from jobhunter.ranking.rules import (
    BaseScoreRule,
    KeywordScore,
    LocationScore,
    RecencyScore,
    SalaryScore,
    SeniorityScore,
)

MAX_SCORE = 10.0
_OLDEST = datetime.min.replace(tzinfo=timezone.utc)


class JobRanker:
    """Dá uma nota de 0 a 10 a cada vaga e ordena da maior para a menor.

    A nota é a média ponderada das regras (``BaseScoreRule``) escalada
    para 0–10. Em caso de empate, a vaga mais recente vem primeiro.

    Args:
        rules: regras de pontuação a combinar.
        top_n: quantas vagas ``top`` devolve.
    """

    def __init__(self, rules: Iterable[BaseScoreRule], top_n: int = 10):
        self.rules = list(rules)
        if not self.rules:
            raise ValueError("O ranking precisa de pelo menos uma regra")
        self.top_n = top_n

    @classmethod
    def from_criteria(cls, criteria: SearchCriteria, now: datetime | None = None) -> JobRanker:
        """Monta o ranking padrão com todas as regras do projeto."""
        rules = [
            KeywordScore(criteria),
            SeniorityScore(criteria),
            LocationScore(criteria),
            SalaryScore(criteria),
            RecencyScore(criteria, now),
        ]
        return cls(rules, top_n=criteria.top_n)

    def score(self, job: Job) -> float:
        """Nota final da vaga, de 0 a 10, com 2 casas decimais."""
        total_weight = sum(rule.weight for rule in self.rules)
        weighted = sum(rule.weight * rule.score(job) for rule in self.rules)
        return round(MAX_SCORE * weighted / total_weight, 2)

    def rank(self, jobs: Iterable[Job]) -> list[Job]:
        """Devolve cópias das vagas com ``score`` preenchido, da melhor à pior."""
        scored = [job.with_score(self.score(job)) for job in jobs]
        return sorted(scored, key=lambda j: (j.score, j.posted_at or _OLDEST), reverse=True)

    def top(self, jobs: Iterable[Job]) -> list[Job]:
        """As ``top_n`` melhores vagas, já pontuadas."""
        return self.rank(jobs)[: self.top_n]
