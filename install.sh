#!/usr/bin/env bash
# Instala o JobHunter numa máquina nova (Linux/macOS).
#
# Uso:
#   ./install.sh          # instala para usar
#   ./install.sh --dev    # instala também o pytest e roda os testes
#
# Requisito: Python 3.11+ (troque o executável com PYTHON=python3.12 ./install.sh).
set -euo pipefail

cd "$(dirname "$0")"
PYTHON="${PYTHON:-python3}"
DEV=false
[[ "${1:-}" == "--dev" ]] && DEV=true

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "Erro: '$PYTHON' não encontrado. Instale o Python 3.11 ou mais novo." >&2
    exit 1
fi
if ! "$PYTHON" -c 'import sys; sys.exit(sys.version_info < (3, 11))'; then
    echo "Erro: o JobHunter precisa do Python 3.11+ (encontrado: $("$PYTHON" --version))." >&2
    exit 1
fi

echo "==> Criando o ambiente virtual em .venv"
[[ -d .venv ]] || "$PYTHON" -m venv .venv

echo "==> Instalando o JobHunter e as dependências"
.venv/bin/python -m pip install --quiet --upgrade pip
if $DEV; then
    .venv/bin/python -m pip install --quiet -e ".[dev]"
else
    .venv/bin/python -m pip install --quiet -e .
fi

echo "==> Criando as pastas de dados"
mkdir -p data/resume data/output

if $DEV; then
    echo "==> Rodando os testes"
    .venv/bin/python -m pytest -q
fi

cat <<'MSG'

Pronto! Próximos passos:
  1. Coloque seu currículo em data/resume/curriculo.pdf
  2. Ajuste seus critérios em config/settings.yaml
  3. Ative o ambiente:   source .venv/bin/activate
  4. Confira o ranking:  jobhunter --dry-run
  5. Gere os prompts:    jobhunter
MSG
