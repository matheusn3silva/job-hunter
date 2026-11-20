# JobHunter

Busca vagas de desenvolvedor (Java, JavaScript, Python), ranqueia pelo seu
perfil, adapta seu currículo para as 10 melhores e lembra das vagas já vistas.

## Pipeline
Scrapers → Filtros → Remover já vistas → Ranking → Top N → Adaptar currículo → Salvar memória

## Instalação (desenvolvimento)
    python -m venv .venv && source .venv/bin/activate
    pip install -e ".[dev]"
    pytest

## Uso
    jobhunter --dry-run        # busca, filtra e mostra o ranking (sem IA, sem gravar)
    jobhunter                  # gera os currículos do top N e salva na memória
    jobhunter --top 5 -v       # top 5, com logs detalhados

Para gerar currículos é preciso `ANTHROPIC_API_KEY` (veja a Parte 6) e o
seu currículo em `data/resume/curriculo.pdf`.

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

Todas as fontes são **gratuitas e sem chave**:

| Fonte (`name`) | Tipo | Observações |
|---|---|---|
| `github-frontendbr`, `github-backendbr` | API do GitHub | Vagas brasileiras como issues (etiquetas de nível, remoto, tecnologias); 1 requisição por repositório (limite: 60/hora) |
| `jobicy` | API pública | Remotas abertas ao Brasil (`geo=brazil`); 1 requisição; limite apertado |
| `weworkremotely` | RSS | Remotas de programação; a região vira `location` |
| `remotive` | API pública | 1 requisição; máx. ~4/dia; a versão gratuita devolve poucas vagas |
| `gupy` | API do portal (não oficial) | ⚠️ retorna 404 desde 2026-11 (a investigar) |

**Por que não LinkedIn/Indeed?** Não têm API pública de busca de vagas
(só para parceiros), os termos de uso proíbem scraping, bloqueiam robôs
(login, CAPTCHA) e a conta usada pode ser banida.

O nível da vaga é lido do **título e das tags** (`Job.headline`): algumas
fontes informam "Sênior"/"Júnior" só em etiquetas.

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

## Memória (Parte 4)
`storage.JobRepository` guarda as vagas já processadas em SQLite
(`data/jobs.db`, criado automaticamente; o `sqlite3` já vem com o Python,
nada a instalar). Todo o SQL fica nessa classe (padrão Repository).

    with JobRepository("data/jobs.db") as repo:
        novas = repo.filter_unseen(vagas)   # remove as já vistas
        ...
        repo.mark_seen(top_n)               # lembra destas nas próximas execuções

- A chave é `Job.uid` (empresa + título + URL).
- Marcar a mesma vaga de novo é ignorado; `count()` e `has_seen(uid)` ajudam a inspecionar.
- Erros de arquivo/SQL viram `StorageError` com mensagem clara.
- O banco fica fora do git (`.gitignore`). Apagar `data/jobs.db` "esquece" tudo.

## Ranking (Parte 5)
`ranking.JobRanker` dá uma nota de **0 a 10** a cada vaga e ordena da melhor
para a pior. A nota é a média ponderada de regras (`BaseScoreRule`), cada uma
avaliando um aspecto de 0 a 1:

| Regra | Peso | Como pontua |
|---|---|---|
| `KeywordScore` | 4 | Tecnologias citadas (no título contam em dobro); 4 acertos = nota máxima |
| `SeniorityScore` | 3 | Nível desejado no título = 1; sem nível informado = 0,5 |
| `LocationScore` | 1 | Remota ou na cidade desejada = 1; desconhecido = 0,5 |
| `SalaryScore` | 1 | Salário divulgado = 1; desconhecido = 0,5 |
| `RecencyScore` | 1 | Até 7 dias = 1, cai até 0 aos 30 dias; sem data = 0,5 |

    ranker = JobRanker.from_criteria(criteria)
    melhores = ranker.top(vagas)   # top_n do settings.yaml, já com score

Empates: a vaga mais recente vem primeiro. Para mudar a importância de um
aspecto, altere o `weight` da regra em `ranking/rules.py`.

## Currículo (Parte 6)
O módulo `resume` tem três classes, cada uma com uma responsabilidade:

| Classe | Papel |
|---|---|
| `ResumeReader` | Extrai o texto do seu PDF (`pypdf`). PDF escaneado (só imagem) gera erro claro |
| `ResumeTailor` | Pede ao Claude (`claude-opus-5-5`) uma versão do currículo para a vaga |
| `ResumeWriter` | Salva em `data/output/<empresa>_<titulo>_<uid>.md` |

Regras dadas à IA: **nunca inventar** experiências, empresas, datas ou
habilidades; só reordenar, reescrever e destacar o que já está no currículo,
no idioma da vaga. Revise sempre o resultado antes de enviar.

Configuração da API: crie uma chave em console.anthropic.com e exporte
`ANTHROPIC_API_KEY` (ou use `ant auth login`). Nunca coloque a chave no
código nem no git (`.env` já é ignorado). Cada vaga adaptada é uma chamada
paga; o texto do currículo vai com cache para baratear as chamadas seguintes.
Se o modelo recusar um pedido, o servidor tenta outro modelo automaticamente
(`fallbacks: "default"`).

Erros (arquivo, chave, limite de uso, rede, recusa) viram `ResumeError`.

## Pipeline e CLI (Parte 7)
`services.JobHuntPipeline` só coordena as etapas; cada uma é feita pela classe
responsável, recebida no construtor (os testes trocam qualquer peça por uma
falsa):

    ScraperRunner → FilterChain → JobRepository.filter_unseen → JobRanker.top
    → ResumeReader/ResumeTailor/ResumeWriter → JobRepository.mark_seen

- `run(dry_run=True)` para antes da IA e não grava nada.
- Só vagas com currículo gerado vão para a memória: se a API falhar em uma
  vaga, ela volta na próxima execução; a falha de uma não interrompe as outras.
- O resultado (`PipelineResult`) traz contagens, descartes por filtro, top N,
  arquivos gerados e avisos, que a CLI (`main.py`) imprime como relatório.
- Caminhos do `settings.yaml` são relativos à raiz do projeto (pasta acima de
  `--config-dir`), então o comando funciona de qualquer pasta.

Códigos de saída: `0` ok; `1` erro de configuração ou de memória.
