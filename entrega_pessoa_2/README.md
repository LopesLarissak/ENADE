# Entrega da pessoa 2 — API, busca, Redis e segurança

Esta pasta reúne os resultados da execução de laboratório descrita no PR.
Os arquivos são evidências, não modelos preenchidos com estimativas.

**Dados:** 18 questões explicitamente sintéticas, em 3 cursos e 3 áreas.
Não comprovam acervo oficial, qualidade da extração de PDFs nem desempenho em produção.
Nenhuma senha, JWT, keytab ou arquivo `.env` deve fazer parte da entrega.

## Como ler

| Arquivo | Conteúdo |
|---|---|
| `rotas_api.csv` / `openapi.json` | Rotas e parâmetros extraídos da API executada |
| `resultado_busca.json` / `busca_cenarios.json` | Respostas reais para as fixtures, filtros e paginação |
| `latencia_busca.csv` | Cada amostra HTTP, em milissegundos |
| `redis_metricas.csv` | Percentis, erros e hit rate por modo cold/warm |
| `teste_carrinho.txt` | Novo login, isolamento por usuário, TTL e reinício Redis |
| `teste_ldap.txt` | Identidade/perfil em `/auth/me` e rejeições de login |
| `teste_perfis_403.txt` | Sem login 401, estudante 403, professor 200 e proteção de gabarito |
| `teste_kerberos.txt` / `kerberos_*.json` | SPNEGO, identidade real, Kafka/GSSAPI e tickets por serviço |
| `teste_exportacao.txt` / `exportacao.*` | Respostas, validação, hashes, JSON e PDF de laboratório |
| `prints_swagger/` | Inventário, identidade e 403/200; credenciais removidas |
| `prints_frontend/` | Usuário/perfil confirmados, busca e carrinho após recarregar |
| `navegador_verificacoes.json` | Verificações feitas no Chromium |
| `pytest.txt` / `frontend_build.txt` | Testes unitários e build Vite |
| `texto_secoes_5_6_7.docx` | Texto das três seções com método, resultados e limitações |
| `manifesto.json` | Origem, condições e hashes para conferência |

`APROVADO` significa que a verificação correspondente passou nesta execução de
laboratório. Não é uma certificação de produção. Os testes em `tests/` usam
doubles; os coletores de evidências acessam serviços reais.

## Reprodução em ambiente novo

Requisitos: Docker Engine/Desktop, Compose **2.24.4+** (tags `!override`),
acesso aos registros de imagens e memória suficiente. Esta execução usou
aproximadamente 1,5 GiB disponíveis e limites reduzidos de JVM; **4 GiB ou mais
são recomendados**. Não execute em instalação de produção, nem no mesmo Docker
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
