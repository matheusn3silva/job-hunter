from datetime import timezone

import pytest

from jobhunter.utils.text import contains_term, parse_datetime, strip_html


def test_strip_html():
    assert strip_html("<p>Olá <b>mundo</b></p><ul><li>Java</li><li>  SQL </li></ul>") == \
        "Olá mundo\nJava\nSQL"


def test_strip_html_keeps_line_breaks_and_collapses_spaces():
    assert strip_html("linha 1<br>linha   2<br><br><div> </div>fim") == "linha 1\nlinha 2\nfim"


def test_strip_html_handles_none():
    assert strip_html(None) == ""


def test_parse_datetime_with_z():
    assert parse_datetime("2026-11-10T12:00:00.000Z").tzinfo is not None


def test_parse_datetime_naive_becomes_utc():
    assert parse_datetime("2026-11-10T12:00:00").tzinfo == timezone.utc


def test_parse_datetime_invalid():
    assert parse_datetime("ontem") is None
    assert parse_datetime(None) is None

@pytest.mark.parametrize("text, term, expected", [
    ("Vaga Python e Django", "python", True),
    ("Dev JavaScript", "java", False),
    ("Projeto em ASP.NET", ".net", True),
    ("Node.js no backend", "node", True),
    ("Plano de seniority", "senior", False),
    ("Tech Lead de squad", "tech lead", True),
    ("qualquer coisa", "", False),
])
def test_contains_term(text, term, expected):
    assert contains_term(text, term) is expected


def test_parse_datetime_rss_format():
    parsed = parse_datetime("Sun, 01 Nov 2026 07:31:04 +0000")
    assert (parsed.year, parsed.month, parsed.day) == (2026, 11, 1) and parsed.tzinfo
