from datetime import timezone

from jobhunter.utils.text import parse_datetime, strip_html


def test_strip_html():
    assert strip_html("<p>Olá <b>mundo</b></p><ul><li>Java</li></ul>") == "Olá mundo Java"


def test_strip_html_handles_none():
    assert strip_html(None) == ""


def test_parse_datetime_with_z():
    assert parse_datetime("2026-11-10T12:00:00.000Z").tzinfo is not None


def test_parse_datetime_naive_becomes_utc():
    assert parse_datetime("2026-11-10T12:00:00").tzinfo == timezone.utc


def test_parse_datetime_invalid():
    assert parse_datetime("ontem") is None
    assert parse_datetime(None) is None