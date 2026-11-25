#!/bin/bash
set -euo pipefail

: "${KRB5_KDC_MASTER_PASSWORD:?Defina KRB5_KDC_MASTER_PASSWORD no .env}"
REALM="ENADE.LOCAL"
mkdir -p /var/lib/krb5kdc /keytabs /es-keytab /certs
chmod 0755 /keytabs

if [ ! -f /var/lib/krb5kdc/principal ]; then
  kdb5_util create -s -P "$KRB5_KDC_MASTER_PASSWORD" -r "$REALM"
fi

create_principal() {
  local principal="$1"
  # kadmin.local pode retornar zero mesmo quando o principal não existe.
  if ! kadmin.local -r "$REALM" -q "getprinc ${principal}" 2>/dev/null | grep -Fq "Principal: ${principal}"; then
    kadmin.local -r "$REALM" -q "addprinc -randkey -maxlife 10hours -maxrenewlife 7days ${principal}"
  fi
}

create_keytab() {
  local principal="$1"
  local file="$2"
  if [ ! -s "$file" ]; then
    kadmin.local -r "$REALM" -q "ktadd -k ${file} ${principal}"
    chmod 0444 "$file"
  fi
}

create_principal "kafka/kafka@${REALM}"
create_principal "api/api@${REALM}"
create_principal "worker/worker@${REALM}"
create_principal "HTTP/elasticsearch@${REALM}"
create_keytab "kafka/kafka@${REALM}" /keytabs/kafka.keytab
create_keytab "api/api@${REALM}" /keytabs/api.keytab
create_keytab "worker/worker@${REALM}" /keytabs/worker.keytab
create_keytab "HTTP/elasticsearch@${REALM}" /es-keytab/elasticsearch-http.keytab

if [ ! -s /certs/elasticsearch.key ] || [ ! -s /certs/elasticsearch.crt ]; then
  openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 825 \
    -keyout /certs/elasticsearch.key -out /certs/elasticsearch.crt \
    -subj "/CN=elasticsearch" \
    -addext "subjectAltName=DNS:elasticsearch,DNS:localhost,IP:127.0.0.1"
  chmod 0440 /certs/elasticsearch.key
  chmod 0444 /certs/elasticsearch.crt
fi
cp /certs/elasticsearch.crt /certs/ca.crt
chmod 0444 /certs/ca.crt

echo "KDC ENADE.LOCAL inicializado; principals kafka, api, worker e HTTP/elasticsearch disponíveis."
exec /usr/sbin/krb5kdc -n
