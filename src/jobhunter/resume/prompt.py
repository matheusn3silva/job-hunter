"""Montagem do prompt para adaptar o currículo numa IA de chat gratuita."""

from __future__ import annotations

from jobhunter.models import Job

INSTRUCTIONS = """Você é um especialista em currículos para vagas de desenvolvimento de software.
Adapte o meu currículo para a vaga abaixo, para aumentar minha chance de ser chamado para entrevista.

Regras obrigatórias:
- NUNCA invente experiências, empregos, cargos, datas, projetos, formações, certificações ou habilidades. Use apenas o que está no meu currículo.
- Você pode reordenar seções, reescrever frases, resumir e destacar o que já existe e é relevante para a vaga (tecnologias, responsabilidades, resultados).
- Use naturalmente as palavras-chave da vaga quando elas descreverem algo que eu realmente tenho.
- Mantenha meu nome e contatos exatamente como estão.
- Escreva no mesmo idioma da descrição da vaga.

Responda em duas partes:
1. O currículo adaptado, pronto para copiar para um editor de texto.
2. Uma lista curta do que você mudou e dos requisitos da vaga que eu não tenho (sem inventar nada, só para eu saber)."""

MISSING_RESUME = ("[Meu currículo está anexado a esta conversa. Se não estiver, "
                  "peça para eu colar o texto do currículo antes de responder.]")


class ResumePromptBuilder:
    """Gera o texto que você cola numa IA de chat gratuita (ChatGPT, Gemini, Claude.ai).

    Custo zero: o JobHunter não chama nenhuma API paga. Cada prompt traz as
    regras (principalmente "não inventar nada"), os dados da vaga e o texto
    do seu currículo. Sem o texto do currículo, o prompt pede para você
    anexar o PDF na conversa.
    """

    def build(self, job: Job, resume_text: str | None = None) -> str:
        """Devolve o prompt completo para a vaga."""
        where = f"{job.location or 'não informado'}{' (remota)' if job.remote else ''}"
        resume = resume_text.strip() if resume_text and resume_text.strip() else MISSING_RESUME
        return (
            f"{INSTRUCTIONS}\n\n"
            f"=== VAGA ===\n"
            f"Título: {job.title}\n"
            f"Empresa: {job.company or 'não informada'}\n"
            f"Local: {where}\n"
            f"Link: {job.url}\n"
            f"Descrição:\n{job.description.strip() or '(sem descrição; veja o link)'}\n\n"
            f"=== MEU CURRÍCULO ===\n"
            f"{resume}\n"
        )
