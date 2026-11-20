import pytest

from jobhunter.models import SearchCriteria


def test_values_are_normalized():
    c = SearchCriteria(keywords=[" Python "], locations=["São Paulo"], seniority=["Júnior"])
    assert c.keywords == ["python"]
    assert c.locations == ["são paulo"]
    assert c.seniority == ["júnior"]


def test_top_n_must_be_positive():
    with pytest.raises(ValueError):
        SearchCriteria(top_n=0)


def test_negative_salary_rejected():
    with pytest.raises(ValueError):
        SearchCriteria(min_salary=-1)
    with pytest.raises(ValueError):
        SearchCriteria(min_salary_internship=-1)


def test_min_salary_for_picks_right_value():
    c = SearchCriteria(min_salary=3000, min_salary_internship=2000)
    assert c.min_salary_for(is_internship=True) == 2000
    assert c.min_salary_for(is_internship=False) == 3000

def test_remote_regions_have_defaults_and_are_normalized():
    assert "worldwide" in SearchCriteria().remote_regions
    assert SearchCriteria(remote_regions=[" LATAM "]).remote_regions == ["latam"]
