import pytest

from jobhunter.models import Job
from jobhunter.resume import ResumeError, ResumePromptBuilder, ResumeReader, ResumeWriter
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


# --- ResumePromptBuilder -----------------------------------------------------

def test_prompt_has_rules_job_and_resume():
    prompt = ResumePromptBuilder().build(JOB, "Fulano - Python, Django")
    assert "NUNCA invente" in prompt
    for expected in ("Desenvolvedor Python Júnior", "Açaí Tech", "https://x/1",
                     "Django e APIs REST", "Fulano - Python, Django"):
        assert expected in prompt
    assert prompt.index("=== VAGA ===") < prompt.index("=== MEU CURRÍCULO ===")


@pytest.mark.parametrize("resume", [None, "   "])
def test_prompt_without_resume_asks_to_attach(resume):
    assert "anexado a esta conversa" in ResumePromptBuilder().build(JOB, resume)


def test_prompt_marks_remote_and_missing_fields():
    job = Job(title="Dev", company="", url="https://x/2", description="", source="t", remote=True)
    prompt = ResumePromptBuilder().build(job, "cv")
    assert "(remota)" in prompt and "não informada" in prompt and "sem descrição" in prompt


# --- ResumeWriter ------------------------------------------------------------

def test_slugify():
    assert slugify("Açaí Tech S/A") == "acai-tech-s-a"
    assert slugify("!!!") == "vaga"
    assert len(slugify("x" * 100)) <= 40


def test_writer_saves_txt_named_by_rank(tmp_path):
    out = tmp_path / "saida"
    path = ResumeWriter(out).write(JOB, "prompt aqui\n\n", rank=3)
    assert path.parent == out
    assert path.name == f"03_acai-tech_desenvolvedor-python-junior_{JOB.uid}.txt"
    assert path.read_text(encoding="utf-8") == "prompt aqui\n"


def test_writer_error(tmp_path):
    blocker = tmp_path / "arquivo"
    blocker.write_text("x")
    with pytest.raises(ResumeError):
        ResumeWriter(blocker / "sub").write(JOB, "cv")
