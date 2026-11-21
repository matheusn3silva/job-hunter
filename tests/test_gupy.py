import pytest

from jobhunter.config.settings import SourceConfig
from jobhunter.models import SearchCriteria
from jobhunter.scrapers import GupyScraper, ScraperError

SOURCE = SourceConfig(name="gupy", type="api", url="https://portal.gupy.io/api/job-search/jobs")
ITEM = {
    "id": 1, "name": "Desenvolvedor Python Júnior", "description": "<p>Django</p>",
    "careerPageName": "Acme", "city": "São Paulo", "state": "SP",
    "workplaceType": "remote", "publishedDate": "2026-11-10T12:00:00.000Z",
    "jobUrl": "https://acme.gupy.io/job/1", "type": "vacancy_type_effective",
}


def test_parses_job_fields(make_client):
    client = make_client({"data": [ITEM]})
    [job] = GupyScraper(SOURCE, client).fetch(SearchCriteria(keywords=["python"]))
    assert job.title == "Desenvolvedor Python Júnior"
    assert job.company == "Acme"
    assert job.description == "Django"
    assert job.location == "São Paulo, SP, Brasil"
    assert job.remote is True
    assert job.source == "gupy"
    assert job.posted_at is not None


def test_one_request_per_keyword_and_dedup(make_client):
    client = make_client({"data": [ITEM]})
    jobs = GupyScraper(SOURCE, client).fetch(SearchCriteria(keywords=["python", "java"]))
    assert len(client.requests) == 2
    assert len(jobs) == 1  # mesma vaga nas duas buscas
    params = client.requests[0].url.params
    assert (params["jobName"], params["limit"], params["offset"]) == ("python", "100", "0")


def test_skips_items_without_title_or_url(make_client):
    client = make_client({"data": [{"name": "Sem link"}, {"jobUrl": "x"}, ITEM]})
    assert len(GupyScraper(SOURCE, client).fetch(SearchCriteria(keywords=["python"]))) == 1


def test_http_error_becomes_scraper_error(make_client):
    with pytest.raises(ScraperError):
        GupyScraper(SOURCE, make_client({}, status=500)).fetch(SearchCriteria(keywords=["a"]))


def test_invalid_payload_becomes_scraper_error(make_client):
    with pytest.raises(ScraperError):
        GupyScraper(SOURCE, make_client(["lista"])).fetch(SearchCriteria(keywords=["a"]))