"""Funções de apoio para tratar texto e datas vindos das fontes."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup


# Tags que começam um novo parágrafo ou linha no texto final.
_BLOCK_TAGS = ("br", "p", "div", "li", "ul", "ol", "tr", "h1", "h2", "h3", "h4", "h5", "h6")


def strip_html(html: str | None) -> str:
    """Remove as tags HTML e devolve texto puro, mantendo as quebras de linha.

    Parágrafos, itens de lista e ``<br>`` viram quebras de linha (para a
    descrição ficar legível no site); espaços repetidos e linhas vazias
    em excesso são removidos.
    """
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup.find_all(_BLOCK_TAGS):
        tag.insert_after("\n")
    lines = (" ".join(line.split()) for line in soup.get_text().splitlines())
    return "\n".join(line for line in lines if line)


def parse_datetime(value: str | None) -> datetime | None:
    """Converte data ISO-8601 ou de RSS (RFC 822) em datetime com fuso (UTC se vier sem).

    Retorna None se o valor for vazio ou inválido. Padronizar o fuso evita
    erro ao comparar datas de fontes diferentes na hora de ordenar.
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:  # formato de RSS: "Sun, 01 Nov 2026 07:31:04 +0000"
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def contains_term(text: str, term: str) -> bool:
    """True se ``term`` aparece em ``text`` como palavra inteira.

    Evita falsos positivos de substring: "java" não casa com "javascript"
    e "senior" não casa com "seniority". Termos que começam ou terminam com
    símbolo (ex.: ".net") só exigem limite de palavra no lado alfanumérico,
    então ".net" casa com "asp.net". A comparação não diferencia maiúsculas.
    """
    term = term.strip().lower()
    if not term:
        return False
    start = r"(?<!\w)" if re.match(r"\w", term) else ""
    end = r"(?!\w)" if re.search(r"\w$", term) else ""
    return re.search(start + re.escape(term) + end, text.lower()) is not None
