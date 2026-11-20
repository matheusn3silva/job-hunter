# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

JobHunter finds developer job postings (Java, JavaScript, Python), filters and ranks them against the user's profile, tailors the résumé for the top N, and remembers postings already seen. The planned pipeline:

Scrapers → Filters → Drop already-seen → Ranking → Top N → Tailor résumé → Save memory

Only the first stage (scrapers) plus models/config exist so far. There is no CLI entry point yet.

Code, docstrings, comments, error messages and the README are written in **Portuguese (pt-BR)**. Keep new code in the same language.

## Commands

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

pytest                                   # all tests
pytest tests/test_gupy.py                # one file
pytest tests/test_gupy.py::test_parses_job_fields   # one test
```

`pytest` is configured in `pyproject.toml` with `pythonpath = ["src"]`. No linter or formatter is configured.

## Architecture

Package lives in `src/jobhunter/` (src layout).

- **`models.Job`**: frozen dataclass, the unit passed between pipeline stages. Never mutate it; use `with_score()` or `dataclasses.replace`. `Job.uid` (sha256 of company|title|url, lowercased) is the dedup key used across sources and across runs (the "seen" memory). `searchable_text` and `is_internship` are what filters should rely on.
- **`models.SearchCriteria`**: user filters; `__post_init__` lowercases every list, so comparisons should use lowercased job text. `min_salary_for(is_internship)` picks the internship vs. regular minimum.
- **`config.Settings.load(settings_file, sources_file)`**: reads `config/settings.yaml` (`criteria` → `SearchCriteria(**...)`, `paths`) and `config/sources.yaml` (list of `SourceConfig`). Every validation failure is converted to `ConfigError`. `SourceConfig.type` must be `html`, `rss` or `api`.
- **Scrapers** (`scrapers/`):
  - `BaseScraper`: subclasses implement `_fetch(criteria) -> list[Job]`; callers use `fetch()`, which wraps `httpx.HTTPError` and `ValueError/TypeError/AttributeError` into `ScraperError`. The `httpx.Client` is injectable.
  - `ScraperFactory.REGISTRY` maps the source's `name` (not `type`) in `sources.yaml` to a scraper class.
  - `ScraperRunner.run(criteria)` runs every source, logs failures into `runner.errors` without aborting the others, and dedups by `uid`.
  - To add a source: create `scrapers/<site>.py`, register it in `ScraperFactory.REGISTRY`, add an entry to `config/sources.yaml`.
- **`utils.text`**: `strip_html` (BeautifulSoup) and `parse_datetime` (ISO-8601, always returns tz-aware datetimes, UTC when none given, so dates from different sources can be compared).

Source-specific constraints that shape the code:
- **gupy**: unofficial portal API; one request per keyword (empty term if no keywords), results merged by `uid`. Items missing title or URL are skipped.
- **remotive**: public API with a tight rate limit (~4 calls/day) and 24h delay. It makes **one** request for the whole `software-dev` category and leaves keyword filtering to the filter stage. Job links must point to Remotive (terms of use). `candidate_required_location` becomes `location` so the location filter can drop country-restricted postings.

## Testing

Tests never hit the network. Use the `make_client(payload, status=200)` fixture in `tests/conftest.py`, which returns an `httpx.Client` backed by `httpx.MockTransport`. `client.requests` records the requests made, so tests can assert request count and params. `ScraperRunner` takes a `scraper_factory` callable so tests can inject fake scrapers.

## Data paths

`config/settings.yaml` paths (`data/resume/curriculo.pdf`, `data/output`, `data/jobs.db`) are relative to the repo root, and `.gitignore` ignores `data/...` at the root. However, the `.gitkeep` placeholders currently sit under `src/data/`. Check which location is intended before writing code that reads or writes these paths.

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

Whenever implementing a feature:

1. Briefly explain its purpose.
2. Explain the architectural decision and why it was chosen.
3. Present the changes made.
4. Explain how the implementation works.
5. Report which tests were executed and their results.
6. Suggest the next step without proceeding to it automatically.

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

## 8. Mandatory Workflow for Every Development Stage

1. Inspect the current project structure and Git status.
2. Confirm the correct branch for the requested task.
3. Implement only the requested stage or feature.
4. Create or update relevant unit tests.
5. Update the relevant documentation.
6. Run the tests.
7. Review `git diff` and the files that will be committed.
8. Create a commit following Conventional Commits.
9. Push the branch to GitHub.
10. Provide the user with a summary of the changes, tests, commit, branch, and push status.

Never execute destructive commands such as `git reset --hard`, delete branches, or overwrite the user's changes without explicit authorization.

If conflicts, failing tests, unexpected changes, authentication issues, or any risk of data loss occur, stop the process and explain the problem before proceeding.