#!/usr/bin/env bash
# Rode apenas em instalação de laboratório NOVA. Não remove volumes nem índices.
set -euo pipefail
cd "$(dirname "$0")/.."
compose=(docker compose --env-file .env.evaluation -f docker-compose.yml -f evaluation/compose.lab.yml)
if [ ! -f .env.evaluation ]; then
  docker run --rm --user "$(id -u):$(id -g)" -v "$PWD:/app" -w /app \
    python:3.11-slim python evaluation/prepare_lab.py
fi
if [ "${EVAL_FRESH_RESULTS:-0}" = 1 ] && [ -d entrega_pessoa_2 ]; then
  backup="$(mktemp -d .evaluation-private/evidencias-base.XXXXXX)"
  mv entrega_pessoa_2 "$backup/entrega_pessoa_2"
fi
mkdir -p entrega_pessoa_2
"${compose[@]}" config --quiet
"${compose[@]}" build api worker kerberos
"${compose[@]}" run -T --rm --no-deps frontend sh -c 'npm ci && npm run build' \
  > entrega_pessoa_2/frontend_build.txt 2>&1
"${compose[@]}" up -d --no-build kerberos kafka elasticsearch redis openldap api frontend
"${compose[@]}" run -T --rm --no-deps worker \
  /app/scripts/with_kerberos.sh python -m evaluation.seed_lab --allow-synthetic
"${compose[@]}" exec -T api python -m pytest -q > entrega_pessoa_2/pytest.txt
"${compose[@]}" exec -T api python -m evaluation.collect_pessoa2 --iterations 100
"${compose[@]}" run -T --rm --no-deps worker \
  /app/scripts/with_kerberos.sh python -m evaluation.collect_pessoa2 --kerberos worker
"${compose[@]}" restart redis
"${compose[@]}" exec -T api python -c \
  'import time; from app.api.main import redis; [(time.sleep(1)) for _ in range(3)]; assert redis.ping()'
"${compose[@]}" exec -T api python -m evaluation.collect_pessoa2 --persistence
echo "Coleta de API concluída. Capture o navegador e gere o relatório conforme o README da entrega."
