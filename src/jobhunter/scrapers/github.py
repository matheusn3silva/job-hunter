"""Scraper dos repositórios de vagas brasileiros no GitHub (ex.: backend-br/vagas)."""

from __future__ import annotations

import re
from typing import Any

from jobhunter.models import Job, SearchCriteria
from jobhunter.scrapers.base import BaseScraper
from jobhunter.utils.text import contains_term, parse_datetime

PER_PAGE = 100
REMOTE_MARKERS = ("remoto", "remote", "100% remoto")
# Prefixo entre colchetes no título: "[Remoto]", "[São Paulo/SP]", "[Híbrido]".
_BRACKET = re.compile(r"^\s*\[([^\]]+)\]\s*")


class GitHubVagasScraper(BaseScraper):
    """Lê vagas publicadas como issues em repositórios da comunidade.

    Repositórios como ``frontendbr/vagas`` e ``backend-br/vagas`` publicam
    cada vaga como uma issue aberta, com etiquetas de nível (Júnior, Pleno),
    modelo (Remoto, CLT, PJ) e tecnologias. A API do GitHub é gratuita
    (60 requisições/hora sem login); fazemos 1 requisição por repositório.

    A ``url`` da fonte é o endpoint de issues, por exemplo
    ``https://api.github.com/repos/backend-br/vagas/issues``.
    """

    def _fetch(self, criteria: SearchCriteria) -> list[Job]:
        items = self._get_json(
            self.source.url,
            {"state": "open", "per_page": PER_PAGE, "sort": "created", "direction": "desc"},
        )
        jobs = (self._parse(item) for item in items if "pull_request" not in item)
        return [job for job in jobs if job]

    def _parse(self, item: dict[str, Any]) -> Job | None:
        raw_title, url = item.get("title"), item.get("html_url")
        if not raw_title or not url:
            return None
        labels = tuple(label["name"] for label in item.get("labels", []) if label.get("name"))
        bracket = _BRACKET.match(raw_title)
        place = bracket.group(1).strip() if bracket else ""
        title = raw_title[bracket.end():].strip() if bracket else raw_title.strip()
        remote = any(contains_term(text, marker) for marker in REMOTE_MARKERS
                     for text in (place, *labels))
        return Job(
            title=title,
            company=self._company_from_title(title),
            url=url,
            description=item.get("body") or "",
            source=self.source.name,
            # Repositórios brasileiros: vaga remota é aberta a quem está no Brasil.
            location="Brasil" if remote else self._city(place),
            remote=remote,
            posted_at=parse_datetime(item.get("created_at")),
            tags=labels,
        )

    @staticmethod
    def _company_from_title(title: str) -> str:
        """Melhor palpite da empresa: "... na Empresa" ou "... - Empresa"."""
        if " na " in title:
            return title.rsplit(" na ", 1)[1].strip()
        if " - " in title:
            return title.rsplit(" - ", 1)[1].strip()
        return ""

    @staticmethod
    def _city(place: str) -> str:
        """O colchete é cidade quando não é um modelo de trabalho (ex.: "Híbrido")."""
        if not place or contains_term(place, "híbrido") or contains_term(place, "hibrido"):
            return ""
        return place
