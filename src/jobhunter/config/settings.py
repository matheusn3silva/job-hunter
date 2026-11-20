"""Carregamento das configurações a partir dos arquivos YAML."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from jobhunter.models.search_criteria import SearchCriteria

VALID_SOURCE_TYPES = ("html", "rss", "api")


class ConfigError(ValueError):
    """Erro de configuração com mensagem amigável."""


@dataclass(frozen=True)
class SourceConfig:
    """Uma fonte de vagas (site, API ou RSS).

    Attributes:
        name: nome único da fonte.
        type: ``html``, ``rss`` ou ``api``.
        url: endereço consultado.
        enabled: permite desligar a fonte sem apagá-la do arquivo.
    """

    name: str
    type: str
    url: str
    enabled: bool = True

    def __post_init__(self) -> None:
        if self.type not in VALID_SOURCE_TYPES:
            raise ConfigError(
                f"Fonte '{self.name}': tipo '{self.type}' inválido. "
                f"Use um de {VALID_SOURCE_TYPES}."
            )


@dataclass
class Settings:
    """Todas as configurações do programa, já validadas."""

    criteria: SearchCriteria
    sources: list[SourceConfig]
    resume_path: Path
    output_dir: Path
    db_path: Path

    @classmethod
    def load(cls, settings_file: Path, sources_file: Path) -> Settings:
        """Lê ``settings.yaml`` e ``sources.yaml``.

        Raises:
            ConfigError: arquivo ausente, campo faltando ou valor inválido.
        """
        data = cls._read_yaml(Path(settings_file))
        raw_sources = cls._read_yaml(Path(sources_file))
        try:
            paths = data["paths"]
            return cls(
                criteria=SearchCriteria(**data["criteria"]),
                sources=[SourceConfig(**s) for s in raw_sources["sources"]],
                resume_path=Path(paths["resume"]),
                output_dir=Path(paths["output"]),
                db_path=Path(paths["database"]),
            )
        except KeyError as exc:
            raise ConfigError(f"Campo obrigatório ausente: {exc}") from exc
        except TypeError as exc:
            raise ConfigError(f"Campo inválido na configuração: {exc}") from exc

    @property
    def active_sources(self) -> list[SourceConfig]:
        """Apenas as fontes com ``enabled: true``."""
        return [s for s in self.sources if s.enabled]

    @staticmethod
    def _read_yaml(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise ConfigError(f"Arquivo de configuração não encontrado: {path}")
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(content, dict):
            raise ConfigError(f"Arquivo vazio ou inválido: {path}")
        return content