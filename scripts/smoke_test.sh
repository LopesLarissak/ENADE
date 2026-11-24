#!/usr/bin/env bash
set -euo pipefail
API="${API_URL:-http://localhost:8000}"
login() {
  local user="$1" pass="$2"
  curl -fsS -X POST "$API/auth/login" -H 'Content-Type: application/json' \
    -d "{\"username\":\"$user\",\"password\":\"$pass\"}" | python -c 'import sys,json; print(json.load(sys.stdin)["access_token"])'
}
STUDENT_TOKEN="$(login estudante 'Estudante@123')"
PROFESSOR_TOKEN="$(login professor 'Professor@123')"
STATUS="$(curl -sS -o /tmp/enade_student_forbidden.json -w '%{http_code}' "$API/analytics/courses" -H "Authorization: Bearer $STUDENT_TOKEN")"
if [[ "$STATUS" != "403" ]]; then echo "Esperado 403 para estudante; recebido $STATUS"; exit 1; fi
curl -fsS "$API/analytics/courses" -H "Authorization: Bearer $PROFESSOR_TOKEN" >/dev/null
curl -fsS "$API/health" >/dev/null
curl -fsS "$API/questions?q=tecnologia&size=1" >/dev/null
echo "Smoke tests concluídos: login LDAP, 403 estudante, analytics professor, health e busca."
