"""Filtros concretos, um por critério de busca."""

from __future__ import annotations

from jobhunter.filters.base import BaseFilter
from jobhunter.models import Job, SearchCriteria
from jobhunter.models.job import INTERNSHIP_MARKERS
from jobhunter.utils.text import contains_term

# Níveis que o filtro de senioridade reconhece no título. Se o título citar
# um destes e nenhum dos níveis aceitos, a vaga é descartada.
KNOWN_SENIORITY_LEVELS = (
    "estágio", "estagio", "estagiário", "estagiario", "intern", "internship",
    "trainee", "júnior", "junior", "jr", "pleno", "mid-level", "sênior",
    "senior", "sr", "especialista", "staff", "principal", "lead", "tech lead",
    "líder",
)


def accepted_levels(criteria: SearchCriteria) -> list[str]:
    """Níveis aceitos pelo usuário, incluindo sinônimos de estágio em inglês.

    Se algum termo de estágio for aceito (ex.: "estágio"), "intern" e
    "internship" também são. Usado pelo filtro e pelo ranking.
    """
    accepted = list(criteria.seniority)
    if any(level in INTERNSHIP_MARKERS for level in accepted):
        accepted += ["intern", "internship"]
    return accepted


def has_accepted_level(job: Job, criteria: SearchCriteria) -> bool:
    """True se o título ou as tags da vaga citam um dos níveis aceitos."""
    return any(contains_term(job.headline, level) for level in accepted_levels(criteria))


class KeywordFilter(BaseFilter):
    """Exige que a vaga cite ao menos uma das tecnologias desejadas.

    Procura no título, descrição e tags. Sem palavras-chave configuradas,
    aceita tudo.
    """

    name = "keywords"

    def accepts(self, job: Job) -> bool:
        if not self.criteria.keywords:
            return True
        text = job.searchable_text
        return any(contains_term(text, kw) for kw in self.criteria.keywords)


class ExcludedKeywordFilter(BaseFilter):
    """Descarta a vaga se ela citar qualquer termo excluído (ex.: "php").

    Termos de senioridade (ex.: "sênior", "tech lead") são procurados só no
    título e nas tags (``Job.headline``): uma vaga júnior que diga "mentoria de devs sênior" na descrição
    não deve ser descartada. Os demais termos valem para o texto inteiro.
    """

    name = "excluded_keywords"

    def accepts(self, job: Job) -> bool:
        for term in self.criteria.excluded_keywords:
            text = job.headline if term in KNOWN_SENIORITY_LEVELS else job.searchable_text
            if contains_term(text, term):
                return False
        return True


class SeniorityFilter(BaseFilter):
    """Mantém vagas do nível desejado ou sem nível informado.

    Olha título e tags (``Job.headline``), não a descrição: descrições costumam citar vários níveis ("você vai
    trabalhar com devs sêniores"), o que geraria falsos descartes.

    - Título cita um nível aceito → aceita.
    - Título cita apenas níveis não aceitos (ex.: "Sênior") → descarta.
    - Título não cita nível nenhum → aceita; o ranking dá nota menor.

    Se algum termo de estágio for aceito (ex.: "estágio"), os equivalentes
    em inglês ("intern", "internship") também são.
    """

    name = "seniority"

    def accepts(self, job: Job) -> bool:
        if not self.criteria.seniority:
            return True
        if has_accepted_level(job, self.criteria):
            return True
        return not any(contains_term(job.headline, level) for level in KNOWN_SENIORITY_LEVELS)


class LocationFilter(BaseFilter):
    """Aplica as regras de local e trabalho remoto.

    - ``remote_only``: descarta vagas presenciais/híbridas.
    - Vaga remota: aceita se não tiver restrição de local ou se o local
      citar uma região aceita (``remote_regions``, ex.: Worldwide, LATAM,
      Brazil) ou uma cidade desejada. "USA Only", por exemplo, é descartada.
    - Vaga presencial: aceita se o local citar uma das cidades desejadas.
      Sem cidades configuradas ou sem local informado, aceita.
    """

    name = "location"

    def accepts(self, job: Job) -> bool:
        location = job.location.lower()
        if job.remote:
            if not location:
                return True
            allowed = [*self.criteria.remote_regions, *self.criteria.locations]
            return any(region in location for region in allowed)
        if self.criteria.remote_only:
            return False
        if not self.criteria.locations or not location:
            return True
        return any(city in location for city in self.criteria.locations)


class SalaryFilter(BaseFilter):
    """Descarta vagas que pagam abaixo do mínimo (estágio ou geral).

    Usa o maior valor divulgado da faixa (``salary_max`` ou ``salary_min``).
    Vagas sem salário passam se ``accept_unknown_salary`` for True.
    """

    name = "salary"

    def accepts(self, job: Job) -> bool:
        minimum = self.criteria.min_salary_for(job.is_internship)
        offered = job.salary_max if job.salary_max is not None else job.salary_min
        if offered is None:
            return self.criteria.accept_unknown_salary
        if minimum is None:
            return True
        return offered >= minimum
