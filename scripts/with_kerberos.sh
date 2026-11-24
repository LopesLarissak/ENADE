#!/bin/sh
set -eu

: "${KRB5_KEYTAB:?KRB5_KEYTAB não foi configurado}"
: "${KRB5_PRINCIPAL:?KRB5_PRINCIPAL não foi configurado}"
export KRB5_CONFIG="${KRB5_CONFIG:-/etc/krb5.conf}"
export KRB5CCNAME="${KRB5CCNAME:-FILE:/tmp/krb5cc_$(id -u)}"

if [ ! -r "$KRB5_KEYTAB" ]; then
  echo "Keytab Kerberos não encontrado ou sem permissão: $KRB5_KEYTAB" >&2
  exit 1
fi

kinit -kt "$KRB5_KEYTAB" "$KRB5_PRINCIPAL"
echo "Ticket Kerberos obtido para $KRB5_PRINCIPAL"
exec "$@"
