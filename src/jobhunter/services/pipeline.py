"""Orquestração de todas as etapas: da busca ao currículo adaptado."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from jobhunter.config import Settings
from jobhunter.filters import FilterChain
from jobhunter.models import Job
from jobhunter.ranking import JobRanker
from jobhunter.resume import ResumeError, ResumeReader, ResumeTailor, ResumeWriter
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
        top: as melhores vagas, já com nota.
        files: currículos gerados.
        saved: quantas vagas foram gravadas na memória.
        errors: falhas não fatais (fonte fora do ar, erro da API em uma vaga...).
    """

    collected: int = 0
    approved: int = 0
    new: int = 0
    rejected: dict[str, int] = field(default_factory=dict)
    top: list[Job] = field(default_factory=list)
    files: list[Path] = field(default_factory=list)
    saved: int = 0
    errors: list[str] = field(default_factory=list)


class JobHuntPipeline:
    """Executa o fluxo completo do JobHunter.

    Scrapers → Filtros → Remover já vistas → Ranking → Top N →
    Adaptar currículo → Salvar memória

    Esta classe só coordena: cada etapa é feita pela classe responsável,
    recebida no construtor (assim os testes trocam qualquer peça por uma
    falsa). Só as vagas com currículo gerado vão para a memória: se a API
    falhar em uma vaga, ela volta na próxima execução.
    """

    def __init__(
        self,
        settings: Settings,
        runner: ScraperRunner,
        filters: FilterChain,
        repository: JobRepository,
        ranker: JobRanker,
        reader: ResumeReader,
        tailor: ResumeTailor,
        writer: ResumeWriter,
    ):
        self.settings = settings
        self.runner = runner
        self.filters = filters
        self.repository = repository
        self.ranker = ranker
        self.reader = reader
        self.tailor = tailor
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
            tailor=ResumeTailor(),
            writer=ResumeWriter(settings.output_dir),
        )

    def run(self, dry_run: bool = False) -> PipelineResult:
        """Executa todas as etapas.

        Args:
            dry_run: só busca, filtra e ranqueia; não chama a IA nem grava
                nada na memória (útil para conferir o ranking).
        """
        result = PipelineResult()
        jobs = self.runner.run(self.settings.criteria)
        result.errors.extend(self.runner.errors)
        result.collected = len(jobs)

        approved = self.filters.apply(jobs)
        result.approved = len(approved)
        result.rejected = dict(self.filters.rejected)

        new = self.repository.filter_unseen(approved)
        result.new = len(new)
        result.top = self.ranker.top(new)

        if dry_run or not result.top:
            return result

        processed = self._tailor_resumes(result)
        result.saved = self.repository.mark_seen(processed)
        return result

    def _tailor_resumes(self, result: PipelineResult) -> list[Job]:
        """Gera um currículo por vaga do top; devolve as vagas que deram certo."""
        try:
            resume_text = self.reader.read(self.settings.resume_path)
        except ResumeError as exc:
            result.errors.append(str(exc))
            return []
        processed = []
        for job in result.top:
            try:
                markdown = self.tailor.tailor(resume_text, job)
                result.files.append(self.writer.write(job, markdown))
                processed.append(job)
            except ResumeError as exc:
                log.warning("%s", exc)
                result.errors.append(f"[{job.title} | {job.company}] {exc}")
        return processed
