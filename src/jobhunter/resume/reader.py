"""Leitura do currículo base em PDF."""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError


class ResumeError(RuntimeError):
    """Falha ao ler o currículo ou salvar um prompt (mensagem amigável)."""


class ResumeReader:
    """Extrai o texto do currículo base (PDF).

    O texto extraído entra no prompt que você cola numa IA de chat. PDFs escaneados (só
    imagem) não têm texto; nesse caso é preciso exportar o currículo de
    novo a partir do editor (Word, Google Docs, Canva...).
    """

    def read(self, path: str | Path) -> str:
        """Devolve o texto do PDF, página por página.

        Raises:
            ResumeError: arquivo ausente, PDF inválido ou sem texto.
        """
        path = Path(path)
        if not path.is_file():
            raise ResumeError(f"Currículo não encontrado: {path}")
        try:
            pages = PdfReader(path).pages
            text = "\n\n".join((page.extract_text() or "").strip() for page in pages)
        except (PdfReadError, OSError, ValueError) as exc:
            raise ResumeError(f"Não foi possível ler o PDF '{path}': {exc}") from exc
        if not text.strip():
            raise ResumeError(
                f"O PDF '{path}' não tem texto (parece escaneado). "
                "Exporte o currículo como PDF a partir do editor de texto."
            )
        return text.strip()
