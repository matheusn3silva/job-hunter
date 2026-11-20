from jobhunter.scrapers.base import BaseScraper, ScraperError
from jobhunter.scrapers.factory import ScraperFactory
from jobhunter.scrapers.github import GitHubVagasScraper
from jobhunter.scrapers.gupy import GupyScraper
from jobhunter.scrapers.jobicy import JobicyScraper
from jobhunter.scrapers.remotive import RemotiveScraper
from jobhunter.scrapers.runner import ScraperRunner
from jobhunter.scrapers.weworkremotely import WeWorkRemotelyScraper

__all__ = ["BaseScraper", "ScraperError", "ScraperFactory", "GitHubVagasScraper",
           "GupyScraper", "JobicyScraper", "RemotiveScraper", "ScraperRunner",
           "WeWorkRemotelyScraper"]
