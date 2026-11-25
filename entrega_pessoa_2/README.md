# API, Redis e autenticação — evidências verificadas

Esta pasta documenta os cenários executados de rotas, identidade, perfis,
controle de acesso e autenticação entre serviços. Cada registro informa seu
escopo: testes unitários usam doubles identificados; registros HTTP e de
autenticação acessaram os serviços reais.

## Conteúdo

| Arquivo | Cenário documentado |
|---|---|
| `rotas_api.csv` / `openapi.json` | 14 operações da API em execução e esquema HTTP Bearer |
| `pytest.txt` | 33 testes unitários aprovados |
| `frontend_build.txt` | Build de produção React/Vite |
| `autenticacao_validada.json` / `teste_ldap.txt` | Login LDAP real e identidade/perfil de estudante e professor |
| `teste_perfis_403.txt` | Identidades, acesso autenticado, 401 e 403 |
| `kerberos_api_kafka.json` / `kerberos_worker_kafka.json` / `teste_kerberos.txt` | API e worker autenticados no Kafka por SASL/GSSAPI |
| `redis_snapshot.json` | PING e contadores globais no instante da coleta |
| `teste_carrinho.txt` | Leitura de carrinho vazio para os dois perfis |
| `teste_exportacao.txt` / `exportacao_vazia.*` | JSON/PDF de carrinho vazio e regras de acesso |
| `prints_swagger/` | Rotas, identidade/perfil e HTTP 403 reais |
| `prints_frontend/` | Identidade/perfil confirmados pela API no React |
| `navegador_verificacoes.json` | Verificações feitas no Chromium |
| `validacoes_incluidas.json` | Escopo das verificações incluídas |
| `texto_secoes_5_6_7.docx` | Texto das seções de API, Redis e segurança no escopo documentado |
| `manifesto.json` | Origem e hashes dos arquivos |

Os prints do Swagger preservam status e corpo da resposta e removem as
credenciais. O frontend usa o build React real, servido pelo preview leve
`evaluation/serve_frontend.py` com proxy para a API. O perfil exibido é confirmado
por `/auth/me`, inclusive após alteração do perfil no localStorage.

Os contadores Redis são globais da instância. Os arquivos de exportação e a
leitura de carrinho estão identificados expressamente como cenários vazios.

## Reprodução

Requisitos: Docker Engine/Desktop, Compose 2.24.4+, acesso aos registros de
imagens; 4 GiB de RAM ou mais são recomendados para o laboratório completo.
Use instalação nova e isolada, sem containers ENADE existentes com os mesmos
nomes ou portas.

```bash
# Na raiz do repositório:
bash evaluation/run_lab_staged.sh
```

O script gera credenciais aleatórias em `.env.evaluation` e um LDIF de
laboratório em `.evaluation-private/`, ambos ignorados pelo Git. Não imprime
credenciais, não remove volumes e recusa popular um índice não vazio.
As fixtures oferecidas pelo seed são explicitamente sintéticas.

Para coletar o escopo de autenticação, Redis e listas vazias desta pasta:

```bash
docker compose --env-file .env.evaluation \
  -f docker-compose.yml -f evaluation/compose.lab.yml \
  exec -T api python -m evaluation.collect_verified_pessoa2
```

Para as capturas de identidade e autorização, com API e frontend disponíveis:

```bash
docker build -f evaluation/Dockerfile.evidence -t enade-evidence-tools:local .
docker run --rm --network enade-plataforma_default --env-file .env.evaluation \
  -v "$PWD:/app" -w /app enade-evidence-tools:local \
  python -m evaluation.capture_pessoa2 --auth-only
docker run --rm -e EVAL_SOURCE_COMMIT="$(git rev-parse HEAD)" \
  -v "$PWD:/app" -w /app enade-evidence-tools:local \
  python -m evaluation.report_pessoa2
```

As evidências Kafka têm o horário e o principal de cada coleta. O modelo
opcional de GitHub Actions fica em `evaluation/github-actions-pessoa2.yml`.
Para ativá-lo pelo site do GitHub, copie seu conteúdo para
`.github/workflows/pessoa2.yml` na branch `entrega/pessoa-2-api-busca-seguranca`.
O evento do PR inicia a execução. Esse modelo usa heap de 512 MiB no
Elasticsearch e 256 MiB no Kafka, preserva os arquivos versionados fora da pasta
da nova coleta e publica somente artefatos da execução corrente aprovada.
Mensagens de erro do navegador passam por remoção de credenciais antes de
aparecerem nos logs. Credenciais de laboratório são geradas automaticamente:
não é necessário cadastrar senhas ou tokens nos secrets do Actions para esse fluxo.

## Revisão

Os colaboradores podem revisar conforme as permissões existentes no GitHub.
O PR não modifica regras de aprovação e não faz merge automático na `main`.
