from jobhunter.config.settings import SourceConfig
from jobhunter.models import SearchCriteria
from jobhunter.scrapers import RemotiveScraper

SOURCE = SourceConfig(name="remotive", type="api", url="https://remotive.com/api/remote-jobs")
PAYLOAD = {"jobs": [{
    "id": 9, "url": "https://remotive.com/remote-jobs/software-dev/x-9",
    "title": "Backend Python", "company_name": "Foo", "category": "Software Development",
    "job_type": "internship", "publication_date": "2026-11-10T10:00:00",
    "candidate_required_location": "Worldwide", "description": "<p>Python</p>",
}]}


def test_parses_job_and_marks_remote(make_client):
    [job] = RemotiveScraper(SOURCE, make_client(PAYLOAD)).fetch(SearchCriteria())
    assert job.remote is True
    assert job.location == "Worldwide"
    assert job.description == "Python"
    assert "internship" in job.tags
    assert job.salary_min is None


def test_makes_a_single_request(make_client):
    client = make_client(PAYLOAD)
    RemotiveScraper(SOURCE, client).fetch(SearchCriteria(keywords=["a", "b", "c"]))
    assert len(client.requests) == 1
    assert client.requests[0].url.params["category"] == "software-dev"