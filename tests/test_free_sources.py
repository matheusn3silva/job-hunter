import pytest

from jobhunter.config.settings import SourceConfig
from jobhunter.models import Job, SearchCriteria
from jobhunter.scrapers import (
    GitHubVagasScraper,
    JobicyScraper,
    ScraperError,
    ScraperFactory,
    WeWorkRemotelyScraper,
)

CRITERIA = SearchCriteria(keywords=["python"])


# --- GitHub (issues como vagas) ----------------------------------------------

GH = SourceConfig(name="github-backendbr", type="api",
                  url="https://api.github.com/repos/backend-br/vagas/issues")


def issue(title, labels=(), **extra):
    return {"title": title, "html_url": f"https://github.com/x/{abs(hash(title))}",
            "body": "Vaga com Python", "created_at": "2026-11-18T22:39:26Z",
            "labels": [{"name": n} for n in labels], **extra}


def test_github_remote_issue(make_client):
    payload = [issue("[Remoto] Desenvolvedor Back-end Júnior - MKdigital", ["Júnior", "Python", "Remoto"])]
    client = make_client(payload)
    [job] = GitHubVagasScraper(GH, client).fetch(CRITERIA)
    assert job.title == "Desenvolvedor Back-end Júnior - MKdigital"
    assert job.company == "MKdigital"
    assert job.remote is True and job.location == "Brasil"
    assert "Júnior" in job.tags and job.posted_at is not None
    params = client.requests[0].url.params
    assert params["state"] == "open" and params["per_page"] == "100"


@pytest.mark.parametrize("title, company, location, remote", [
    ("Product Engineer na JotPsych", "JotPsych", "", False),
    ("[Joinville/SC] Back-end Developer (Node.js)", "", "Joinville/SC", False),
    ("[Híbrido] Sr Software Engineer - Stealth", "Stealth", "", False),
])
def test_github_title_parsing(make_client, title, company, location, remote):
    [job] = GitHubVagasScraper(GH, make_client([issue(title)])).fetch(CRITERIA)
    assert (job.company, job.location, job.remote) == (company, location, remote)


def test_github_skips_pull_requests_and_broken_items(make_client):
    payload = [issue("PR", pull_request={}), {"title": "sem link"}, issue("[Remoto] Dev Python")]
    assert len(GitHubVagasScraper(GH, make_client(payload)).fetch(CRITERIA)) == 1


def test_github_rate_limit_becomes_scraper_error(make_client):
    with pytest.raises(ScraperError):
        GitHubVagasScraper(GH, make_client({"message": "rate limit"}, status=403)).fetch(CRITERIA)


# --- Jobicy --------------------------------------------------------------------

JOBICY = SourceConfig(name="jobicy", type="api", url="https://jobicy.com/api/v2/remote-jobs")


def test_jobicy_parses_and_makes_one_request(make_client):
    payload = {"jobs": [
        {"jobTitle": "Python Developer", "url": "https://jobicy.com/jobs/1", "companyName": "Foo",
         "jobGeo": "Brazil", "jobLevel": "Junior", "jobDescription": "<p>Django</p>",
         "pubDate": "2026-11-20T17:24:44+00:00"},
        {"jobTitle": "Sem nível", "url": "https://jobicy.com/jobs/2", "jobLevel": "Any"},
        {"jobTitle": "Sem link"},
    ]}
    client = make_client(payload)
    first, second = JobicyScraper(JOBICY, client).fetch(CRITERIA)
    assert (first.title, first.company, first.location, first.remote) == \
        ("Python Developer", "Foo", "Brazil", True)
    assert first.description == "Django" and first.tags == ("Junior",)
    assert second.tags == ()
    assert len(client.requests) == 1 and client.requests[0].url.params["geo"] == "brazil"


# --- We Work Remotely (RSS) ------------------------------------------------------

WWR = SourceConfig(name="weworkremotely", type="rss",
                   url="https://weworkremotely.com/categories/remote-programming-jobs.rss")
RSS = """<?xml version="1.0"?><rss><channel>
<item><title>Knock: Front End Developer</title><region>Anywhere in the World</region>
<category>Front-End Programming</category><description>&lt;p&gt;React&lt;/p&gt;</description>
<pubDate>Sun, 01 Nov 2026 07:31:04 +0000</pubDate><link>https://weworkremotely.com/remote-jobs/1</link></item>
<item><title>Sem empresa</title><region>USA Only</region><link>https://weworkremotely.com/remote-jobs/2</link></item>
<item><title>Sem link</title></item>
</channel></rss>"""


def test_wwr_parses_rss(make_client):
    first, second = WeWorkRemotelyScraper(WWR, make_client(RSS)).fetch(CRITERIA)
    assert (first.company, first.title, first.location) == ("Knock", "Front End Developer",
                                                           "Anywhere in the World")
    assert first.description == "React" and first.posted_at.year == 2026
    assert first.tags == ("Front-End Programming",)
    assert (second.company, second.title, second.location) == ("", "Sem empresa", "USA Only")


def test_wwr_invalid_xml_becomes_scraper_error(make_client):
    with pytest.raises(ScraperError):
        WeWorkRemotelyScraper(WWR, make_client("isto não é xml <")).fetch(CRITERIA)


# --- Registro e nível pelas tags ---------------------------------------------

@pytest.mark.parametrize("name, cls", [
    ("jobicy", "JobicyScraper"), ("weworkremotely", "WeWorkRemotelyScraper"),
    ("github-frontendbr", "GitHubVagasScraper"), ("github-backendbr", "GitHubVagasScraper"),
])
def test_factory_knows_free_sources(name, cls):
    source = SourceConfig(name=name, type="api", url="https://x")
    assert type(ScraperFactory.create(source)).__name__ == cls


def test_level_from_tags_is_used_by_filters_and_internship():
    from jobhunter.filters import ExcludedKeywordFilter, SeniorityFilter

    senior = Job(title="Product Engineer", company="A", url="u", description="", source="s",
                 tags=("Sênior", "Remoto"))
    criteria = SearchCriteria(seniority=["júnior"], excluded_keywords=["sênior"])
    assert not SeniorityFilter(criteria).accepts(senior)
    assert not ExcludedKeywordFilter(criteria).accepts(senior)
    intern = Job(title="Dev", company="A", url="u", description="", source="s", tags=("Estágio",))
    assert intern.is_internship
