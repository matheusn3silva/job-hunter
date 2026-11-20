import pytest

from jobhunter.filters import (
    BaseFilter,
    ExcludedKeywordFilter,
    FilterChain,
    KeywordFilter,
    LocationFilter,
    SalaryFilter,
    SeniorityFilter,
)
from jobhunter.models import Job, SearchCriteria


def make_job(**overrides) -> Job:
    base = dict(title="Desenvolvedor Python Júnior", company="Acme", url="https://x/1",
                description="Trabalho com Django", source="teste", location="São Paulo, SP")
    return Job(**{**base, **overrides})


# --- KeywordFilter -----------------------------------------------------------

def test_keyword_accepts_when_any_keyword_matches():
    f = KeywordFilter(SearchCriteria(keywords=["java", "Django"]))
    assert f.accepts(make_job())


def test_keyword_rejects_without_match_and_uses_whole_words():
    f = KeywordFilter(SearchCriteria(keywords=["java"]))
    assert not f.accepts(make_job(title="Dev JavaScript", description="React"))


def test_keyword_without_criteria_accepts_all():
    assert KeywordFilter(SearchCriteria()).accepts(make_job())


def test_keyword_checks_tags():
    f = KeywordFilter(SearchCriteria(keywords=["spring"]))
    assert f.accepts(make_job(description="", tags=("Spring",)))


# --- ExcludedKeywordFilter ---------------------------------------------------

@pytest.mark.parametrize("text", ["Experiência com PHP", "Projeto em ASP.NET"])
def test_excluded_keyword_rejects(text):
    f = ExcludedKeywordFilter(SearchCriteria(excluded_keywords=["php", ".net"]))
    assert not f.accepts(make_job(description=text))


def test_excluded_keyword_ignores_partial_words():
    f = ExcludedKeywordFilter(SearchCriteria(excluded_keywords=["senior"]))
    assert f.accepts(make_job(description="Plano de seniority claro"))


# --- SeniorityFilter ---------------------------------------------------------

LEVELS = SearchCriteria(seniority=["estágio", "júnior", "pleno"])


@pytest.mark.parametrize("title", ["Dev Python Júnior", "Estágio em Java", "Software Intern",
                                   "Desenvolvedor Pleno"])
def test_seniority_accepts_wanted_levels(title):
    assert SeniorityFilter(LEVELS).accepts(make_job(title=title))


@pytest.mark.parametrize("title", ["Desenvolvedor Sênior", "Tech Lead Java", "Senior Engineer"])
def test_seniority_rejects_other_levels(title):
    assert not SeniorityFilter(LEVELS).accepts(make_job(title=title))


def test_seniority_keeps_jobs_without_level():
    assert SeniorityFilter(LEVELS).accepts(make_job(title="Desenvolvedor Python"))


def test_seniority_only_looks_at_title():
    job = make_job(title="Dev Júnior", description="Você terá mentoria de devs sênior")
    assert SeniorityFilter(LEVELS).accepts(job)


# --- LocationFilter ----------------------------------------------------------

CITY = SearchCriteria(locations=["São Paulo"])


@pytest.mark.parametrize("location", ["Worldwide", "LATAM", "Brazil", "", "Recife, PE, Brasil"])
def test_remote_accepts_allowed_regions(location):
    assert LocationFilter(CITY).accepts(make_job(remote=True, location=location))


@pytest.mark.parametrize("location", ["USA Only", "Europe", "Canada, UK"])
def test_remote_rejects_restricted_countries(location):
    assert not LocationFilter(CITY).accepts(make_job(remote=True, location=location))


def test_onsite_accepts_wanted_city_and_rejects_others():
    f = LocationFilter(CITY)
    assert f.accepts(make_job(location="São Paulo, SP"))
    assert not f.accepts(make_job(location="Curitiba, PR"))


def test_onsite_without_location_is_kept():
    assert LocationFilter(CITY).accepts(make_job(location=""))


def test_remote_only_rejects_onsite():
    f = LocationFilter(SearchCriteria(remote_only=True))
    assert not f.accepts(make_job(remote=False))
    assert f.accepts(make_job(remote=True, location="Worldwide"))


# --- SalaryFilter ------------------------------------------------------------

SALARY = SearchCriteria(min_salary=3000, min_salary_internship=2000)


def test_salary_uses_general_minimum():
    f = SalaryFilter(SALARY)
    assert f.accepts(make_job(salary_min=3000))
    assert not f.accepts(make_job(salary_min=2500))


def test_salary_uses_internship_minimum():
    f = SalaryFilter(SALARY)
    assert f.accepts(make_job(title="Estágio Python", salary_min=2000))
    assert not f.accepts(make_job(title="Estágio Python", salary_min=1500))


def test_salary_uses_top_of_range():
    assert SalaryFilter(SALARY).accepts(make_job(salary_min=2500, salary_max=3500))


def test_unknown_salary_follows_config():
    assert SalaryFilter(SALARY).accepts(make_job())
    strict = SearchCriteria(min_salary=3000, accept_unknown_salary=False)
    assert not SalaryFilter(strict).accepts(make_job())


def test_salary_without_minimum_accepts():
    assert SalaryFilter(SearchCriteria()).accepts(make_job(salary_min=100))


# --- FilterChain -------------------------------------------------------------

class RejectAll(BaseFilter):
    name = "reject_all"

    def accepts(self, job):
        return False


def test_chain_keeps_only_jobs_approved_by_all_filters():
    criteria = SearchCriteria(keywords=["python"], excluded_keywords=["php"],
                              seniority=["júnior"], locations=["são paulo"], min_salary=3000)
    good = make_job()
    jobs = [good, make_job(url="https://x/2", description="Python e PHP"),
            make_job(url="https://x/3", title="Python Sênior"),
            make_job(url="https://x/4", salary_min=1000)]
    chain = FilterChain.from_criteria(criteria)
    assert chain.apply(jobs) == [good]
    assert chain.rejected == {"excluded_keywords": 1, "seniority": 1, "salary": 1}


def test_chain_counts_rejections_per_filter_and_resets():
    chain = FilterChain([RejectAll(SearchCriteria())])
    assert chain.apply([make_job(), make_job(url="https://x/2")]) == []
    assert chain.rejected["reject_all"] == 2
    chain.apply([])
    assert chain.rejected == {}


def test_empty_chain_accepts_everything():
    assert FilterChain([]).apply([make_job()]) == [make_job()]
