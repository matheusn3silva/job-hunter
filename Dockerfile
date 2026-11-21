# Imagem do JobHunter: roda em qualquer sistema com Docker, sem instalar Python.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependências e código primeiro: mudar só a config não refaz a instalação.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install .

# Config padrão (o docker-compose monta a sua por cima).
COPY config ./config
RUN mkdir -p data/resume data/output && chmod -R a+rwX data

# Porta do site (serviço "web" do docker-compose).
EXPOSE 5000

ENTRYPOINT ["jobhunter"]
CMD ["--dry-run"]
