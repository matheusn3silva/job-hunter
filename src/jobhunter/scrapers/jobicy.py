"""Scraper do Jobicy (API pública e gratuita de vagas remotas)."""

from __future__ import annotations

from typing import Any

from jobhunter.models import Job, SearchCriteria
from jobhunter.scrapers.base import BaseScraper
from jobhunter.utils.text import parse_datetime, strip_html

COUNT = 50
GEO = "brazil"


class JobicyScraper(BaseScraper):
    """Busca vagas remotas abertas para quem mora no Brasil (``geo=brazil``).

    API gratuita e sem chave, mas com limite de requisições apertado: fazemos
    UMA chamada por execução. O nível informado pela fonte (``jobLevel``,
    ex.: "Senior", "Junior") vira tag, para os filtros de senioridade.
    """

    def _fetch(self, criteria: SearchCriteria) -> list[Job]:
        payload = self._get_json(self.source.url, {"count": COUNT, "geo": GEO})
        jobs = (self._parse(item) for item in payload.get("jobs", []))
        return [job for job in jobs if job]

    def _parse(self, item: dict[str, Any]) -> Job | None:
        title, url = item.get("jobTitle"), item.get("url")
        if not title or not url:
            return None
        level = item.get("jobLevel")
        tags = (level,) if level and level.lower() != "any" else ()
        return Job(
            title=title,
            company=item.get("companyName") or "",
            url=url,
            description=strip_html(item.get("jobDescription") or item.get("jobExcerpt")),
            source=self.source.name,
            location=item.get("jobGeo") or "",
            remote=True,
            posted_at=parse_datetime(item.get("pubDate")),
            tags=tags,
        )
