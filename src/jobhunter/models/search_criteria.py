"""Critérios de busca definidos pelo usuário."""

from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_REMOTE_REGIONS = (
    "worldwide", "anywhere", "global", "latam", "latin america",
    "south america", "americas", "brazil", "brasil",
)


@dataclass
class SearchCriteria:
    """Seus filtros e critérios de busca.

    Attributes:
        keywords: tecnologias desejadas; a vaga precisa citar ao menos uma.
        excluded_keywords: se a vaga citar qualquer uma, é descartada.
        seniority: níveis aceitos (ex.: estágio, júnior, pleno).
        locations: cidades/estados aceitos (vagas remotas sempre passam).
        remote_only: se True, só aceita vagas remotas.
        remote_regions: regiões aceitas em vagas remotas com restrição de
            local (ex.: "Worldwide", "LATAM", "Brazil"); vagas remotas
            restritas a outros lugares (ex.: "USA Only") são descartadas.
        min_salary: salário mínimo mensal (R$) para vagas CLT/PJ.
        min_salary_internship: salário mínimo mensal (R$) para estágios.
        accept_unknown_salary: aceita vagas sem salário informado (a maioria
            não divulga; descartá-las removeria quase tudo).
        top_n: quantas vagas seguem para a adaptação de currículo.
    """

    keywords: list[str] = field(default_factory=list)
    excluded_keywords: list[str] = field(default_factory=list)
    seniority: list[str] = field(default_factory=list)
    locations: list[str] = field(default_factory=list)
    remote_only: bool = False
    remote_regions: list[str] = field(default_factory=lambda: list(DEFAULT_REMOTE_REGIONS))
    min_salary: float | None = None
    min_salary_internship: float | None = None
    accept_unknown_salary: bool = True
    top_n: int = 10

    def __post_init__(self) -> None:
        if self.top_n < 1:
            raise ValueError("top_n deve ser pelo menos 1")
        for name in ("min_salary", "min_salary_internship"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise ValueError(f"{name} não pode ser negativo")
        # Normaliza para minúsculas: comparar texto fica simples.
        self.keywords = [k.strip().lower() for k in self.keywords]
        self.excluded_keywords = [k.strip().lower() for k in self.excluded_keywords]
        self.seniority = [s.strip().lower() for s in self.seniority]
        self.locations = [x.strip().lower() for x in self.locations]
        self.remote_regions = [r.strip().lower() for r in self.remote_regions]

    def min_salary_for(self, is_internship: bool) -> float | None:
        """Salário mínimo aplicável: o de estágio ou o geral."""
        return self.min_salary_internship if is_internship else self.min_salary