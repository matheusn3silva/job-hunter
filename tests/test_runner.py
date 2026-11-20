import pytest

from jobhunter.config.settings import SourceConfig
from jobhunter.models import Job, SearchCriteria
from jobhunter.scrapers import BaseScraper, ScraperError, ScraperFactory, ScraperRunner

JOB = Job(title="Dev", company="Acme", url="https://x/1", description="d", source="a")


class OkScraper(BaseScraper):
    def _fetch(self, criteria):
        return [JOB]


class BrokenScraper(BaseScraper):
    def _fetch(self, criteria):
        raise ScraperError("quebrou")


def src(name):
    return SourceConfig(name=name, type="api", url="https://x")


def test_merges_and_deduplicates():
    runner = ScraperRunner([src("a"), src("b")], lambda s: OkScraper(s))
    assert len(runner.run(SearchCriteria())) == 1


def test_failing_source_does_not_stop_others():
    factory = lambda s: BrokenScraper(s) if s.name == "bad" else OkScraper(s)
    runner = ScraperRunner([src("bad"), src("good")], factory)
    assert len(runner.run(SearchCriteria())) == 1
    assert len(runner.errors) == 1


def test_factory_unknown_source_raises():
    with pytest.raises(ScraperError):
        ScraperFactory.create(src("inexistente"))


def test_factory_creates_registered_scrapers():
    assert type(ScraperFactory.create(src("gupy"))).__name__ == "GupyScraper"
    assert type(ScraperFactory.create(src("remotive"))).__name__ == "RemotiveScraper"