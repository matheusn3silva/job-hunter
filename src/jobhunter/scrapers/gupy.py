"""Scraper da Gupy (busca pública do portal de vagas portal.gupy.io)."""

from __future__ import annotations

from typing import Any

from jobhunter.models import Job, SearchCriteria
from jobhunter.scrapers.base import BaseScraper
from jobhunter.utils.text import parse_datetime, strip_html

PAGE_SIZE = 100  # máximo aceito pela busca do portal


class GupyScraper(BaseScraper):
    """Busca vagas na Gupy, uma requisição por palavra-chave.

    Usa a mesma rota que o site ``portal.gupy.io`` chama ao pesquisar
    (``/api/job-search/jobs?jobName=...&limit=...&offset=...``): pública,
    sem login e com a descrição completa. A API oficial (``api.gupy.io``)
    exige token de empresa cliente, por isso não serve para uso pessoal.

    A rota não é documentada e pode mudar sem aviso; se falhar, o runner
    registra o erro e as outras fontes continuam. Campos usados: ``data[]``
    com ``name``, ``careerPageName``, ``jobUrl``, ``city``, ``state``,
    ``workplaceType``, ``publishedDate``, ``description`` e ``type``. Itens
    sem título ou link são ignorados.
    """

    def _fetch(self, criteria: SearchCriteria) -> list[Job]:
        jobs: dict[str, Job] = {}
        for term in criteria.keywords or [""]:
            payload = self._get_json(
                self.source.url, {"jobName": term, "limit": PAGE_SIZE, "offset": 0}
            )
            for item in payload.get("data", []):
                job = self._parse(item)
                if job:
                    jobs[job.uid] = job  # mesma vaga em duas buscas vira uma só
        return list(jobs.values())

    def _parse(self, item: dict[str, Any]) -> Job | None:
        title, url = item.get("name"), item.get("jobUrl")
        if not title or not url:
            return None
        workplace = (item.get("workplaceType") or "").lower()
        # A Gupy é um portal brasileiro: sem país informado, assume Brasil. Isso
        # permite ao filtro de localização aceitar vagas remotas daqui.
        country = item.get("country") or "Brasil"
        location = ", ".join(p for p in (item.get("city"), item.get("state"), country) if p)
        return Job(
            title=title,
            company=item.get("careerPageName") or "",
            url=url,
            description=strip_html(item.get("description")),
            source=self.source.name,
            location=location,
            remote=workplace == "remote" or bool(item.get("isRemoteWork")),
            posted_at=parse_datetime(item.get("publishedDate")),
            tags=(item["type"],) if item.get("type") else (),
        )