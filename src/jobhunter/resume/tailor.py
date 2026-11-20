"""Adaptação do currículo para uma vaga usando a API da Anthropic (Claude)."""

from __future__ import annotations

from typing import Any

import anthropic

from jobhunter.models import Job
from jobhunter.resume.reader import ResumeError

MODEL = "claude-opus-5-5"
MAX_TOKENS = 16000
# Se o modelo recusar, o servidor tenta outro modelo automaticamente.
FALLBACK_BETA = "server-side-fallback-2026-07-01"

SYSTEM_PROMPT = """Você é um especialista em currículos para vagas de desenvolvimento de software.
Sua tarefa: adaptar o currículo do candidato para a vaga informada, aumentando a chance de ele ser chamado para entrevista.

Regras obrigatórias:
- NUNCA invente experiências, empregos, cargos, datas, projetos, formações, certificações ou habilidades. Use apenas o que está no currículo original.
- Você pode reordenar seções, reescrever frases, resumir e destacar o que já existe e é relevante para a vaga (tecnologias, responsabilidades, resultados).
- Use naturalmente as palavras-chave da vaga quando elas descreverem algo que o candidato realmente tem.
- Mantenha nome e contatos exatamente como no original.
- Escreva no mesmo idioma da descrição da vaga.
- Responda somente com o currículo em Markdown, sem comentários antes ou depois."""


class ResumeTailor:
    """Gera uma versão do currículo adaptada a uma vaga.

    O texto do currículo base vai num bloco com cache: nas várias chamadas
    de uma execução (uma por vaga), essa parte repetida sai mais barata.

    Args:
        client: cliente da Anthropic. Injetável para testes; se omitido, é
            criado na primeira chamada lendo ``ANTHROPIC_API_KEY`` (ou o
            login do ``ant auth login``).
        model: modelo usado.
    """

    def __init__(self, client: Any | None = None, model: str = MODEL):
        self._client = client
        self.model = model

    def tailor(self, resume_text: str, job: Job) -> str:
        """Devolve o currículo adaptado à vaga, em Markdown.

        Raises:
            ResumeError: sem credencial, erro da API, recusa ou resposta vazia.
        """
        try:
            response = self._get_client().beta.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                output_config={"effort": "high"},
                betas=[FALLBACK_BETA],
                fallbacks="default",
                system=SYSTEM_PROMPT,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": f"<curriculo>\n{resume_text}\n</curriculo>",
                         "cache_control": {"type": "ephemeral"}},
                        {"type": "text", "text": self._job_prompt(job)},
                    ],
                }],
            )
        except anthropic.AuthenticationError as exc:
            raise ResumeError("Chave da API da Anthropic inválida ou ausente "
                              "(defina ANTHROPIC_API_KEY).") from exc
        except anthropic.RateLimitError as exc:
            raise ResumeError("Limite de uso da API atingido; tente mais tarde.") from exc
        except anthropic.APIStatusError as exc:
            raise ResumeError(f"Erro da API ({exc.status_code}): {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise ResumeError("Sem conexão com a API da Anthropic.") from exc

        if response.stop_reason == "refusal":
            raise ResumeError(f"O modelo recusou adaptar o currículo para '{job.title}'.")
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        if not text:
            raise ResumeError(f"Resposta vazia ao adaptar o currículo para '{job.title}'.")
        return text

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                self._client = anthropic.Anthropic()
            except anthropic.AnthropicError as exc:
                raise ResumeError("Não foi possível criar o cliente da Anthropic "
                                  "(defina ANTHROPIC_API_KEY).") from exc
        return self._client

    @staticmethod
    def _job_prompt(job: Job) -> str:
        return (
            "Adapte o currículo acima para esta vaga:\n"
            f"<vaga>\nTítulo: {job.title}\nEmpresa: {job.company}\n"
            f"Local: {job.location or 'não informado'}{' (remota)' if job.remote else ''}\n"
            f"Descrição:\n{job.description}\n</vaga>"
        )
