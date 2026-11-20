from datetime import datetime, timedelta, timezone

import pytest

from jobhunter.models import Job, SearchCriteria
from jobhunter.ranking import (
    BaseScoreRule,
    JobRanker,
    KeywordScore,
    LocationScore,
    RecencyScore,
    SalaryScore,
    SeniorityScore,
)

NOW = datetime(2026, 11, 20, tzinfo=timezone.utc)
CRITERIA = SearchCriteria(keywords=["python", "django", "react", "java"],
                          seniority=["estágio", "júnior", "pleno"], locations=["São Paulo"], top_n=2)


def make_job(n: int = 1, **overrides) -> Job:
    base = dict(title="Desenvolvedor", company="Acme", url=f"https://x/{n}",
                description="", source="teste")
    return Job(**{**base, **overrides})


# --- Regras ------------------------------------------------------------------

def test_keyword_score_counts_hits_and_title_bonus():
    rule = KeywordScore(CRITERIA)
    assert rule.score(make_job(description="nada a ver")) == 0
    assert rule.score(make_job(description="python")) == 0.25
    assert rule.score(make_job(title="Dev Python", description="django")) == 0.75
    assert rule.score(make_job(title="Python Django", description="react java")) == 1.0


def test_seniority_score_prefers_explicit_level():
    rule = SeniorityScore(CRITERIA)
    assert rule.score(make_job(title="Dev Júnior")) == 1.0
    assert rule.score(make_job(title="Software Intern")) == 1.0
    assert rule.score(make_job(title="Desenvolvedor")) == 0.5


def test_location_score():
    rule = LocationScore(CRITERIA)
    assert rule.score(make_job(remote=True, location="Worldwide")) == 1.0
    assert rule.score(make_job(location="São Paulo, SP")) == 1.0
    assert rule.score(make_job(location="")) == 0.5


def test_salary_score():
    rule = SalaryScore(CRITERIA)
    assert rule.score(make_job(salary_min=3000)) == 1.0
    assert rule.score(make_job()) == 0.5


@pytest.mark.parametrize("days, expected", [(1, 1.0), (7, 1.0), (18.5, 0.5), (30, 0.0), (90, 0.0)])
def test_recency_score_decays(days, expected):
    rule = RecencyScore(CRITERIA, now=NOW)
    assert rule.score(make_job(posted_at=NOW - timedelta(days=days))) == pytest.approx(expected)


def test_recency_unknown_date():
    assert RecencyScore(CRITERIA, now=NOW).score(make_job()) == 0.5


def test_rules_without_criteria_are_neutral():
    empty = SearchCriteria()
    assert KeywordScore(empty).score(make_job()) == 0.5
    assert SeniorityScore(empty).score(make_job()) == 0.5


# --- JobRanker ---------------------------------------------------------------

class Fixed(BaseScoreRule):
    name = "fixed"

    def __init__(self, value: float, weight: float):
        super().__init__(SearchCriteria())
        self.value, self.weight = value, weight

    def score(self, job):
        return self.value


def test_score_is_weighted_average_scaled_to_ten():
    ranker = JobRanker([Fixed(1.0, weight=3), Fixed(0.0, weight=1)])
    assert ranker.score(make_job()) == 7.5


def test_rank_orders_best_first_and_fills_score():
    ranker = JobRanker.from_criteria(CRITERIA, now=NOW)
    weak = make_job(1, description="java")
    strong = make_job(2, title="Dev Python Júnior", description="django react", remote=True,
                      posted_at=NOW)
    ranked = ranker.rank([weak, strong])
    assert [j.url for j in ranked] == [strong.url, weak.url]
    assert ranked[0].score > ranked[1].score > 0
    assert weak.score == 0.0  # original não é alterado


def test_ties_prefer_most_recent():
    ranker = JobRanker([Fixed(1.0, weight=1)])
    old = make_job(1, posted_at=NOW - timedelta(days=10))
    new = make_job(2, posted_at=NOW)
    undated = make_job(3)
    assert [j.url for j in ranker.rank([old, undated, new])] == [new.url, old.url, undated.url]


def test_top_returns_top_n():
    ranker = JobRanker.from_criteria(CRITERIA, now=NOW)
    jobs = [make_job(n, description="python " * n) for n in range(5)]
    assert len(ranker.top(jobs)) == 2


def test_ranker_requires_rules():
    with pytest.raises(ValueError):
        JobRanker([])


def test_empty_input():
    assert JobRanker.from_criteria(CRITERIA).rank([]) == []
