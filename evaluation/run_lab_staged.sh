#!/usr/bin/env bash
# Laboratório novo. Autenticações de Kafka e Elasticsearch em etapas independentes.
set -euo pipefail
cd "$(dirname "$0")/.."
compose=(docker compose --env-file .env.evaluation -f docker-compose.yml -f evaluation/compose.lab.yml)
if [ ! -f .env.evaluation ]; then
  docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/app" -w /app \
    python:3.11-slim python evaluation/prepare_lab.py
fi
mkdir -p entrega_pessoa_2
"${compose[@]}" config --quiet
"${compose[@]}" build api worker kerberos
docker run --rm -v "$PWD:/app" -w /app enade-plataforma-api \
  python -m pytest -q > entrega_pessoa_2/pytest.txt
"${compose[@]}" run -T --rm --no-deps frontend sh -c 'npm ci && npm run build' \
  > entrega_pessoa_2/frontend_build.txt
"${compose[@]}" up -d --wait kerberos redis openldap
"${compose[@]}" up -d --no-deps api
"${compose[@]}" exec -T api python -c '
import time, urllib.request
for attempt in range(30):
    try:
        urllib.request.urlopen("http://localhost:8000/openapi.json", timeout=2).read()
        break
    except OSError:
        time.sleep(1)
else:
    raise SystemExit("API não iniciou")
'
"${compose[@]}" exec -T api python -m evaluation.collect_pessoa2 --auth-only
"${compose[@]}" up -d --wait kafka
"${compose[@]}" exec -T api python -m evaluation.collect_pessoa2 --kerberos api --kerberos-service kafka
"${compose[@]}" run -T --rm --no-deps worker \
  /app/scripts/with_kerberos.sh python -m evaluation.collect_pessoa2 --kerberos worker --kerberos-service kafka
"${compose[@]}" stop kafka
"${compose[@]}" up -d --no-deps --wait --wait-timeout 600 elasticsearch
"${compose[@]}" run -T --rm --no-deps worker \
  /app/scripts/with_kerberos.sh python -m evaluation.seed_lab --allow-synthetic
"${compose[@]}" exec -T -e EVAL_KERBEROS_SERVICES=elasticsearch api \
  python -m evaluation.collect_pessoa2 --iterations 100
"${compose[@]}" run -T --rm --no-deps worker /app/scripts/with_kerberos.sh \
  python -m evaluation.collect_pessoa2 --kerberos worker --kerberos-service elasticsearch
"${compose[@]}" restart redis
"${compose[@]}" exec -T api python -c 'import time; time.sleep(3)'
"${compose[@]}" exec -T api python -m evaluation.collect_pessoa2 --persistence
"${compose[@]}" up -d --no-deps frontend
docker build -f evaluation/Dockerfile.evidence -t enade-evidence-tools:local .
docker info --format '{{json .MemTotal}}' > entrega_pessoa_2/memoria_docker_bytes.json
docker run --rm --network enade-plataforma_default --env-file .env.evaluation \
  -e EVAL_SOURCE_COMMIT="$(git rev-parse HEAD)" -e EVAL_ENVIRONMENT="Docker local, execução em etapas" \
  -v "$PWD:/app" -w /app enade-evidence-tools:local \
  sh -c 'python -m evaluation.capture_pessoa2 && python -m evaluation.report_pessoa2'
