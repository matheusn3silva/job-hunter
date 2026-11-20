"""Memória das vagas já vistas, guardada em SQLite."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from jobhunter.models import Job

# Limite seguro de parâmetros por consulta ("?" em um IN) no SQLite.
_CHUNK_SIZE = 500

_SCHEMA = """
CREATE TABLE IF NOT EXISTS seen_jobs (
    uid      TEXT PRIMARY KEY,
    title    TEXT NOT NULL,
    company  TEXT NOT NULL,
    url      TEXT NOT NULL,
    source   TEXT NOT NULL,
    score    REAL NOT NULL,
    seen_at  TEXT NOT NULL
)
"""


class StorageError(RuntimeError):
    """Falha ao ler ou gravar a memória de vagas (arquivo, permissão, SQL)."""


class JobRepository:
    """Guarda as vagas já processadas para não repeti-las em outras execuções.

    Padrão Repository: todo o SQL fica aqui. O resto do sistema só chama
    ``filter_unseen`` e ``mark_seen``, sem saber que existe um banco.

    A chave é ``Job.uid`` (empresa + título + URL), a mesma usada para remover
    duplicatas entre fontes. O repositório não decide QUAIS vagas marcar:
    quem chama decide (a ideia é marcar só as top N que receberam currículo).

    Uso::

        with JobRepository("data/jobs.db") as repo:
            novas = repo.filter_unseen(vagas)
            ...
            repo.mark_seen(top_n)

    Args:
        db_path: caminho do arquivo SQLite (a pasta é criada se faltar) ou
            ``":memory:"`` para um banco temporário, útil em testes.

    Raises:
        StorageError: se o banco não puder ser aberto ou criado.
    """

    def __init__(self, db_path: str | Path):
        try:
            if str(db_path) != ":memory:":
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(db_path))
            with self._conn:
                self._conn.execute(_SCHEMA)
        except (OSError, sqlite3.Error) as exc:
            raise StorageError(f"Não foi possível abrir a memória em '{db_path}': {exc}") from exc

    def has_seen(self, uid: str) -> bool:
        """True se a vaga com esse ``uid`` já foi processada."""
        row = self._query("SELECT 1 FROM seen_jobs WHERE uid = ?", (uid,)).fetchone()
        return row is not None

    def filter_unseen(self, jobs: Iterable[Job]) -> list[Job]:
        """Devolve só as vagas novas, mantendo a ordem recebida."""
        jobs = list(jobs)
        seen = self._seen_uids([job.uid for job in jobs])
        return [job for job in jobs if job.uid not in seen]

    def mark_seen(self, jobs: Iterable[Job]) -> int:
        """Grava as vagas como vistas. Vagas já gravadas são ignoradas.

        Returns:
            Quantas vagas novas foram gravadas.
        """
        now = datetime.now(timezone.utc).isoformat()
        rows = [(j.uid, j.title, j.company, j.url, j.source, j.score, now) for j in jobs]
        try:
            with self._conn:  # transação: grava tudo ou nada
                cursor = self._conn.executemany(
                    "INSERT OR IGNORE INTO seen_jobs "
                    "(uid, title, company, url, source, score, seen_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    rows,
                )
        except sqlite3.Error as exc:
            raise StorageError(f"Falha ao gravar vagas na memória: {exc}") from exc
        return cursor.rowcount

    def count(self) -> int:
        """Quantas vagas estão na memória."""
        return self._query("SELECT COUNT(*) FROM seen_jobs").fetchone()[0]

    def close(self) -> None:
        """Fecha a conexão com o banco."""
        self._conn.close()

    def __enter__(self) -> JobRepository:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _seen_uids(self, uids: list[str]) -> set[str]:
        """Quais destes ``uids`` já estão gravados (consulta em blocos)."""
        found: set[str] = set()
        for start in range(0, len(uids), _CHUNK_SIZE):
            chunk = uids[start:start + _CHUNK_SIZE]
            marks = ", ".join("?" * len(chunk))
            rows = self._query(f"SELECT uid FROM seen_jobs WHERE uid IN ({marks})", chunk)
            found.update(uid for (uid,) in rows)
        return found

    def _query(self, sql: str, params: Iterable[object] = ()) -> sqlite3.Cursor:
        try:
            return self._conn.execute(sql, tuple(params))
        except sqlite3.Error as exc:
            raise StorageError(f"Falha ao consultar a memória: {exc}") from exc
