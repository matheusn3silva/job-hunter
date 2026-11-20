"""Gravação dos prompts de currículo em arquivos de texto."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from jobhunter.models import Job
from jobhunter.resume.reader import ResumeError

MAX_SLUG = 40


def slugify(text: str) -> str:
    """Texto seguro para nome de arquivo: sem acento, minúsculo, com hífens."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug[:MAX_SLUG].rstrip("-") or "vaga"


class ResumeWriter:
    """Salva cada prompt como ``.txt`` na pasta de saída.

    Nome do arquivo: ``<posição>_<empresa>_<titulo>_<uid>.txt``. A posição no
    ranking (01, 02...) deixa os arquivos ordenados do melhor para o pior no
    gerenciador de arquivos; o ``uid`` evita sobrescrever vagas com o mesmo
    título entre execuções.

    Args:
        output_dir: pasta de saída (criada se não existir).
    """

    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)

    def write(self, job: Job, text: str, rank: int = 1) -> Path:
        """Grava o arquivo e devolve o caminho criado.

        Args:
            rank: posição da vaga no ranking (1 = melhor).

        Raises:
            ResumeError: se a pasta ou o arquivo não puderem ser escritos.
        """
        name = f"{rank:02d}_{slugify(job.company)}_{slugify(job.title)}_{job.uid}.txt"
        path = self.output_dir / name
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(text.strip() + "\n", encoding="utf-8")
        except OSError as exc:
            raise ResumeError(f"Não foi possível salvar o prompt em '{path}': {exc}") from exc
        return path
