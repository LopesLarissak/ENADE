# Plataforma Distribuída de Busca e Indexação do Acervo ENADE

Projeto acadêmico em laboratório com Python/FastAPI, Apache Kafka (KRaft), Elasticsearch, Redis, OpenLDAP e React/Vite.

## 1. Requisitos locais
- Docker Desktop ou Docker Engine + Compose v2.
- Codespaces com pelo menos 4 GB de RAM recomendados (Elasticsearch consome memória).
- Git.

## 2. Configuração e inicialização

```bash
cp .env.example .env
# Gere um segredo forte e cole no campo API_SECRET do .env:
openssl rand -hex 32
# Suba o ambiente
docker compose up -d --build
# Acompanhe os serviços
docker compose ps
docker compose logs -f api worker
```

Aguarde o OpenLDAP concluir o bootstrap LDIF. Endereços:
- Frontend: http://localhost:5173
- API/Swagger: http://localhost:8000/docs
- Health: http://localhost:8000/health
- Elasticsearch: http://localhost:9200

**Contas exclusivamente para laboratório:** `estudante` / `Estudante@123` e `professor` / `Professor@123`. Troque as senhas e hashes LDAP antes de compartilhar o ambiente. O listener LDAP e Elasticsearch deste Compose são internos de laboratório, sem TLS/autenticação de transporte; não use em produção.

> Se o volume LDAP já foi inicializado antes de adicionar o LDIF, os arquivos de bootstrap não são reaplicados automaticamente. Em instalação descartável recém-criada, `docker compose down -v` remove os dados persistidos e permite inicializar do zero. **Esse comando apaga os volumes Kafka, Elasticsearch, Redis e LDAP. Não o execute se precisar preservar dados.**

## 3. Ingestão
Coloque PDFs em `data/pdfs/`. Exemplo:

```bash
docker compose exec api python -m app.ingestion.cli \
  --input /app/data/pdfs \
  --year 2021 \
  --course "Sistemas de Informação" \
  --area "Computação" \
  --exam-type CE
```

Gabarito e metadados podem ser associados por número da questão usando arquivos JSON externos:

```bash
# answer-key.json: {"01":"A", "02":"C"}
# metadata.json: {"01":{"competencies":["Ética"],"knowledge_objects":["Sociedade e tecnologia"]}}
docker compose exec api python -m app.ingestion.cli --input /app/data/pdfs \
  --year 2021 --course "Sistemas de Informação" --area "Computação" \
  --exam-type CE --answer-key /app/data/answer-key.json --metadata /app/data/metadata.json
```

O produtor publica JSON no tópico `enade.questions`; o worker valida, indexa no Elasticsearch e confirma o offset somente após indexação ou encaminhamento confirmado à DLQ `enade.questions.dlq`. O ID determinístico evita duplicação quando o mesmo PDF e conteúdo são reprocessados. O OCR é contingência para páginas sem camada textual e deve ser validado manualmente.

## 4. Usuários e segurança da API
- `POST /auth/login`: autenticação LDAP e emissão de JWT HS256.
- `GET /auth/me`: identidade e perfil do token.
- Estudante: busca sem campo `answer_key`.
- Professor: busca com gabarito, analytics, exportação e invalidação de cache.
- Rotas restritas retornam HTTP 403 para estudante e 401 sem autenticação.

Exemplo de teste manual:

```bash
STUDENT=$(curl -s -X POST http://localhost:8000/auth/login -H 'Content-Type: application/json' -d '{"username":"estudante","password":"Estudante@123"}' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
PROF=$(curl -s -X POST http://localhost:8000/auth/login -H 'Content-Type: application/json' -d '{"username":"professor","password":"Professor@123"}' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
curl -i http://localhost:8000/analytics/courses -H "Authorization: Bearer $STUDENT"  # esperado: 403
curl -i http://localhost:8000/analytics/courses -H "Authorization: Bearer $PROF"     # esperado: 200
```

## 5. Endpoints principais
| Método | Rota | Acesso |
|---|---|---|
| GET | `/health` | Público |
| POST | `/auth/login` | Público |
| GET | `/auth/me` | Autenticado |
| GET | `/questions` | Público ou autenticado; estudante sem gabarito |
| GET | `/questions/{id}` | Público ou autenticado; estudante sem gabarito |
| GET | `/analytics/courses` | Professor |
| GET | `/analytics/competencies` | Professor |
| GET | `/analytics/competencies/timeline` | Professor |
| POST/GET/DELETE | `/cart/{session_id}` | Autenticado; isolado por usuário |
| GET | `/cart/{session_id}/export.json` | Professor |
| GET | `/cart/{session_id}/export.pdf` | Professor |
| POST | `/admin/cache/invalidate` | Professor |

Busca aceita `q`, `area`, `course`, `year`, `exam_type`, `question_type`, `competency`, `annulled`, `page` e `size`.

## 6. Testes e experimentos

```bash
docker compose exec api pytest -q
# benchmark com token de professor (cache frio e aquecido)
docker compose exec api python evaluation/benchmark.py --url http://localhost:8000 --query tecnologia --iterations 100 --token "$PROF" --output /app/data/benchmark.csv
# instalar matplotlib no ambiente de avaliação e gerar gráfico
pip install -r evaluation/requirements.txt
python evaluation/plot_results.py data/benchmark.csv --output reports/latencia-cache.png
```

Amostra manual: preencher `evaluation/quality_sample_template.csv` com no mínimo 50 questões. O relatório-base está em `reports/RELATORIO_TECNICO.md`. Não inserir métricas estimadas: p50/p95/p99, docs/s, qualidade e perda/duplicação devem vir da execução real.

### Teste de resiliência
1. Inicie ingestão de um acervo maior e acompanhe `docker compose logs -f worker`.
2. Durante a ingestão, execute `docker compose stop worker`.
3. Aguarde e reinicie com `docker compose start worker`.
4. Compare IDs publicados com documentos indexados e verifique offsets; o consumidor usa commit manual.
5. Repita interrompendo temporariamente Elasticsearch. A falha de indexação não deve confirmar offset; mensagens inválidas encaminhadas com sucesso à DLQ podem ser confirmadas.
6. Salve logs, contagens antes/depois e horário de cada ação no relatório.

## 7. Topologia e limites declarados
Laboratório: 1 broker Kafka, 3 partições no tópico principal, 1 partição DLQ, Elasticsearch single-node/1 shard/0 réplicas, Redis standalone. Isso permite execução local e demonstra o pipeline, mas não oferece alta disponibilidade. Para produção, adotar múltiplos brokers, replicação, TLS, autenticação, backups, observabilidade e política de recuperação.

**Kerberos:** este pacote não declara RF22 concluído. A autenticação mútua Kafka–Elasticsearch–API via Kerberos exige KDC/realm, principals, keytabs, JAAS/SASL-GSSAPI no Kafka e uma configuração de segurança Elasticsearch compatível com o licenciamento/recursos da distribuição escolhida. Não simule esse requisito com um container KDC isolado. Antes da submissão, executar e registrar essa integração no ambiente-alvo ou declarar formalmente a limitação ao docente.

**Mídia:** o extrator registra imagens e páginas de origem e aplica OCR em páginas sem texto; elementos gráficos são sinalizados para revisão. A conversão semântica de diagramas para Mermaid e fórmulas de imagem para LaTeX ainda exige componente multimodal e validação humana. O campo `structured_media` identifica candidatos, não garante conversão correta.

## 8. Segurança no Git
- Nunca versionar `.env`, senhas reais, tokens, keytabs ou certificados privados.
- `.env.example` contém apenas valores de laboratório.
- `.dockerignore` exclui `.env`, keytabs e PDFs privados do contexto da imagem.
- Alterar as senhas de laboratório antes de disponibilizar o serviço.
