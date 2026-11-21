"""Orquestração de todas as etapas: da busca ao prompt de currículo."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from jobhunter.config import Settings
from jobhunter.filters import FilterChain
from jobhunter.models import Job
from jobhunter.ranking import JobRanker
from jobhunter.resume import ResumeError, ResumePromptBuilder, ResumeReader, ResumeWriter
from jobhunter.scrapers import ScraperRunner
from jobhunter.storage import JobRepository

log = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """O que aconteceu em uma execução, para o relatório da CLI.

    Attributes:
        collected: vagas coletadas (já sem duplicatas entre fontes).
        approved: vagas aprovadas pelos filtros.
        new: aprovadas que ainda não estavam na memória.
        rejected: quantas cada filtro descartou.
        ranked: todas as vagas novas, com nota, da melhor para a pior.
        top: as ``top_n`` primeiras de ``ranked``.
        source_counts: vagas trazidas por cada fonte.
        source_failures: erro de cada fonte que falhou.
        files: prompts de currículo gerados (.txt).
        saved: quantas vagas foram gravadas na memória.
        errors: falhas não fatais (fonte fora do ar, currículo ilegível...).
    """

    collected: int = 0
    approved: int = 0
    new: int = 0
    rejected: dict[str, int] = field(default_factory=dict)
    ranked: list[Job] = field(default_factory=list)
    top: list[Job] = field(default_factory=list)
    source_counts: dict[str, int] = field(default_factory=dict)
    source_failures: dict[str, str] = field(default_factory=dict)
    files: list[Path] = field(default_factory=list)
    saved: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class PromptBatch:
    """Resultado de uma geração de prompts.

    Attributes:
        files: arquivos ``.txt`` criados.
        saved: quantas vagas foram gravadas na memória.
        errors: avisos (currículo ilegível, falha ao gravar uma vaga...).
    """

    files: list[Path] = field(default_factory=list)
    saved: int = 0
    errors: list[str] = field(default_factory=list)


class JobHuntPipeline:
    """Executa o fluxo completo do JobHunter.

    Scrapers → Filtros → Remover já vistas → Ranking → Top N →
    Prompt de currículo (.txt) → Salvar memória

    Esta classe só coordena: cada etapa é feita pela classe responsável,
    recebida no construtor (assim os testes trocam qualquer peça por uma
    falsa). Só as vagas com prompt salvo vão para a memória: se a gravação
    falhar em uma vaga, ela volta na próxima execução. Sem custo: nenhuma
    API paga é chamada.
    """

    def __init__(
        self,
        settings: Settings,
        runner: ScraperRunner,
        filters: FilterChain,
        repository: JobRepository,
        ranker: JobRanker,
        reader: ResumeReader,
        prompt_builder: ResumePromptBuilder,
        writer: ResumeWriter,
    ):
        self.settings = settings
        self.runner = runner
        self.filters = filters
        self.repository = repository
        self.ranker = ranker
        self.reader = reader
        self.prompt_builder = prompt_builder
        self.writer = writer

    @classmethod
    def from_settings(cls, settings: Settings, repository: JobRepository) -> JobHuntPipeline:
        """Monta o pipeline padrão a partir das configurações."""
        criteria = settings.criteria
        return cls(
            settings=settings,
            runner=ScraperRunner(settings.active_sources),
            filters=FilterChain.from_criteria(criteria),
            repository=repository,
            ranker=JobRanker.from_criteria(criteria),
            reader=ResumeReader(),
            prompt_builder=ResumePromptBuilder(),
            writer=ResumeWriter(settings.output_dir),
        )

    def run(self, dry_run: bool = False) -> PipelineResult:
        """Executa todas as etapas (usado pela CLI).

        Args:
            dry_run: só busca, filtra e ranqueia; não gera prompts nem grava
                nada na memória (útil para conferir o ranking).
        """
        result = self.search()
        if dry_run or not result.top:
            return result
        batch = self.write_prompts(result.top)
        result.files, result.saved = batch.files, batch.saved
        result.errors.extend(batch.errors)
        return result

    def search(self) -> PipelineResult:
        """Busca, filtra, remove as já vistas e ranqueia. Não grava nada.

        O site usa esta etapa sozinha: mostra o ranking completo e deixa o
        usuário escolher para quais vagas gerar prompts.
        """
        result = PipelineResult()
        jobs = self.runner.run(self.settings.criteria)
        result.errors.extend(self.runner.errors)
        result.source_counts = dict(self.runner.counts)
        result.source_failures = dict(self.runner.failures)
        result.collected = len(jobs)

        approved = self.filters.apply(jobs)
        result.approved = len(approved)
        result.rejected = dict(self.filters.rejected)

        new = self.repository.filter_unseen(approved)
        result.new = len(new)
        result.ranked = self.ranker.rank(new)
        result.top = result.ranked[: self.ranker.top_n]
        return result

    def write_prompts(self, jobs: list[Job], first_rank: int = 1) -> PromptBatch:
        """Gera um prompt ``.txt`` por vaga e grava as vagas na memória.

        Só as vagas com prompt salvo vão para a memória. Se o currículo não
        puder ser lido, os prompts saem mesmo assim, pedindo para anexar o
        PDF na conversa (e um aviso vai para ``errors``).

        Args:
            jobs: vagas, na ordem do ranking.
            first_rank: posição da primeira vaga (vai no nome do arquivo).
        """
        batch = PromptBatch()
        if not jobs:
            return batch
        try:
            resume_text: str | None = self.reader.read(self.settings.resume_path)
        except ResumeError as exc:
            batch.errors.append(f"{exc} Os prompts pedirão para anexar o currículo na conversa.")
            resume_text = None
        processed = []
        for rank, job in enumerate(jobs, start=first_rank):
            try:
                prompt = self.prompt_builder.build(job, resume_text)
                batch.files.append(self.writer.write(job, prompt, rank))
                processed.append(job)
            except ResumeError as exc:
                log.warning("%s", exc)
                batch.errors.append(f"[{job.title} | {job.company}] {exc}")
        batch.saved = self.repository.mark_seen(processed)
        return batch
