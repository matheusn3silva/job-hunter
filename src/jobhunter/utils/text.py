"""Funções de apoio para tratar texto e datas vindos das fontes."""

from __future__ import annotations

from datetime import datetime, timezone

from bs4 import BeautifulSoup


def strip_html(html: str | None) -> str:
    """Remove as tags HTML e devolve texto puro, com espaços normalizados."""
    return BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)


def parse_datetime(value: str | None) -> datetime | None:
    """Converte data ISO-8601 em datetime com fuso (UTC se vier sem fuso).

    Retorna None se o valor for vazio ou inválido. Padronizar o fuso evita
    erro ao comparar datas de fontes diferentes na hora de ordenar.
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)