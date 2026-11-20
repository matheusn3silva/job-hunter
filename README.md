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
  - `remote_regions`: regiões aceitas em vagas remotas (Worldwide, LATAM, Brazil...).
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

## Scrapers (Parte 2)
Cada fonte é uma classe que herda de `BaseScraper` e implementa `_fetch`.
`ScraperFactory` escolhe a classe pelo `name` da fonte em `sources.yaml`;
`ScraperRunner` roda todas as fontes ativas, isola falhas (`runner.errors`)
e remove duplicatas.

Para adicionar um site: crie `scrapers/meusite.py`, registre em
`ScraperFactory.REGISTRY` e adicione a fonte em `config/sources.yaml`.

| Fonte | Tipo | Observações |
|---|---|---|
| gupy | API do portal (não oficial) | 1 requisição por palavra-chave |
| remotive | API pública | 1 requisição; máx. ~4/dia; vagas com 24h de atraso |

## Filtros (Parte 3)
Cada critério é uma classe que herda de `BaseFilter` e implementa `accepts(job)`.
`FilterChain.from_criteria(criteria)` monta a cadeia padrão; `apply(jobs)`
devolve só as vagas aprovadas em todos os filtros e `rejected` mostra quantas
cada filtro descartou (útil para calibrar o `settings.yaml`).

| Filtro | Regra |
|---|---|
| `KeywordFilter` | A vaga cita ao menos uma tecnologia de `keywords` |
| `ExcludedKeywordFilter` | Descarta se citar algo de `excluded_keywords` |
| `SeniorityFilter` | Pelo **título**: aceita níveis de `seniority` ou vaga sem nível; descarta outros níveis (ex.: Sênior) |
| `LocationFilter` | Remota: só sem restrição ou com região de `remote_regions` ("USA Only" sai). Presencial: cidade de `locations` |
| `SalaryFilter` | Mínimo de estágio ou geral; sem salário passa se `accept_unknown_salary` |

As palavras são comparadas como **palavras inteiras** (`utils.text.contains_term`):
"java" não casa com "javascript" e ".net" casa com "asp.net". Para aceitar
variações como "nodejs", adicione-as em `keywords`.

Para criar um filtro: herde de `BaseFilter`, defina `name`, implemente `accepts`
e adicione a classe em `DEFAULT_FILTERS` (`filters/chain.py`).
