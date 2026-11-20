import pytest

from jobhunter.config import ConfigError, Settings

SETTINGS = """
criteria:
  keywords: [python]
  min_salary: 3000
  min_salary_internship: 2000
paths:
  resume: data/resume/curriculo.pdf
  output: data/output
  database: data/jobs.db
"""

SOURCES = """
sources:
  - {name: a, type: html, url: "https://a.com"}
  - {name: b, type: rss, url: "https://b.com", enabled: false}
"""


@pytest.fixture
def files(tmp_path):
    s, src = tmp_path / "settings.yaml", tmp_path / "sources.yaml"
    s.write_text(SETTINGS, encoding="utf-8")
    src.write_text(SOURCES, encoding="utf-8")
    return s, src


def test_load_valid_config(files):
    settings = Settings.load(*files)
    assert settings.criteria.min_salary == 3000
    assert settings.criteria.min_salary_internship == 2000
    assert settings.db_path.name == "jobs.db"


def test_active_sources_filters_disabled(files):
    assert [s.name for s in Settings.load(*files).active_sources] == ["a"]


def test_missing_file_raises(tmp_path, files):
    with pytest.raises(ConfigError):
        Settings.load(tmp_path / "nope.yaml", files[1])


def test_missing_paths_raises(tmp_path, files):
    files[0].write_text("criteria: {}\n", encoding="utf-8")
    with pytest.raises(ConfigError):
        Settings.load(*files)


def test_invalid_source_type_raises(tmp_path, files):
    files[1].write_text('sources:\n  - {name: x, type: ftp, url: "u"}\n', encoding="utf-8")
    with pytest.raises(ConfigError):
        Settings.load(*files)


def test_unknown_criteria_field_raises(tmp_path, files):
    files[0].write_text(SETTINGS.replace("keywords", "palavras"), encoding="utf-8")
    with pytest.raises(ConfigError):
        Settings.load(*files)