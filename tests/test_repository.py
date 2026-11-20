import pytest

from jobhunter.models import Job
from jobhunter.storage import JobRepository, StorageError


def make_job(n: int, **overrides) -> Job:
    base = dict(title=f"Dev {n}", company="Acme", url=f"https://x/{n}",
                description="d", source="teste")
    return Job(**{**base, **overrides})


@pytest.fixture
def repo():
    with JobRepository(":memory:") as r:
        yield r


def test_new_repository_is_empty(repo):
    assert repo.count() == 0
    assert not repo.has_seen(make_job(1).uid)


def test_mark_seen_and_has_seen(repo):
    assert repo.mark_seen([make_job(1, score=7.5)]) == 1
    assert repo.has_seen(make_job(1).uid)
    assert repo.count() == 1


def test_marking_twice_does_not_duplicate(repo):
    repo.mark_seen([make_job(1)])
    assert repo.mark_seen([make_job(1), make_job(2)]) == 1
    assert repo.count() == 2


def test_filter_unseen_keeps_order_and_drops_seen(repo):
    repo.mark_seen([make_job(2)])
    jobs = [make_job(3), make_job(2), make_job(1)]
    assert repo.filter_unseen(jobs) == [make_job(3), make_job(1)]


def test_filter_unseen_handles_more_than_one_chunk(repo):
    jobs = [make_job(n) for n in range(1200)]
    repo.mark_seen(jobs[::2])
    assert repo.filter_unseen(jobs) == jobs[1::2]


def test_empty_lists(repo):
    assert repo.filter_unseen([]) == []
    assert repo.mark_seen([]) == 0


def test_memory_persists_between_runs(tmp_path):
    db = tmp_path / "jobs.db"
    with JobRepository(db) as first_run:
        first_run.mark_seen([make_job(1)])
    with JobRepository(db) as second_run:
        assert second_run.has_seen(make_job(1).uid)
        assert second_run.filter_unseen([make_job(1), make_job(2)]) == [make_job(2)]


def test_creates_missing_parent_folder(tmp_path):
    db = tmp_path / "nova" / "pasta" / "jobs.db"
    with JobRepository(db):
        pass
    assert db.exists()


def test_invalid_path_raises_storage_error(tmp_path):
    blocker = tmp_path / "arquivo"
    blocker.write_text("não é pasta")
    with pytest.raises(StorageError):
        JobRepository(blocker / "jobs.db")


def test_closed_repository_raises_storage_error():
    repo = JobRepository(":memory:")
    repo.close()
    with pytest.raises(StorageError):
        repo.count()
