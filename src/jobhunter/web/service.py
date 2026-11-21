"""Regras do site: currículo, busca, prompts e detalhes das vagas.

As rotas do Flask (``app.py``) só recebem a requisição e chamam esta
classe; assim a lógica fica testável sem servidor e sem navegador.
"""

from __future__ import annotations

import os
import tempfile
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from jobhunter.config import Settings
from jobhunter.models import Job
from jobhunter.resume import ResumeError, ResumeReader
from jobhunter.services import JobHuntPipeline, PipelineResult, PromptBatch
from jobhunter.storage import JobRepository
from jobhunter.web.sources import SourceStyle, style_for

PipelineFactory = Callable[[Settings, JobRepository], JobHuntPipeline]


@dataclass(frozen=True)
class SourceStatus:
    """Uma fonte ativa e o que aconteceu com ela na última busca.

    ``count`` é None antes da primeira busca; ``error`` só existe se falhou.
    """

    name: str
    style: SourceStyle
    count: int | None = None
    error: str | None = None


@dataclass(frozen=True)
class PromptFile:
    """Um prompt ``.txt`` salvo na pasta de saída."""

    name: str
    modified: datetime


class WebService:
    """Estado e ações do site local (um usuário, no próprio computador).

    Guarda em memória o resultado da última busca, para mostrar as listas e
    os detalhes das vagas. Buscar não grava nada; só gerar prompts grava as
    vagas na memória (igual à CLI). Um ``Lock`` impede duas buscas ou
    gerações ao mesmo tempo (o servidor atende várias abas em paralelo).

    Args:
        settings: configurações já carregadas (caminhos absolutos).
        pipeline_factory: cria o pipeline com um repositório aberto;
            injetável para os testes usarem peças falsas.
    """

    def __init__(self, settings: Settings, pipeline_factory: PipelineFactory = JobHuntPipeline.from_settings):
        self.settings = settings
        self._pipeline_factory = pipeline_factory
        self._lock = threading.Lock()
        self.last: PipelineResult | None = None
        self.prompted: set[str] = set()

    # --- currículo ---------------------------------------------------------

    def resume_exists(self) -> bool:
        return self.settings.resume_path.is_file()

    def save_resume(self, data: bytes, filename: str) -> None:
        """Valida o PDF enviado e o salva como currículo base.

        O arquivo é conferido numa cópia temporária antes de substituir o
        atual: um PDF ruim nunca apaga o currículo que já estava salvo.

        Raises:
            ResumeError: arquivo vazio, sem extensão .pdf ou sem texto legível.
        """
        if not filename.lower().endswith(".pdf"):
            raise ResumeError("Envie o currículo em PDF.")
        if not data:
            raise ResumeError("O arquivo enviado está vazio.")
        target = self.settings.resume_path
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(suffix=".pdf", dir=target.parent)
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            ResumeReader().read(tmp)  # levanta ResumeError se não der para ler
            tmp.replace(target)
        finally:
            tmp.unlink(missing_ok=True)

    # --- busca -------------------------------------------------------------

    def search(self) -> PipelineResult:
        """Busca, filtra e ranqueia as vagas novas; guarda o resultado."""
        with self._lock, JobRepository(self.settings.db_path) as repo:
            self.last = self._pipeline_factory(self.settings, repo).search()
            self.prompted = set()
        return self.last

    @property
    def top(self) -> list[Job]:
        return self.last.top if self.last else []

    @property
    def others(self) -> list[Job]:
        """Vagas fora do top (ranking completo menos o top)."""
        return self.last.ranked[len(self.last.top):] if self.last else []

    def job(self, uid: str) -> Job | None:
        """Vaga da última busca pelo ``uid`` (None se não existir)."""
        ranked = self.last.ranked if self.last else []
        return next((job for job in ranked if job.uid == uid), None)

    def rank_of(self, uid: str) -> int | None:
        """Posição da vaga no ranking (1 = melhor)."""
        ranked = self.last.ranked if self.last else []
        return next((pos for pos, job in enumerate(ranked, start=1) if job.uid == uid), None)

    def sources(self) -> list[SourceStatus]:
        """Fontes ativas, com o resultado da última busca."""
        counts = self.last.source_counts if self.last else {}
        failures = self.last.source_failures if self.last else {}
        return [
            SourceStatus(s.name, style_for(s.name), counts.get(s.name), failures.get(s.name))
            for s in self.settings.active_sources
        ]

    # --- prompts -----------------------------------------------------------

    def create_top_prompts(self) -> PromptBatch:
        """Gera os prompts de todas as vagas do top."""
        return self._create(self.top, first_rank=1)

    def create_prompt(self, uid: str) -> PromptBatch:
        """Gera o prompt de uma vaga (normalmente de fora do top).

        Raises:
            KeyError: se a vaga não estiver na última busca.
        """
        job = self.job(uid)
        if job is None:
            raise KeyError(uid)
        return self._create([job], first_rank=self.rank_of(uid) or 1)

    def _create(self, jobs: list[Job], first_rank: int) -> PromptBatch:
        with self._lock, JobRepository(self.settings.db_path) as repo:
            batch = self._pipeline_factory(self.settings, repo).write_prompts(jobs, first_rank)
        names = {path.name for path in batch.files}
        self.prompted |= {job.uid for job in jobs if any(job.uid in n for n in names)}
        return batch

    def list_prompts(self) -> list[PromptFile]:
        """Prompts salvos na pasta de saída, do mais novo para o mais antigo."""
        folder = self.settings.output_dir
        if not folder.is_dir():
            return []
        files = [PromptFile(p.name, datetime.fromtimestamp(p.stat().st_mtime))
                 for p in folder.glob("*.txt")]
        return sorted(files, key=lambda f: (f.modified, f.name), reverse=True)

    def read_prompt(self, name: str) -> str:
        """Conteúdo de um prompt salvo.

        Só aceita um nome de arquivo ``.txt`` da pasta de saída: caminhos
        como ``../config/settings.yaml`` são recusados.

        Raises:
            FileNotFoundError: nome inválido ou arquivo inexistente.
        """
        if Path(name).name != name or not name.endswith(".txt"):
            raise FileNotFoundError(name)
        path = self.settings.output_dir / name
        if not path.is_file():
            raise FileNotFoundError(name)
        return path.read_text(encoding="utf-8")
