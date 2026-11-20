"""Modelo de dados de uma vaga."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, replace
from datetime import datetime

from jobhunter.utils.text import contains_term

INTERNSHIP_MARKERS = (
    "estágio", "estagio", "estagiário", "estagiario", "intern", "internship",
)


@dataclass(frozen=True)
class Job:
    """Uma vaga coletada de qualquer fonte.

    Imutável (frozen): para alterar, use ``with_score`` ou ``dataclasses.replace``.
    Isso evita que um filtro mude a vaga sem querer.

    Attributes:
        title, company, url, description, source: dados básicos da vaga.
        location: cidade/estado, se informado.
        remote: True se for remota.
        salary_min / salary_max: faixa mensal em R$; None = não informado.
        posted_at: data de publicação, se disponível.
        score: pontuação do ranking (preenchida na etapa de ranking).
        tags: palavras-chave extras.
    """

    title: str
    company: str
    url: str
    description: str
    source: str
    location: str = ""
    remote: bool = False
    salary_min: float | None = None
    salary_max: float | None = None
    posted_at: datetime | None = None
    score: float = 0.0
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def uid(self) -> str:
        """ID estável (empresa + título + URL), usado para não repetir vagas."""
        raw = "|".join(p.strip().lower() for p in (self.company, self.title, self.url))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    @property
    def searchable_text(self) -> str:
        """Título + descrição + tags em minúsculas, para busca de palavras-chave."""
        return " ".join([self.title, self.description, *self.tags]).lower()

    @property
    def is_internship(self) -> bool:
        """True se o título indica estágio.

        Compara palavras inteiras: "Internal Tools" não é estágio.
        """
        return any(contains_term(self.title, marker) for marker in INTERNSHIP_MARKERS)

    def with_score(self, score: float) -> Job:
        """Retorna uma cópia da vaga com a pontuação definida."""
        return replace(self, score=score)