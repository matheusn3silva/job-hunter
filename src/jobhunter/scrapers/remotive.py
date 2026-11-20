"""Scraper da Remotive (API pública de vagas remotas)."""

from __future__ import annotations

from typing import Any

from jobhunter.models import Job, SearchCriteria
from jobhunter.scrapers.base import BaseScraper
from jobhunter.utils.text import parse_datetime, strip_html


class RemotiveScraper(BaseScraper):
    """Busca vagas de software na Remotive com UMA única requisição.

    Respeita o limite da API (poucas chamadas por dia): baixa a categoria
    ``software-dev`` inteira e deixa o filtro por palavra-chave para a etapa
    de filtros. O link de cada vaga aponta para a Remotive, como exigem os
    termos de uso. ``candidate_required_location`` vira ``location`` para
    que o filtro de localização exclua vagas restritas a outros países.
    """

    CATEGORY = "software-dev"

    def _fetch(self, criteria: SearchCriteria) -> list[Job]:
        payload = self._get_json(self.source.url, {"category": self.CATEGORY})
        jobs = (self._parse(item) for item in payload.get("jobs", []))
        return [job for job in jobs if job]

    def _parse(self, item: dict[str, Any]) -> Job | None:
        title, url = item.get("title"), item.get("url")
        if not title or not url:
            return None
        tags = tuple(t for t in (item.get("category"), item.get("job_type")) if t)
        return Job(
            title=title,
            company=item.get("company_name") or "",
            url=url,
            description=strip_html(item.get("description")),
            source=self.source.name,
            location=item.get("candidate_required_location") or "",
            remote=True,
            posted_at=parse_datetime(item.get("publication_date")),
            tags=tags,
        )