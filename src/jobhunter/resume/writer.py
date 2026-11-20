"""Gravação dos currículos adaptados em arquivos."""

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
    """Salva cada currículo adaptado como Markdown na pasta de saída.

    Nome do arquivo: ``<empresa>_<titulo>_<uid>.md`` (o ``uid`` evita
    sobrescrever vagas com mesmo título). O topo do arquivo traz um
    comentário com o link da vaga, invisível ao converter para PDF.

    Args:
        output_dir: pasta de saída (criada se não existir).
    """

    def __init__(self, output_dir: str | Path):
        self.output_dir = Path(output_dir)

    def write(self, job: Job, resume_markdown: str) -> Path:
        """Grava o arquivo e devolve o caminho criado.

        Raises:
            ResumeError: se a pasta ou o arquivo não puderem ser escritos.
        """
        path = self.output_dir / f"{slugify(job.company)}_{slugify(job.title)}_{job.uid}.md"
        header = (f"<!-- Vaga: {job.title} | {job.company} | nota {job.score} -->\n"
                  f"<!-- Link: {job.url} -->\n\n")
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(header + resume_markdown.strip() + "\n", encoding="utf-8")
        except OSError as exc:
            raise ResumeError(f"Não foi possível salvar o currículo em '{path}': {exc}") from exc
        return path
