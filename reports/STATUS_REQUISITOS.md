# Segurança Kerberos e serviços ENADE

## Requisito RF22 implementado na arquitetura

- Kafka exige SASL/GSSAPI e autentica `api/api`, `worker/worker` e o broker `kafka/kafka`.
- Elasticsearch usa realm Kerberos/SPNEGO no endpoint HTTP, HTTPS com certificado, e keytab exclusivo `HTTP/elasticsearch@ENADE.LOCAL`.
- API e worker obtêm tickets com keytabs individuais e usam SPNEGO com autenticação mútua ao acessar Elasticsearch.
- O Elasticsearch mapeia `api/api` para leitura e `worker/worker` para indexação.
- O tráfego interno HTTP do Elasticsearch é substituído por HTTPS; não publicar a porta 9200 no host.

## Outros componentes

Redis Open Source não implementa autenticação Kerberos nativa. Não é correto afirmar que ele está protegido por Kerberos: nesta configuração ele exige senha forte (AUTH), não publica a porta no host e fica acessível somente pela rede Docker. Para produção, habilite TLS e ACLs nomeadas; a senha simples não cifra o tráfego. OpenLDAP é o diretório de identidade para as pessoas; sua integração SASL/GSSAPI exige configurar o servidor slapd com Cyrus SASL e o principal `ldap/<hostname>`, além de TLS. O login LDAP simples atual não passa automaticamente a usar Kerberos apenas porque existe um KDC.

## Principals e permissões

| Principal | Serviço | Permissões Elasticsearch |
|---|---|---|
| `kafka/kafka@ENADE.LOCAL` | Broker Kafka | Não acessa ES |
| `api/api@ENADE.LOCAL` | API | Leitura do índice ENADE |
| `worker/worker@ENADE.LOCAL` | Worker | Criar índice e indexar documentos |
| `HTTP/elasticsearch@ENADE.LOCAL` | Elasticsearch HTTP | Aceita tickets SPNEGO |

## Inicialização e verificação

```bash
cp .env.example .env
openssl rand -hex 32  # API_SECRET
openssl rand -hex 32  # KRB5_KDC_MASTER_PASSWORD
docker compose config
docker compose up -d --build
docker compose ps
docker compose logs --tail=150 kerberos elasticsearch kafka api worker
docker compose exec api klist
docker compose exec worker klist
```

Teste o acesso autenticado ao Elasticsearch a partir dos containers: `python -c 'from app.kerberos_elasticsearch import KerberosElasticsearch; c=KerberosElasticsearch(); print(c.ping())'`. A verificação mútua é exigida pelo `HTTPSPNEGOAuth` e o certificado é validado pela CA montada.

## Limitações e validação

A autenticação Kerberos do Elasticsearch atua na camada HTTP; ela não substitui TLS de transporte entre nós. O Compose usa nó único para laboratório. O realm Kerberos e o mapeamento de roles precisam ser confirmados na versão/licença Elastic efetivamente executada. Redis e LDAP não devem ser descritos como Kerberos sem a respectiva configuração nativa. Executar testes integrados no Codespace antes de declarar RF22 concluído.


## Executado

| Verificação | Resultado |
|---|---|
| `python -m compileall -q app tests evaluation` | OK |
| `python -m pytest -q tests/test_extractor.py tests/test_models.py` | 5 passed |
| Leitura de `docker-compose.yml` com parser YAML | OK; 8 serviços reconhecidos |
| Verificação de dependências Python instaladas no ambiente de auditoria | Parcial; dependências de infraestrutura ausentes |

## Bloqueios do ambiente de auditoria

- `docker` não está instalado neste ambiente; não foi possível subir Kafka, Elasticsearch, Redis, OpenLDAP, API ou frontend.
- Não há acesso à internet para instalar os pacotes ausentes.
- A coleta integral do acervo ENADE não pode ser comprovada sem os PDFs originais e seus metadados.
- O teste integral `pytest -q` não concluiu a coleta: faltam `elasticsearch` e `ldap3` neste ambiente de auditoria. O Dockerfile instala as dependências listadas em `requirements.txt`, mas isso ainda precisa ser validado no Codespace.
- Build do Vite não foi executado porque `frontend/node_modules` não está presente e o ambiente não consegue baixar pacotes.

## Próxima validação obrigatória no Codespace

```bash
cp .env.example .env
# Gere e configure API_SECRET antes de subir:
openssl rand -hex 32

docker compose config
docker compose up -d --build
docker compose ps
docker compose logs --tail=150 api worker

docker compose exec api pytest -q
docker compose exec frontend npm run build
bash scripts/smoke_test.sh
```

O smoke test deve demonstrar explicitamente o HTTP 403 para estudante na rota `/analytics/courses` e HTTP 200 para professor.

**Importante:** RF22 (Kerberos/SASL-GSSAPI), conversão semântica de mídia (RF04), acervo completo (RF01) e métricas de desempenho/resiliência ainda não podem ser declarados concluídos. O Compose atual é uma topologia local de laboratório, não uma implantação de alta disponibilidade.
