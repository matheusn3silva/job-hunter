"""Linha de comando do JobHunter: ``jobhunter [--dry-run] [--top N]``."""

from __future__ import annotations

import argparse
import logging
from dataclasses import replace
from pathlib import Path

from jobhunter.config import ConfigError, Settings
from jobhunter.services import JobHuntPipeline, PipelineResult
from jobhunter.storage import JobRepository, StorageError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jobhunter",
        description="Busca vagas, ranqueia pelo seu perfil e gera prompts de currículo para as melhores.",
    )
    parser.add_argument("--config-dir", type=Path, default=Path("config"),
                        help="pasta com settings.yaml e sources.yaml (padrão: config)")
    parser.add_argument("--dry-run", action="store_true",
                        help="só lista o ranking: não gera prompts nem grava na memória")
    parser.add_argument("--top", type=int, metavar="N", help="quantas vagas no top (sobrepõe top_n)")
    parser.add_argument("-v", "--verbose", action="store_true", help="mostra logs detalhados")
    return parser


def load_settings(config_dir: Path, top: int | None = None) -> Settings:
    """Carrega a configuração e resolve caminhos relativos à raiz do projeto.

    A raiz é a pasta acima de ``config_dir``; assim ``data/jobs.db`` funciona
    mesmo rodando o comando a partir de outra pasta.
    """
    settings = Settings.load(config_dir / "settings.yaml", config_dir / "sources.yaml")
    root = config_dir.resolve().parent

    def resolve(path: Path) -> Path:
        return path if path.is_absolute() else root / path

    criteria = settings.criteria
    if top is not None:
        if top < 1:
            raise ConfigError("--top deve ser pelo menos 1")
        criteria = replace(criteria, top_n=top)
    return replace(
        settings,
        criteria=criteria,
        resume_path=resolve(settings.resume_path),
        output_dir=resolve(settings.output_dir),
        db_path=resolve(settings.db_path),
    )


def format_report(result: PipelineResult, dry_run: bool) -> str:
    """Texto do relatório final mostrado no terminal."""
    lines = [
        f"Coletadas: {result.collected} | Aprovadas nos filtros: {result.approved} "
        f"| Novas: {result.new}",
    ]
    if result.rejected:
        cuts = ", ".join(f"{name}: {n}" for name, n in sorted(result.rejected.items()))
        lines.append(f"Descartadas por filtro: {cuts}")
    if not result.top:
        lines.append("Nenhuma vaga nova para mostrar.")
    else:
        lines.append("")
        lines.append(f"Top {len(result.top)}:")
        for pos, job in enumerate(result.top, start=1):
            where = "remota" if job.remote else (job.location or "local não informado")
            lines.append(f"{pos:>2}. [{job.score:4.1f}] {job.title} | {job.company} | {where}")
            lines.append(f"     {job.url}")
    if result.files:
        lines.append("")
        lines.append(f"Prompts de currículo gerados ({len(result.files)}) — cole numa IA de chat gratuita:")
        lines.extend(f"  {path}" for path in result.files)
    if dry_run:
        lines.append("")
        lines.append("Modo --dry-run: nenhum prompt gerado e nada salvo na memória.")
    elif result.top:
        lines.append(f"Vagas salvas na memória: {result.saved}")
    if result.errors:
        lines.append("")
        lines.append(f"Avisos ({len(result.errors)}):")
        lines.extend(f"  - {error}" for error in result.errors)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada do comando ``jobhunter``. Devolve o código de saída."""
    args = build_parser().parse_args(argv)
    # Sem -v, avisos aparecem só no relatório final (evita mensagens duplicadas).
    logging.basicConfig(level=logging.INFO if args.verbose else logging.ERROR,
                        format="%(levelname)s %(name)s: %(message)s")
    try:
        settings = load_settings(args.config_dir, args.top)
        with JobRepository(settings.db_path) as repository:
            result = JobHuntPipeline.from_settings(settings, repository).run(dry_run=args.dry_run)
    except (ConfigError, StorageError) as exc:
        print(f"Erro: {exc}")
        return 1
    print(format_report(result, args.dry_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
