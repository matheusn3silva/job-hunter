"""Site local do JobHunter (Flask): ``jobhunter-web`` abre em http://localhost:5000.

As rotas só traduzem HTTP ↔ ``WebService``; a lógica fica no serviço.
"""

from __future__ import annotations

import argparse
import threading
import webbrowser
from pathlib import Path
from urllib.parse import urlparse

from flask import Flask, abort, jsonify, render_template, request
from werkzeug.exceptions import RequestEntityTooLarge

from jobhunter.config import ConfigError
from jobhunter.main import default_config_dir, load_settings
from jobhunter.models import Job
from jobhunter.resume import ResumeError
from jobhunter.services import PromptBatch
from jobhunter.storage import StorageError
from jobhunter.web.service import WebService
from jobhunter.web.sources import style_for

MAX_UPLOAD_MB = 10


def create_app(service: WebService) -> Flask:
    """Cria o app Flask ligado a um ``WebService`` (os testes passam um falso)."""
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
    app.jinja_env.globals["style_for"] = style_for

    @app.before_request
    def block_other_sites():
        """Só aceita ações (POST) vindas do próprio site.

        Evita que uma página aberta em outra aba dispare buscas ou prompts
        aqui (ataque CSRF), já que o servidor roda na sua máquina.
        """
        origin = request.headers.get("Origin")
        if request.method == "POST" and origin and urlparse(origin).netloc != request.host:
            abort(403)

    @app.get("/")
    def index():
        return render_template(
            "index.html",
            result=service.last,
            top=service.top,
            others=service.others,
            sources=service.sources(),
            prompts=service.list_prompts(),
            prompted=service.prompted,
            resume_exists=service.resume_exists(),
            top_n=service.settings.criteria.top_n,
        )

    @app.post("/api/resume")
    def upload_resume():
        file = request.files.get("file")
        if file is None or not file.filename:
            return _error("Nenhum arquivo enviado.", 400)
        try:
            service.save_resume(file.read(), file.filename)
        except ResumeError as exc:
            return _error(str(exc), 400)
        return jsonify(message="Currículo salvo.")

    @app.post("/api/search")
    def search():
        try:
            result = service.search()
        except StorageError as exc:
            return _error(str(exc), 500)
        return jsonify(collected=result.collected, new=result.new, top=len(result.top),
                       errors=result.errors)

    @app.post("/api/prompts/top")
    def prompts_top():
        if not service.top:
            return _error("Faça uma busca antes de gerar os prompts.", 400)
        return _batch_response(service.create_top_prompts())

    @app.post("/api/prompts/job/<uid>")
    def prompt_for_job(uid: str):
        try:
            return _batch_response(service.create_prompt(uid))
        except KeyError:
            return _error("Vaga não encontrada; faça a busca de novo.", 404)

    @app.get("/api/prompts/<name>")
    def read_prompt(name: str):
        try:
            text = service.read_prompt(name)
        except FileNotFoundError:
            return _error("Prompt não encontrado.", 404)
        return text, 200, {"Content-Type": "text/plain; charset=utf-8"}

    @app.get("/api/jobs/<uid>")
    def job_detail(uid: str):
        job = service.job(uid)
        if job is None:
            return _error("Vaga não encontrada; faça a busca de novo.", 404)
        return jsonify(_job_json(job, service.rank_of(uid), uid in service.prompted,
                                 len(service.top)))

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(_exc):
        return _error(f"Arquivo maior que {MAX_UPLOAD_MB} MB.", 413)

    return app


def _error(message: str, status: int):
    return jsonify(error=message), status


def _batch_response(batch: PromptBatch):
    return jsonify(files=[p.name for p in batch.files], saved=batch.saved, errors=batch.errors)


def _job_json(job: Job, rank: int | None, prompted: bool, top_size: int) -> dict:
    """Dados da vaga para o painel de detalhes."""
    style = style_for(job.source)
    return {
        "uid": job.uid,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "remote": job.remote,
        "url": job.url,
        "description": job.description,
        "tags": list(job.tags),
        "score": job.score,
        "rank": rank,
        "in_top": rank is not None and rank <= top_size,
        "prompted": prompted,
        "posted_at": job.posted_at.strftime("%d/%m/%Y") if job.posted_at else None,
        "source": {"name": job.source, "label": style.label, "initials": style.initials,
                   "color": style.color},
    }


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada do comando ``jobhunter-web``."""
    parser = argparse.ArgumentParser(prog="jobhunter-web",
                                     description="Abre o site local do JobHunter.")
    parser.add_argument("--config-dir", type=Path, default=None,
                        help="pasta com settings.yaml e sources.yaml")
    parser.add_argument("--host", default="127.0.0.1",
                        help="endereço do servidor (padrão: só este computador)")
    parser.add_argument("--port", type=int, default=5000, help="porta (padrão: 5000)")
    parser.add_argument("--no-browser", action="store_true", help="não abre o navegador")
    args = parser.parse_args(argv)
    try:
        settings = load_settings(args.config_dir or default_config_dir())
    except ConfigError as exc:
        print(f"Erro: {exc}")
        return 1
    url = f"http://{'localhost' if args.host in ('127.0.0.1', '0.0.0.0') else args.host}:{args.port}"
    print(f"JobHunter aberto em {url}  (Ctrl+C para sair)")
    if not args.no_browser:
        threading.Timer(1.0, webbrowser.open, [url]).start()
    create_app(WebService(settings)).run(host=args.host, port=args.port, debug=False, threaded=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
