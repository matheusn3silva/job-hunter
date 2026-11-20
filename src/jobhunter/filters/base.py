"""Classe base de todos os filtros."""

from __future__ import annotations

from abc import ABC, abstractmethod

from jobhunter.models import Job, SearchCriteria


class BaseFilter(ABC):
    """Contrato dos filtros: decide se uma vaga segue ou é descartada.

    Cada filtro cuida de UM critério (palavra-chave, senioridade, local,
    salário). Assim cada regra é pequena, testável isoladamente e pode ser
    ligada/desligada sem mexer nas outras.

    Para criar um filtro novo, herde desta classe, defina ``name`` e
    implemente ``accepts``.

    Args:
        criteria: critérios do usuário (já normalizados em minúsculas).
    """

    name: str = "base"

    def __init__(self, criteria: SearchCriteria):
        self.criteria = criteria

    @abstractmethod
    def accepts(self, job: Job) -> bool:
        """True se a vaga atende ao critério deste filtro."""
