"""Scraper do We Work Remotely (feed RSS gratuito)."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from jobhunter.models import Job, SearchCriteria
from jobhunter.scrapers.base import BaseScraper
from jobhunter.utils.text import parse_datetime, strip_html


class WeWorkRemotelyScraper(BaseScraper):
    """Lê o feed RSS de vagas de programação do We Work Remotely.

    Cada ``<item>`` traz ``title`` no formato "Empresa: Cargo", ``region``
    (ex.: "Anywhere in the World", "USA Only"), ``category``, ``description``
    (HTML), ``pubDate`` e ``link``. A região vira ``location`` para o filtro
    descartar vagas restritas a outros países. Uma requisição por execução.
    """

    def _fetch(self, criteria: SearchCriteria) -> list[Job]:
        try:
            root = ET.fromstring(self._get_text(self.source.url))
        except ET.ParseError as exc:
            raise ValueError(f"RSS inválido: {exc}") from exc
        jobs = (self._parse(item) for item in root.iter("item"))
        return [job for job in jobs if job]

    def _parse(self, item: ET.Element) -> Job | None:
        raw_title, url = item.findtext("title"), item.findtext("link")
        if not raw_title or not url:
            return None
        company, _, title = raw_title.partition(":")
        if not title:  # título sem "Empresa:"
            company, title = "", raw_title
        category = item.findtext("category")
        return Job(
            title=title.strip(),
            company=company.strip(),
            url=url.strip(),
            description=strip_html(item.findtext("description")),
            source=self.source.name,
            location=(item.findtext("region") or "").strip(),
            remote=True,
            posted_at=parse_datetime(item.findtext("pubDate")),
            tags=(category,) if category else (),
        )
