# Pessoa 2 — API, busca, Redis e segurança

Evidências geradas pela execução integrada do GitHub Actions
<https://github.com/LopesLarissak/ENADE/actions/runs/45702828715>
(Ubuntu 24.04, Docker Compose com Elasticsearch, Kafka, Redis, OpenLDAP e KDC
reais; 18 questões sintéticas identificadas como `FIXTURE_SINTETICA_NAO_OFICIAL`).
Resultado: 18 de 18 verificações automáticas aprovadas (`verificacoes.json`).

| Item | Evidência |
|---|---|
| 1. Rotas no Swagger | `rotas_api.csv`, `openapi.json`, `prints_swagger/01_rotas.png` |
| 2–5. Busca textual, filtros combinados, paginação/highlight, interdisciplinar | `resultado_busca.json`, `busca_cenarios.json`, `prints_frontend/` |
| 6. Latência p50/p95/p99 | `latencia_busca.csv` (200 amostras), resumo em `redis_metricas.csv` |
| 7. Hit rate Redis | `redis_metricas.csv`, `redis_snapshot.json` |
| 8. Carrinho e persistência da sessão | `teste_carrinho.txt` (novo login, isolamento, 404, TTL, reinício do Redis) |
| 9–10. Login estudante e professor | `teste_ldap.txt`, `autenticacao_validada.json`, `prints_swagger/03_*` |
| 11. Gabarito bloqueado para estudante | `verificacoes.json` (item 11), `prints_frontend/*_busca_e_sessao.png` |
| 12. HTTP 403 | `teste_perfis_403.txt`, `prints_swagger/02_estudante_403.png`, `04_professor_200.png` |
| 13. Kerberos real entre serviços | `teste_kerberos.txt`, `kerberos_api*.json`, `kerberos_worker*.json` |
| 14. Exportação JSON e PDF | `teste_exportacao.txt`, `exportacao.json`, `exportacao.pdf` |
| Texto das seções 5, 6 e 7 | `texto_secoes_5_6_7.docx` |
| Integridade | `manifesto.json` (SHA-256), conferido por `evaluation/verify_delivery.py` |

Medições: cliente único, sequencial, na rede Docker do runner; `cold` invalida o
cache antes de cada consulta e `warm` reutiliza a consulta aquecida. Não são
números de produção.

Identidade comprovada: cada captura de login é acompanhada da resposta de
`/auth/me` (usuário e perfil) e do acesso autorizado ou negado correspondente.
Senhas, JWTs, keytabs e tickets não aparecem em nenhum arquivo.

## Reprodução

O workflow `.github/workflows/pessoa2.yml` executa tudo a cada push na branch do
PR e publica a pasta como artefato `entrega-pessoa-2`. Localmente, com Docker e
4 GiB de RAM ou mais: `bash evaluation/run_lab.sh` (credenciais de laboratório são
geradas em `.env.evaluation`, ignorado pelo Git).
