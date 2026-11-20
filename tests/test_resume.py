from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from jobhunter.models import Job
from jobhunter.resume import ResumeError, ResumeReader, ResumeTailor, ResumeWriter
from jobhunter.resume.writer import slugify

JOB = Job(title="Desenvolvedor Python Júnior", company="Açaí Tech", url="https://x/1",
          description="Django e APIs REST", source="teste", location="São Paulo", score=8.5)


def make_pdf(path, text: str | None) -> None:
    """Cria um PDF mínimo de uma página (com ou sem texto) para os testes."""
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode() if text else b""
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for n, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % n + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    path.write_bytes(bytes(out))


# --- ResumeReader ------------------------------------------------------------

def test_reads_pdf_text(tmp_path):
    pdf = tmp_path / "cv.pdf"
    make_pdf(pdf, "Fulano Dev Python")
    assert "Fulano Dev Python" in ResumeReader().read(pdf)


def test_missing_file(tmp_path):
    with pytest.raises(ResumeError, match="não encontrado"):
        ResumeReader().read(tmp_path / "nada.pdf")


def test_invalid_pdf(tmp_path):
    fake = tmp_path / "cv.pdf"
    fake.write_text("isto não é um pdf")
    with pytest.raises(ResumeError):
        ResumeReader().read(fake)


def test_pdf_without_text(tmp_path):
    pdf = tmp_path / "scan.pdf"
    make_pdf(pdf, None)
    with pytest.raises(ResumeError, match="escaneado"):
        ResumeReader().read(pdf)


# --- ResumeTailor ------------------------------------------------------------

class FakeClient:
    """Imita ``anthropic.Anthropic``: guarda a chamada e devolve uma resposta pronta."""

    def __init__(self, response=None, error=None):
        self.calls = []
        self._response, self._error = response, error
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        return self._response


def reply(*texts, stop_reason="end_turn"):
    blocks = [SimpleNamespace(type="thinking", thinking="")]
    blocks += [SimpleNamespace(type="text", text=t) for t in texts]
    return SimpleNamespace(content=blocks, stop_reason=stop_reason)


def test_tailor_sends_resume_and_job_and_returns_text():
    client = FakeClient(reply("# Fulano\n", "Dev Python"))
    result = ResumeTailor(client).tailor("Fulano - Python, Django", JOB)
    assert result == "# Fulano\nDev Python"
    call = client.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert "NUNCA invente" in call["system"]
    resume_block, job_block = call["messages"][0]["content"]
    assert "Python, Django" in resume_block["text"]
    assert resume_block["cache_control"] == {"type": "ephemeral"}
    assert "Django e APIs REST" in job_block["text"] and "Açaí Tech" in job_block["text"]
    assert call["fallbacks"] == "default"


def test_refusal_raises():
    with pytest.raises(ResumeError, match="recusou"):
        ResumeTailor(FakeClient(reply("", stop_reason="refusal"))).tailor("cv", JOB)


def test_empty_answer_raises():
    with pytest.raises(ResumeError, match="vazia"):
        ResumeTailor(FakeClient(reply("   "))).tailor("cv", JOB)


def _status_error(cls, status):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("erro", response=httpx2.Response(status, request=request), body=None)


@pytest.mark.parametrize("error, message", [
    (_status_error(anthropic.AuthenticationError, 401), "ANTHROPIC_API_KEY"),
    (_status_error(anthropic.RateLimitError, 429), "Limite"),
    (_status_error(anthropic.InternalServerError, 500), "500"),
    (anthropic.APIConnectionError(request=httpx2.Request("POST", "https://x")), "conexão"),
])
def test_api_errors_become_resume_error(error, message):
    with pytest.raises(ResumeError, match=message):
        ResumeTailor(FakeClient(error=error)).tailor("cv", JOB)


# --- ResumeWriter ------------------------------------------------------------

def test_slugify():
    assert slugify("Açaí Tech S/A") == "acai-tech-s-a"
    assert slugify("!!!") == "vaga"
    assert len(slugify("x" * 100)) <= 40


def test_writer_saves_markdown_with_job_header(tmp_path):
    out = tmp_path / "saida"
    path = ResumeWriter(out).write(JOB, "# Fulano\n")
    assert path.parent == out
    assert path.name == f"acai-tech_desenvolvedor-python-junior_{JOB.uid}.md"
    content = path.read_text(encoding="utf-8")
    assert "https://x/1" in content and content.endswith("# Fulano\n")


def test_writer_error(tmp_path):
    blocker = tmp_path / "arquivo"
    blocker.write_text("x")
    with pytest.raises(ResumeError):
        ResumeWriter(blocker / "sub").write(JOB, "cv")
