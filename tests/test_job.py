from dataclasses import FrozenInstanceError

import pytest

from jobhunter.models import Job


def make_job(**overrides) -> Job:
    base = dict(title="Dev Python", company="Acme", url="https://x.com/1",
                description="Trabalho com Python e Django", source="teste")
    return Job(**{**base, **overrides})


def test_uid_is_stable_and_ignores_case_and_spaces():
    assert make_job().uid == make_job(company=" ACME ", title="dev python").uid


def test_uid_differs_for_different_jobs():
    assert make_job().uid != make_job(url="https://x.com/2").uid


def test_job_is_immutable():
    with pytest.raises(FrozenInstanceError):
        make_job().title = "outro"


def test_with_score_returns_copy():
    job = make_job()
    scored = job.with_score(7.5)
    assert scored.score == 7.5 and job.score == 0.0


def test_searchable_text_is_lowercase_and_includes_tags():
    job = make_job(tags=("Backend",))
    assert "django" in job.searchable_text and "backend" in job.searchable_text


@pytest.mark.parametrize("title", ["Estágio em Java", "Estagiário Dev", "Software Intern"])
def test_is_internship_true(title):
    assert make_job(title=title).is_internship


def test_is_internship_false():
    assert not make_job(title="Desenvolvedor Júnior").is_internship