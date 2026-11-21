import io
from datetime import datetime, timezone

import pytest

from jobhunter.config import Settings
from jobhunter.config.settings import SourceConfig
from jobhunter.filters import FilterChain
from jobhunter.models import Job, SearchCriteria
from jobhunter.ranking import JobRanker
from jobhunter.resume import ResumeError, ResumePromptBuilder, ResumeReader, ResumeWriter
from jobhunter.services import JobHuntPipeline
from jobhunter.web import WebService, create_app
from jobhunter.web.sources import style_for
from test_resume import make_pdf

CRITERIA = SearchCriteria(keywords=["python"], top_n=2)


def make_job(n: int) -> Job:
    return Job(title=f"Dev Python {n}", company=f"Empresa {n}", url=f"https://x/{n}",
               description="Python\nDjango", source="gupy" if n % 2 else "jobicy",
               remote=True, location="Brasil", tags=("Júnior",),
               posted_at=datetime(2026, 11, 10 + n, tzinfo=timezone.utc))


JOBS = [make_job(n) for n in range(1, 5)]  # ranking por data: 4, 3, 2, 1


class FakeRunner:
    def __init__(self):
        self.errors, self.counts, self.failures = [], {}, {}

    def run(self, criteria):
        self.counts = {"gupy": 2, "jobicy": 2}
        self.failures = {"remotive": "[remotive] falha HTTP"}
        self.errors = ["[remotive] falha HTTP"]
        return list(JOBS)


@pytest.fixture
def settings(tmp_path):
    sources = [SourceConfig(name=n, type="api", url="https://x") for n in ("gupy", "jobicy", "remotive")]
    return Settings(criteria=CRITERIA, sources=sources, resume_path=tmp_path / "resume" / "cv.pdf",
                    output_dir=tmp_path / "out", db_path=tmp_path / "jobs.db")


def factory(settings, repo):
    """Pipeline real, só com o runner falso (sem internet)."""
    return JobHuntPipeline(
        settings=settings, runner=FakeRunner(), filters=FilterChain.from_criteria(CRITERIA),
        repository=repo, ranker=JobRanker.from_criteria(CRITERIA), reader=ResumeReader(),
        prompt_builder=ResumePromptBuilder(), writer=ResumeWriter(settings.output_dir),
    )


@pytest.fixture
def service(settings):
    return WebService(settings, pipeline_factory=factory)


@pytest.fixture
def client(service):
    app = create_app(service)
    app.testing = True
    return app.test_client()


def pdf_bytes(tmp_path, text="Fulano - Python"):
    path = tmp_path / "upload.pdf"
    make_pdf(path, text)
    return path.read_bytes()


# --- WebService --------------------------------------------------------------

def test_search_splits_top_and_others_and_tracks_sources(service):
    service.search()
    assert [j.url for j in service.top] == ["https://x/4", "https://x/3"]
    assert [j.url for j in service.others] == ["https://x/2", "https://x/1"]
    status = {s.name: (s.count, s.error) for s in service.sources()}
    assert status == {"gupy": (2, None), "jobicy": (2, None),
                      "remotive": (None, "[remotive] falha HTTP")}


def test_sources_before_first_search(service):
    assert all(s.count is None and s.error is None for s in service.sources())
    assert service.top == [] and service.others == [] and service.job("x") is None


def test_top_prompts_are_written_and_saved_to_memory(service, settings):
    service.search()
    batch = service.create_top_prompts()
    assert [p.name[:3] for p in batch.files] == ["01_", "02_"] and batch.saved == 2
    assert service.prompted == {JOBS[3].uid, JOBS[2].uid}
    service.search()  # vagas do top já estão na memória
    assert [j.url for j in service.top] == ["https://x/2", "https://x/1"]


def test_single_prompt_uses_job_rank(service):
    service.search()
    batch = service.create_prompt(JOBS[0].uid)  # 4ª no ranking
    assert batch.files[0].name.startswith("04_")
    with pytest.raises(KeyError):
        service.create_prompt("nao-existe")


def test_save_resume_validates_and_keeps_old_on_error(service, settings, tmp_path):
    service.save_resume(pdf_bytes(tmp_path), "meu cv.PDF")
    assert service.resume_exists()
    original = settings.resume_path.read_bytes()
    for data, name in [(b"nao e pdf", "cv.pdf"), (b"", "cv.pdf"), (pdf_bytes(tmp_path), "cv.docx")]:
        with pytest.raises(ResumeError):
            service.save_resume(data, name)
    assert settings.resume_path.read_bytes() == original
    assert list(settings.resume_path.parent.iterdir()) == [settings.resume_path]  # sem temporários


def test_prompts_list_and_safe_read(service, settings):
    service.search()
    service.create_top_prompts()
    names = [p.name for p in service.list_prompts()]
    assert len(names) == 2
    assert "NUNCA invente" in service.read_prompt(names[0])
    (settings.output_dir.parent / "segredo.txt").write_text("x")
    for bad in ("../segredo.txt", "nada.txt", "01_x.md"):
        with pytest.raises(FileNotFoundError):
            service.read_prompt(bad)


def test_style_for_unknown_source():
    assert style_for("gupy").label == "Gupy"
    assert style_for("nova").initials == "NO"


# --- Rotas -------------------------------------------------------------------

def test_index_before_search(client):
    html = client.get("/").get_data(as_text=True)
    assert "Nenhuma busca ainda" in html and "Sem currículo" in html and "Gupy" in html


def test_search_route_then_index_shows_lists(client):
    data = client.post("/api/search").get_json()
    assert data == {"collected": 4, "new": 4, "top": 2, "errors": ["[remotive] falha HTTP"]}
    html = client.get("/").get_data(as_text=True)
    assert "Top 2" in html and "Outras vagas (2)" in html and "Gerar prompt" in html
    assert "https://x/4" in html and "falhou" in html


def test_job_detail_route(client):
    client.post("/api/search")
    job = client.get(f"/api/jobs/{JOBS[3].uid}").get_json()
    assert job["title"] == "Dev Python 4" and job["rank"] == 1 and job["in_top"] is True
    assert job["source"]["label"] == "Jobicy" and job["description"] == "Python\nDjango"
    assert job["posted_at"] == "14/11/2026" and job["tags"] == ["Júnior"]
    assert client.get("/api/jobs/nao-existe").status_code == 404


def test_prompt_routes_and_copy(client):
    assert client.post("/api/prompts/top").status_code == 400  # sem busca
    client.post("/api/search")
    top = client.post("/api/prompts/top").get_json()
    assert len(top["files"]) == 2 and top["saved"] == 2
    assert "anexado" in client.get(f"/api/prompts/{top['files'][0]}").get_data(as_text=True)
    one = client.post(f"/api/prompts/job/{JOBS[0].uid}").get_json()
    assert one["files"][0].startswith("04_")
    assert client.post("/api/prompts/job/nao-existe").status_code == 404
    assert client.get("/api/prompts/nada.txt").status_code == 404
    html = client.get("/").get_data(as_text=True)
    assert "Prompts criados (3)" in html and "prompt criado" in html


def test_resume_upload_route(client, tmp_path):
    ok = client.post("/api/resume", data={"file": (io.BytesIO(pdf_bytes(tmp_path)), "cv.pdf")},
                     content_type="multipart/form-data")
    assert ok.status_code == 200
    assert "Currículo anexado" in client.get("/").get_data(as_text=True)
    bad = client.post("/api/resume", data={"file": (io.BytesIO(b"x"), "cv.pdf")},
                      content_type="multipart/form-data")
    assert bad.status_code == 400 and bad.get_json()["error"]
    assert client.post("/api/resume").status_code == 400


def test_upload_too_large(client, service):
    client.application.config["MAX_CONTENT_LENGTH"] = 10
    resp = client.post("/api/resume", data={"file": (io.BytesIO(b"x" * 100), "cv.pdf")},
                       content_type="multipart/form-data")
    assert resp.status_code == 413


def test_post_from_other_site_is_blocked(client):
    assert client.post("/api/search", headers={"Origin": "https://malicioso.com"}).status_code == 403
    assert client.post("/api/search", headers={"Origin": "http://localhost"}).status_code == 200
