"""Aparência das fontes de vagas no site (nome, sigla e cor do selo)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceStyle:
    """Como uma fonte aparece no site.

    Attributes:
        label: nome legível (ex.: "Gupy").
        initials: sigla do selo redondo (ex.: "GU").
        color: cor de fundo do selo (cor da marca do site).
        site: página inicial da fonte, para o link do selo.
    """

    label: str
    initials: str
    color: str
    site: str


# Selos simples com as cores de cada site: nenhum logo é baixado de fora.
SOURCE_STYLES: dict[str, SourceStyle] = {
    "github-frontendbr": SourceStyle("GitHub frontendbr", "FE", "#24292f",
                                     "https://github.com/frontendbr/vagas"),
    "github-backendbr": SourceStyle("GitHub backend-br", "BE", "#24292f",
                                    "https://github.com/backend-br/vagas"),
    "gupy": SourceStyle("Gupy", "GU", "#1a3ce0", "https://portal.gupy.io"),
    "jobicy": SourceStyle("Jobicy", "JY", "#0f9d58", "https://jobicy.com"),
    "remotive": SourceStyle("Remotive", "RE", "#e3456e", "https://remotive.com"),
    "weworkremotely": SourceStyle("We Work Remotely", "WW", "#c9a227",
                                  "https://weworkremotely.com"),
}


def style_for(name: str) -> SourceStyle:
    """Estilo da fonte; fontes novas sem estilo recebem um selo cinza genérico."""
    return SOURCE_STYLES.get(name) or SourceStyle(name, name[:2].upper(), "#6b7280", "")
