# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

JobHunter finds developer job postings (Java, JavaScript, Python) from free sources, filters and ranks them against the user's profile, writes a résumé-tailoring prompt (.txt) for the top N to paste into a free chat AI, and remembers postings already seen. The whole project must stay free of cost. The planned pipeline:

Scrapers → Filters → Drop already-seen → Ranking → Top N → Résumé prompt (.txt) → Save memory

The project is feature-complete (Parts 1–10): free scrapers, filters, seen-jobs storage, ranking, résumé prompts, the pipeline service, the `jobhunter` CLI, and installation (`install.sh`, Docker). Open issue: the Gupy endpoint returns 404. There is no CLI entry point yet.

Code, docstrings, comments, error messages and the README are written in **Portuguese (pt-BR)**. Keep new code in the same language.

## Commands

```bash
./install.sh --dev                       # new machine: venv + editable install + data dirs + tests
python -m venv .venv && source .venv/bin/activate   # or manually
pip install -e ".[dev]"
docker compose run --rm jobhunter --dry-run           # Docker (not tested in this environment: no Docker here)

jobhunter --dry-run                      # real run: scrape, filter, rank (nothing saved)
jobhunter                                # full run: writes prompt .txt files to data/output and saves memory

pytest                                   # all tests
pytest tests/test_gupy.py                # one file
pytest tests/test_gupy.py::test_parses_job_fields   # one test
```

`pytest` is configured in `pyproject.toml` with `pythonpath = ["src"]`. No linter or formatter is configured.

## Architecture

Package lives in `src/jobhunter/` (src layout).

- **`models.Job`**: frozen dataclass, the unit passed between pipeline stages. Never mutate it; use `with_score()` or `dataclasses.replace`. `Job.uid` (sha256 of company|title|url, lowercased) is the dedup key used across sources and across runs (the "seen" memory). `searchable_text`, `headline` (title + tags, where sources put the job level) and `is_internship` (whole words on `headline`) are what filters should rely on. Seniority checks use `headline`, never the description.
- **`models.SearchCriteria`**: user filters; `__post_init__` lowercases every list, so comparisons should use lowercased job text. `min_salary_for(is_internship)` picks the internship vs. regular minimum.
- **`config.Settings.load(settings_file, sources_file)`**: reads `config/settings.yaml` (`criteria` → `SearchCriteria(**...)`, `paths`) and `config/sources.yaml` (list of `SourceConfig`). Every validation failure is converted to `ConfigError`. `SourceConfig.type` must be `html`, `rss` or `api`.
- **Scrapers** (`scrapers/`):
  - `BaseScraper`: subclasses implement `_fetch(criteria) -> list[Job]`; callers use `fetch()`, which wraps `httpx.HTTPError` and `ValueError/TypeError/AttributeError` into `ScraperError`. The `httpx.Client` is injectable.
  - `ScraperFactory.REGISTRY` maps the source's `name` (not `type`) in `sources.yaml` to a scraper class.
  - `ScraperRunner.run(criteria)` runs every source, logs failures into `runner.errors` without aborting the others, and dedups by `uid`.
  - To add a source: create `scrapers/<site>.py`, register it in `ScraperFactory.REGISTRY`, add an entry to `config/sources.yaml`.
- **Filters** (`filters/`): `BaseFilter.accepts(job) -> bool`, one class per criterion in `rules.py` (keywords, excluded keywords, seniority by **title + tags** (`Job.headline`), location/remote regions, salary). `FilterChain.from_criteria(criteria)` builds the default chain from `DEFAULT_FILTERS`; `apply(jobs)` keeps jobs approved by every filter and counts discards per filter `name` in `rejected`. Term matching uses `utils.text.contains_term` (whole words).
- **Ranking** (`ranking/`): same pattern as filters. `BaseScoreRule.score(job)` returns 0..1 and has a `weight`; rules in `ranking/rules.py` (keywords 4, seniority 3, location 1, salary 1, recency 1; unknown info scores 0.5). `JobRanker.from_criteria(criteria, now=None)` combines them as a weighted average scaled to 0..10; `rank(jobs)` returns copies with `score` set, best first (ties: most recent first); `top(jobs)` returns `criteria.top_n`. Seniority logic is shared through `filters.rules.accepted_levels` / `has_accepted_level`.
- **Pipeline** (`services/pipeline.py`): `JobHuntPipeline` only orchestrates; every stage is injected (`from_settings(settings, repository)` builds the defaults). `run(dry_run=False) -> PipelineResult`. Only jobs whose prompt file was written are marked as seen; per-job `ResumeError`s are collected in `result.errors` and don't stop the loop; an unreadable base résumé only adds a warning (prompts ask the user to attach the PDF).
- **CLI** (`main.py`, console script `jobhunter`): `--config-dir` (default: `./config` if it exists, else the project's `config/` via `default_config_dir()`), `--dry-run`, `--top N`, `-v`. `load_settings` resolves relative paths against the parent of the config dir (project root). Exit code 1 on `ConfigError`/`StorageError`. Without `-v`, logging is at ERROR so warnings appear only once, in the report.
- **Résumé** (`resume/`): **zero cost, no paid API** (user decision 2026-11-20). `ResumeReader.read(path)` extracts PDF text with `pypdf`; `ResumePromptBuilder.build(job, resume_text=None)` returns a prompt (rules forbidding invented experience + job data + résumé text, or a request to attach the PDF when the text is missing) that the user pastes into a free chat AI; `ResumeWriter(output_dir).write(job, text, rank)` saves `<rank:02d>_<company>_<title>_<uid>.txt`. Failures become `ResumeError`. The former Anthropic API tailor lives only in git history (tag `v0.7.0`); do not reintroduce paid APIs.
- **Storage** (`storage/`): `JobRepository(db_path)` (Repository pattern, all SQL lives there) keeps processed jobs in SQLite table `seen_jobs`, keyed by `Job.uid`. `filter_unseen(jobs)` keeps order, `mark_seen(jobs)` uses `INSERT OR IGNORE` and returns how many were new, plus `has_seen`, `count`, `close`/context manager. `":memory:"` works for tests; parent folders are created; `sqlite3` errors become `StorageError`. The caller decides which jobs to mark (planned: only the top N).
- **`utils.text`**: `contains_term` (whole-word, case-insensitive), `strip_html` (BeautifulSoup) and `parse_datetime` (ISO-8601, always returns tz-aware datetimes, UTC when none given, so dates from different sources can be compared).

Source-specific constraints that shape the code:
- **github-frontendbr / github-backendbr** (`GitHubVagasScraper`, same class registered under two names): open issues of community job repos, 1 request per repo (`per_page=100`); pull requests skipped; `[Remoto]`/label "Remoto" → `remote=True`, `location="Brasil"`; a `[City/UF]` prefix becomes `location`; company guessed from "... na Empresa" or "... - Empresa"; labels become `tags`.
- **jobicy**: one request with `geo=brazil` (tight rate limit, 429 on quick repeats); `jobLevel` (unless "Any") becomes a tag.
- **weworkremotely**: RSS parsed with `xml.etree` via `BaseScraper._get_text`; title "Company: Role"; `region` becomes `location`; `parse_datetime` also accepts RFC 822 dates.
- **gupy**: ⚠️ as of 2026-11-20 the configured endpoint (`portal.api.gupy.io/api/job`) returns 404, and so does `/api/v1/jobs`; the runner isolates the failure. Needs a new endpoint or to be disabled. Unofficial portal API; `location` is `city, state, country` (country defaults to "Brasil", so the location filter accepts remote Gupy jobs); one request per keyword (empty term if no keywords), results merged by `uid`. Items missing title or URL are skipped.
- **remotive**: public API with a tight rate limit (~4 calls/day) and 24h delay. It makes **one** request for the whole `software-dev` category and leaves keyword filtering to the filter stage. Job links must point to Remotive (terms of use). `candidate_required_location` becomes `location` so the location filter can drop country-restricted postings.

## Testing

Tests never hit the network. Use the `make_client(payload, status=200)` fixture in `tests/conftest.py`, which returns an `httpx.Client` backed by `httpx.MockTransport`. `client.requests` records the requests made, so tests can assert request count and params. `ScraperRunner` takes a `scraper_factory` callable so tests can inject fake scrapers.

## Data paths

`config/settings.yaml` paths (`data/resume/curriculo.pdf`, `data/output`, `data/jobs.db`) are relative to the repo root. `data/` lives at the repo root; `.gitignore` ignores its contents except the `.gitkeep` placeholders, so the personal résumé, generated résumés and the database are never committed.

## Decisions from earlier development (Claude Web history)

Parts 1 and 2 were designed in a Claude Web chat before moving to Claude Code. Decisions already made there:

- **Installation** (Part 10): `install.sh` (Linux/macOS, checks Python 3.11+, `--dev` also runs tests); `Dockerfile` (python:3.12-slim, `ENTRYPOINT jobhunter`, default `--dry-run`) + `docker-compose.yml` (mounts `./config` read-only and `./data`, runs as host `UID:GID`). Keep `pyproject.toml` `version` in sync with release tags.
- **Résumé**: the base résumé is a **PDF** (`data/resume/curriculo.pdf`). Tailoring happens in a free chat AI from the generated prompt, **never inventing experience**.
- **Ranking**: score by keywords / seniority / location; semantic similarity may be added later.
- **Filters (Part 3, implemented), answered by the user**:
  - Jobs that don't mention a seniority level (e.g. "Desenvolvedor Python") are **kept**; ranking gives them a lower score.
  - Remote jobs restricted to other countries (e.g. "USA Only") are **removed**; accept only Worldwide, LATAM and Brazil.
  - A job is an internship when its title contains "estágio", "estagiário" or "intern" (`Job.is_internship`, plain substring match); salary minimums are R$ 2,000 (internship) / R$ 3,000 (others), and jobs without salary pass (`accept_unknown_salary`).
- **Sources**: prefer APIs/RSS over HTML scraping. **Do not scrape LinkedIn or Indeed** (they block it and forbid it in their terms). Vagas.com and Infojobs (HTML) were postponed. We Work Remotely was suggested but not implemented.
- **Gupy**: the listing may return only a summary description; if so, fetch the full description from the job page **only for the finalists** (planned for Part 3). The user asked to read Gupy's developer docs, but that fetch failed and is still pending; field names are unconfirmed.
- **Remotive**: salary comes as free text in USD/year, so `salary_min/max` stay `None`; do not convert currencies (it would distort the BRL filters).
- **Distribution (final part)**: make installation on new machines easy (install script and/or Docker).
- **Communication**: the user prefers short answers and low token usage.

## Database and local installs

Job memory uses **SQLite** (`data/jobs.db`, Python's built-in `sqlite3`), which is just a file and needs no server. Never install a database server on the user's machine; if one is ever needed, run it with Docker.

## Git workflow

Each project part goes on a branch named `parte-N-nome` (e.g. `parte-2-scrapers`). When the part is done it is committed and the branch is pushed automatically; merging into `main` only happens with explicit user authorization. Full rules in section 7 below.

Files that must never be committed (already in `.gitignore`): `.venv/`, `__pycache__/`, `*.egg-info/`, `.pytest_cache/`, `.env`, `data/jobs.db`, `data/output/*`, `data/resume/*` (personal résumé). Use `git add <paths>` or check `git status` after `git add -A` to confirm none of them are staged.

# JobHunter — Claude Code Instructions

## 1. Project Context

JobHunter is a Python application designed to automate job searching for software development positions.

The system should:

- Search for job openings across multiple platforms and sources.
- Apply filters defined by the user.
- Avoid processing jobs that have already been found in previous executions.
- Rank job opportunities according to the user's professional profile.
- Select the most relevant opportunities.
- Read the user's base resume.
- Generate tailored resume versions for each selected job.
- Store processed jobs to prevent duplicates in future executions.

The user will manually apply for the jobs.

## 2. Technologies and Architecture

- Python 3.11+
- Object-Oriented Programming (OOP)
- SQLite for job persistence
- Pytest for testing
- YAML for configuration
- HTTPX for HTTP requests
- BeautifulSoup4 for HTML parsing when necessary

Maintain a modular architecture with clearly separated responsibilities.

Avoid implementing multiple responsibilities within a single class or concentrating all business logic in the main entry point.

## 3. Job Profile and Filtering Criteria

Prioritize jobs related to:

- Java
- JavaScript
- Python
- Spring
- React
- Node.js
- Django
- FastAPI

Prioritize the following seniority levels:

- Internship
- Junior
- Mid-level

Salary criteria:

- Internship positions: minimum salary of BRL 2,000.
- Other positions: minimum salary of BRL 3,000.

Jobs without a disclosed salary may still be accepted and evaluated by the ranking system, according to the configured filtering criteria.

Remote positions restricted to countries where the candidate is not eligible must be discarded. Prioritize opportunities labeled Worldwide, LATAM, or Brazil when applicable.

## 4. Development Guidelines

- Develop the project incrementally, one stage at a time.
- Before implementing a new feature, analyze the existing project structure.
- Do not refactor unrelated parts of the codebase unnecessarily.
- Do not create unnecessary files.
- Do not overwrite existing implementations without analyzing their impact.
- Reuse existing classes, interfaces, patterns, and conventions.
- Apply Object-Oriented Programming principles consistently and appropriately.
- Maintain low coupling and clearly defined responsibilities.
- Prioritize simple, readable, maintainable, and testable code.

## 5. Testing and Documentation

Every new feature must include relevant unit tests.

- Use pytest.
- Test expected behavior.
- Test relevant error scenarios and edge cases.
- Do not consider an implementation complete without running the relevant tests.
- Document classes, methods, and features clearly.
- Update README.md whenever there are relevant changes to the architecture, installation process, or usage instructions.

Documentation should be educational and help the developer understand how the project works.

## 6. Workflow and Communication

The user is developing this project while learning.

**Plan first, then implement.** Before creating or editing any code, present a short plan and wait for the user's approval:

1. Purpose of the change.
2. Architectural decision and why it was chosen.
3. Files that will be created or changed and how the implementation will work.
4. Tests that will be added or run.
5. Commit message(s) and, when applicable, the merge title and tag.

Once the user approves the plan, implement it, run the tests, commit and push **without asking for confirmation again** (the approved plan is the authorization, including any merge/tag it lists). If something must deviate from the plan, stop and explain.

After finishing, give a short summary: what was done, test results, commits, branch and push status, and the suggested next step (without starting it).

Avoid excessively long responses and unnecessary token consumption.

Do not implement multiple future stages without the user's authorization. Work only on the requested task and follow the project's incremental development approach.

## 7. Git and Version Control

Git version control is mandatory throughout development.

### Commits

- Automatically create commits when a functional stage is completed.
- Before committing, inspect the changes and ensure sensitive files, credentials, `.env` files, personal resumes, generated files, and private data are not included.
- Run tests before committing.
- Do not commit broken code or failing tests unless explicitly authorized by the user.
- Use Conventional Commits in English, maintaining consistency.

Commit types:

- `feat:` new feature
- `fix:` bug fix
- `test:` tests
- `docs:` documentation
- `refactor:` code refactoring
- `chore:` maintenance tasks

Examples:

- `feat: implement job filtering system`
- `test: add unit tests for salary filters`
- `docs: document scraper architecture`
- `fix: correct remote job filtering`

### Branches

- Never develop directly on the `main` branch.
- Create a dedicated branch for each development stage or significant feature.
- Use descriptive branch names, such as `parte-3-filters` or `feat/job-ranking`.
- Keep the `main` branch stable.

### Push

- After validating and creating a commit, automatically push the branch to the remote repository whenever Git is properly configured and the push is safe.
- Configure the upstream branch when necessary.
- Never perform force pushes (`--force` or `--force-with-lease`).
- Never overwrite remote commits.
- Never push secrets or private files.

### Releases and Versioning

Follow Semantic Versioning (SemVer):

- `v0.1.0` — initial project foundation
- `v0.2.0` — significant new feature
- `v0.2.1` — bug fix

Create tags only for stable versions after integration into `main`, not for every commit.

Never merge into `main`, create tags, or publish releases automatically without explicit user authorization.

Merges into `main` use `git merge --no-ff` with an English title in the format `Part N <name>` (e.g. `Part 3 filters`), consistent with the English commit messages. Always show the merge title to the user before merging; an approved plan containing the title counts as authorization.

Right after merging a part into `main`, create and push its annotated SemVer tag in the same step (e.g. `git tag -a v0.4.0 -m "v0.4.0: <summary>"` then `git push origin v0.4.0`). The tag is listed in the plan, so plan approval covers it.

## 8. Mandatory Workflow for Every Development Stage

1. Inspect the current project structure and Git status.
2. Confirm the correct branch for the requested task.
3. Present the plan (section 6) and wait for the user's approval.
4. Implement only the approved stage or feature.
5. Create or update relevant unit tests.
6. Update the relevant documentation.
7. Run the tests.
8. Review `git diff` and the files that will be committed.
9. Create a commit following Conventional Commits.
10. Push the branch to GitHub.
11. Provide the user with a summary of the changes, tests, commit, branch, and push status.

Never execute destructive commands such as `git reset --hard`, delete branches, or overwrite the user's changes without explicit authorization.

If conflicts, failing tests, unexpected changes, authentication issues, or any risk of data loss occur, stop the process and explain the problem before proceeding.