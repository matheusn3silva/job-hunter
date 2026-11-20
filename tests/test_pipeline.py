from datetime import datetime, timezone
from pathlib import Path

import pytest

from jobhunter.config import Settings
from jobhunter.filters import FilterChain
from jobhunter.main import format_report, load_settings, main
from jobhunter.models import Job, SearchCriteria
from jobhunter.ranking import JobRanker
from jobhunter.resume import ResumeError, ResumeWriter
from jobhunter.services import JobHuntPipeline, PipelineResult
from jobhunter.storage import JobRepository

CRITERIA = SearchCriteria(keywords=["python"], excluded_keywords=["php"], top_n=2)


def make_job(n: int, **overrides) -> Job:
    base = dict(title=f"Dev Python {n}", company="Acme", url=f"https://x/{n}",
                description="python", source="teste", remote=True,
                posted_at=datetime(2026, 11, 10 + n, tzinfo=timezone.utc))  # maior n = mais recente
    return Job(**{**base, **overrides})


class FakeRunner:
    def __init__(self, jobs, errors=()):
        self.jobs, self.errors = jobs, list(errors)

    def run(self, criteria):
        return list(self.jobs)


class FakeReader:
    def __init__(self, error=None):
        self.error = error

    def read(self, path):
        if self.error:
            raise ResumeError(self.error)
        return "Fulano - Python"


class FakeBuilder:
    def __init__(self):
        self.calls = []

    def build(self, job, resume_text=None):
        self.calls.append((job.url, resume_text))
        return f"prompt para {job.title}"


class BrokenWriter(ResumeWriter):
    """Falha ao gravar a vaga indicada (simula disco cheio, permissão...)."""

    def __init__(self, output_dir, fail_url):
        super().__init__(output_dir)
        self.fail_url = fail_url

    def write(self, job, text, rank=1):
        if job.url == self.fail_url:
            raise ResumeError("disco cheio")
        return super().write(job, text, rank)


def build(tmp_path, jobs, reader=None, builder=None, writer=None, repo=None, runner_errors=()):
    settings = Settings(criteria=CRITERIA, sources=[], resume_path=tmp_path / "cv.pdf",
                        output_dir=tmp_path / "out", db_path=tmp_path / "jobs.db")
    repo = repo or JobRepository(":memory:")
    pipeline = JobHuntPipeline(
        settings=settings, runner=FakeRunner(jobs, runner_errors),
        filters=FilterChain.from_criteria(CRITERIA), repository=repo,
        ranker=JobRanker.from_criteria(CRITERIA), reader=reader or FakeReader(),
        prompt_builder=builder or FakeBuilder(),
        writer=writer or ResumeWriter(settings.output_dir),
    )
    return pipeline, repo


JOBS = [make_job(1), make_job(3), make_job(2), make_job(4, description="python php")]
# Mesma nota em tudo; desempate pela data: top 2 = vagas 3 e 2.


def test_full_run_generates_prompts_for_top_and_saves_memory(tmp_path):
    pipeline, repo = build(tmp_path, JOBS, runner_errors=["[x] falha HTTP"])
    result = pipeline.run()
    assert (result.collected, result.approved, result.new) == (4, 3, 3)
    assert result.rejected == {"excluded_keywords": 1}
    assert [j.url for j in result.top] == ["https://x/3", "https://x/2"]
    assert len(result.files) == 2 and all(p.exists() for p in result.files)
    assert [p.name[:3] for p in result.files] == ["01_", "02_"]
    assert result.saved == 2 and repo.count() == 2
    assert result.errors == ["[x] falha HTTP"]


def test_second_run_skips_jobs_already_seen(tmp_path):
    repo = JobRepository(":memory:")
    build(tmp_path, JOBS, repo=repo)[0].run()
    result = build(tmp_path, JOBS, repo=repo)[0].run()
    assert result.new == 1
    assert [j.url for j in result.top] == ["https://x/1"]


def test_dry_run_does_not_write_nor_save(tmp_path):
    builder = FakeBuilder()
    pipeline, repo = build(tmp_path, JOBS, builder=builder)
    result = pipeline.run(dry_run=True)
    assert len(result.top) == 2
    assert builder.calls == [] and result.files == [] and repo.count() == 0


def test_failed_job_is_reported_and_not_saved(tmp_path):
    writer = BrokenWriter(tmp_path / "out", fail_url="https://x/3")
    pipeline, repo = build(tmp_path, JOBS, writer=writer)
    result = pipeline.run()
    assert len(result.files) == 1 and result.saved == 1
    assert not repo.has_seen(make_job(3).uid)
    assert "disco cheio" in result.errors[0]


def test_unreadable_resume_still_writes_prompts(tmp_path):
    builder = FakeBuilder()
    pipeline, repo = build(tmp_path, JOBS, reader=FakeReader("Currículo não encontrado"),
                           builder=builder)
    result = pipeline.run()
    assert [text for _, text in builder.calls] == [None, None]
    assert len(result.files) == 2 and repo.count() == 2
    assert "Currículo não encontrado" in result.errors[0] and "anexar" in result.errors[0]


def test_resume_text_goes_into_prompts(tmp_path):
    builder = FakeBuilder()
    build(tmp_path, JOBS, builder=builder)[0].run()
    assert all(text == "Fulano - Python" for _, text in builder.calls)


def test_no_jobs(tmp_path):
    result = build(tmp_path, [])[0].run()
    assert result.top == [] and result.saved == 0


# --- CLI ---------------------------------------------------------------------

def write_config(root: Path, sources: str = "sources: []\n") -> Path:
    config = root / "config"
    config.mkdir()
    (config / "settings.yaml").write_text(
        "criteria:\n  keywords: [python]\n  top_n: 5\n"
        "paths:\n  resume: data/resume/cv.pdf\n  output: data/output\n  database: data/jobs.db\n",
        encoding="utf-8")
    (config / "sources.yaml").write_text(sources, encoding="utf-8")
    return config


def test_load_settings_resolves_paths_from_project_root(tmp_path):
    settings = load_settings(write_config(tmp_path), top=3)
    assert settings.db_path == tmp_path / "data" / "jobs.db"
    assert settings.output_dir == tmp_path / "data" / "output"
    assert settings.criteria.top_n == 3


def test_load_settings_rejects_invalid_top(tmp_path):
    with pytest.raises(Exception, match="--top"):
        load_settings(write_config(tmp_path), top=0)


def test_main_dry_run_with_no_sources(tmp_path, capsys):
    assert main(["--config-dir", str(write_config(tmp_path)), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "Coletadas: 0" in out and "Nenhuma vaga nova" in out and "--dry-run" in out
    assert (tmp_path / "data" / "jobs.db").exists()


def test_main_config_error_returns_1(tmp_path, capsys):
    assert main(["--config-dir", str(tmp_path / "nao-existe")]) == 1
    assert "Erro:" in capsys.readouterr().out


def test_format_report_lists_top_files_and_errors():
    result = PipelineResult(collected=5, approved=2, new=2, rejected={"salary": 3},
                            top=[make_job(1, score=8.25)], files=[Path("out/cv.md")],
                            saved=1, errors=["[gupy] falha HTTP"])
    text = format_report(result, dry_run=False)
    for expected in ("Coletadas: 5", "salary: 3", "[ 8.2] Dev Python 1", "https://x/1",
                     "Prompts de currículo gerados (1)", "out/cv.md", "memória: 1",
                     "[gupy] falha HTTP"):
        assert expected in text
