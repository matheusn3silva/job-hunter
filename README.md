# JobHunter

Busca vagas de desenvolvedor (Java, JavaScript, Python), ranqueia pelo seu
perfil, adapta seu currículo para as 10 melhores e lembra das vagas já vistas.

## Pipeline
Scrapers → Filtros → Remover já vistas → Ranking → Top N → Adaptar currículo → Salvar memória

## Instalação (desenvolvimento)
    python -m venv .venv && source .venv/bin/activate
    pip install -e ".[dev]"
    pytest

## Configuração
- `config/settings.yaml`: seus critérios (stack, senioridade, salário, local).
  - `min_salary`: mínimo para júnior/pleno. `min_salary_internship`: mínimo para estágio.
  - `accept_unknown_salary`: aceita vagas sem salário divulgado.
- `config/sources.yaml`: fontes de vagas (`enabled: false` desliga uma fonte).
- Coloque seu currículo em `data/resume/curriculo.pdf`.

## Módulos
| Módulo | Papel |
|---|---|
| `models.Job` | Vaga imutável; `uid` evita repetição entre execuções |
| `models.SearchCriteria` | Seus filtros, normalizados em minúsculas |
| `config.Settings` | Lê e valida os YAMLs; `ConfigError` com mensagem clara |

## Fluxo de trabalho com git
Cada parte do projeto = uma branch `parte-N-nome` e um commit/merge ao final.