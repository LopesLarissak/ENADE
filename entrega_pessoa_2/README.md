# Entrega da pessoa 2 — API, busca, Redis e segurança

**ENTREGA PARCIAL. Não são 14/14 itens aprovados.** Leia primeiro
[`STATUS.md`](STATUS.md) e `verificacoes.json`. O Elasticsearch não ficou saudável
em 600 segundos, inclusive na tentativa sem Kafka. Há evidências reais de LDAP,
identidade/perfis, 401/403 e Kerberos no Kafka; as dependências do índice continuam
bloqueadas. Testes unitários e build não substituem esses testes integrados.

Esta pasta reúne os resultados da execução de laboratório descrita no PR.
Os arquivos são evidências, não modelos preenchidos com estimativas.

**Dados:** o script de seed oferece 18 questões sintéticas, em 3 cursos e 3 áreas,
mas **elas não foram indexadas nesta execução**, por causa do bloqueio do Elasticsearch.
Não houve comprovação de acervo oficial, extração de PDFs ou desempenho em produção.
Nenhuma senha, JWT, keytab ou arquivo `.env` deve fazer parte da entrega.

## Como ler

| Arquivo | Conteúdo |
|---|---|
| `rotas_api.csv` / `openapi.json` | Rotas e parâmetros extraídos da API executada |
| `resultado_busca.json` / `busca_cenarios.json` | Bloqueio e sondagens após parar a dependência; sem resultados fabricados |
| `latencia_busca.csv` | Somente cabeçalho: nenhuma medição válida de busca |
| `redis_metricas.csv` | Somente cabeçalho: percentis e hit rate de busca não medidos |
| `redis_snapshot.json` | PING e contadores globais; não são hit rate da busca |
| `teste_carrinho.txt` | Leitura vazia e inclusão bloqueada; persistência não aprovada |
| `teste_ldap.txt` | Identidade/perfil em `/auth/me` e rejeições de login |
| `teste_perfis_403.txt` | Sem login 401, estudante 403; consulta do professor ao índice e gabarito pendentes |
| `teste_kerberos.txt` / `kerberos_*.json` | Kafka/GSSAPI aprovado para API e worker; SPNEGO/Elasticsearch bloqueado |
| `teste_exportacao.txt` / `exportacao_vazia.*` | JSON/PDF reais, mas somente de carrinho vazio |
| `prints_swagger/` | Inventário, identidades e 403; credenciais removidas |
| `prints_frontend/` | Usuário/perfil confirmados; não comprovam busca ou carrinho |
| `navegador_verificacoes.json` | Verificações de autenticação no Chromium |
| `pytest.txt` / `frontend_build.txt` | Testes unitários e build Vite |
| `texto_secoes_5_6_7.docx` | Relatório PARCIAL das três seções, com resultados e bloqueios |
| `elasticsearch_diagnostico.json` | Prazo, estado e eventos selecionados sem credenciais |
| `manifesto.json` | Origem, condições e hashes para conferência |

`APROVADO` significa que a verificação correspondente passou nesta execução de
laboratório. Não é uma certificação de produção. Os testes em `tests/` usam
doubles; os coletores de evidências acessam serviços reais.

## Reprodução em ambiente novo

Requisitos: Docker Engine/Desktop, Compose **2.24.4+** (tags `!override`),
acesso aos registros de imagens e memória suficiente. Esta execução usou
aproximadamente 1,5 GiB disponíveis e limites reduzidos de JVM, sem conseguir
concluir a inicialização do Elasticsearch; **4 GiB ou mais são recomendados**.
Não execute em instalação de produção, nem no mesmo Docker
de outro ENADE com os mesmos nomes de containers ou portas.

```bash
# Na raiz do repositório, em laboratório novo e isolado:
bash evaluation/run_lab.sh
```

Para separar Kafka e Elasticsearch em etapas, o equivalente completo é:
`bash evaluation/run_lab_staged.sh`. Mesmo assim, Elasticsearch + Chromium
podem exceder a memória de ambientes muito pequenos. Os registros Kerberos
indicam o horário de cada etapa; não implicam execução simultânea.

O script cria `.env.evaluation` e `.evaluation-private/` ignorados pelo Git.
As credenciais são aleatórias e não são impressas. O LDIF de laboratório não
reutiliza as senhas de exemplo do repositório. A licença Elasticsearch `trial`
é habilitada somente no override de laboratório; sua validade é limitada.

O script recusa popular índice não vazio. Não remove volumes nem dados existentes.
Para repetir apenas a medição, com o laboratório já populado:

```bash
docker compose --env-file .env.evaluation \
  -f docker-compose.yml -f evaluation/compose.lab.yml \
  exec -T api python -m evaluation.collect_pessoa2 --iterations 100
```

Esse comando invalida cache **da instância de laboratório**, altera carrinhos
de teste e sobrescreve os resultados da coleta. A persistência após reinício
Redis é testada pelo script completo.

### Capturas e relatório

Execute depois da coleta, ainda com API e frontend disponíveis:

```bash
docker run --rm --network enade-plataforma_default \
  --env-file .env.evaluation -e EVAL_SOURCE_COMMIT="$(git rev-parse HEAD)" \
  -v "$PWD:/app" -w /app \
  mcr.microsoft.com/playwright/python:v1.55.0-noble \
  sh -c 'pip install -q -r evaluation/requirements-evidence.txt &&
         python -m evaluation.capture_pessoa2 &&
         python -m evaluation.report_pessoa2'
```

O navegador faz login real, confirma `/auth/me`, testa as rotas de ambos os perfis,
busca, carrinho após reload e downloads. Não salva HAR, traces, vídeos, senhas ou
JWTs. Os prints do Swagger ocultam o comando com Authorization e o campo de
credencial, preservando o status e a resposta HTTP. A interface exibe somente
identidade confirmada pelo servidor, inclusive após alteração de perfil no
localStorage.

O comando acima é o **modo completo**, ainda pendente de execução integral.
Nesta entrega foram usados `capture_pessoa2 --auth-only` e
`report_pessoa2 --partial`, para não simular os resultados dependentes do índice.
As capturas do frontend usam o **build React de produção real**, servido por
`evaluation/serve_frontend.py` com proxy para a API real, para reduzir a memória
do servidor de desenvolvimento. Não são telas reconstruídas ou resultados simulados.

Depois de qualquer nova execução, atualize também o teste Kerberos do worker e
o teste de reinício do Redis antes de gerar o relatório, para não misturar coletas.
O manifesto contém hashes; alterações posteriores exigem sua regeneração.

## Critérios e limitações

- **Latência:** 100 requisições por modo; um cliente; rede interna Docker;
  percentis por interpolação linear. `cold` significa cache Redis de busca
  invalidado, não disco/JVM frio. p99 com esta amostra não constitui SLA.
- **Hit rate:** delta de `INFO stats`; hits/(hits+misses); sem tráfego concorrente.
  Os contadores Redis são globais, não específicos de uma rota em produção.
- **Interdisciplinar:** busca textual do mesmo tema em várias áreas. Não
  comprova mecanismo semântico ou interdisciplinaridade pedagógica do acervo.
- **Sessão:** JWT identifica o usuário; Redis guarda o carrinho por usuário +
  `session_id`. O teste cobre novo login, reload e reinício do processo Redis,
  não perda de disco ou expiração acelerada de 24 horas.
- **Kerberos real:** `_security/_authenticate` identifica o principal do
  Elasticsearch; a requisição SPNEGO exige autenticação mútua e CA válida;
  Kafka fornece metadados via SASL/GSSAPI. `klist` sozinho não seria prova.
  Na execução em etapas, a autenticação de cada serviço é independente e
  possui seu próprio horário de coleta.
- **Segurança de laboratório:** LDAP sem TLS, Kafka `SASL_PLAINTEXT`, keytabs
  compartilhados entre containers confiáveis e JWT em localStorage são
  limitações declaradas. Redis e LDAP **não** são apresentados como serviços
  autenticados por Kerberos.
- **Autorização:** a API decide permissões. Esconder botão não substitui 403,
  e uma captura de login não substitui identidade + perfil + resposta autorizada.

## Revisão do PR

`evaluation/github-actions-pessoa2.yml` é um **modelo inativo**. Não há workflow
publicado em `.github/workflows/`: a conexão recusou a permissão `workflow`.
Isso não impede revisar ou aprovar o restante do PR.

Compare os scripts, os hashes e as evidências. Colaboradores podem revisar;
a aprovação e o merge obedecem às permissões e regras já existentes no GitHub.
Este trabalho não muda regras da branch nem faz merge automático.
