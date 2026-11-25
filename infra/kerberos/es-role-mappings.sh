#!/usr/bin/env bash
# Mapeia os principals Kerberos para as roles de roles.yml.
# O arquivo role_mapping.yml só vale para realms LDAP/AD/PKI; para o realm
# Kerberos o Elasticsearch exige mapeamentos pela API de segurança.
# Executar dentro do container elasticsearch (usa ELASTIC_PASSWORD do ambiente,
# sem imprimir o valor): docker compose exec -T elasticsearch bash -s < este_arquivo
set -euo pipefail
: "${ELASTIC_PASSWORD:?ELASTIC_PASSWORD ausente no container elasticsearch}"
for attempt in $(seq 1 60); do
  code=$(curl -sk -o /dev/null -w '%{http_code}' -u "elastic:${ELASTIC_PASSWORD}" https://localhost:9200/_security/_authenticate || true)
  [ "$code" = 200 ] && break
  sleep 2
done
[ "$code" = 200 ] || { echo "Usuário administrativo do Elasticsearch indisponível (HTTP $code)."; exit 1; }
for service in api worker; do
  body="{\"enabled\":true,\"roles\":[\"enade_${service}_role\"],\"rules\":{\"all\":[{\"field\":{\"username\":\"${service}/${service}\"}},{\"field\":{\"realm.name\":\"kerb1\"}}]}}"
  code=$(curl -sk -o /dev/null -w '%{http_code}' -u "elastic:${ELASTIC_PASSWORD}" \
    -X PUT "https://localhost:9200/_security/role_mapping/enade_${service}" \
    -H 'Content-Type: application/json' -d "$body")
  [ "$code" = 200 ] || { echo "Falha ao mapear ${service}/${service} (HTTP $code)."; exit 1; }
done
echo "Principals api/api e worker/worker mapeados para enade_api_role e enade_worker_role."
