# Entrega PARCIAL — não representa 14/14 testes aprovados

Elasticsearch não ficou saudável em 600 segundos. As sondagens HTTP abaixo foram feitas após sua parada; 503 é evidência de dependência indisponível, não aprovação nem diagnóstico de defeito na busca.

| Requisito | Estado |
|---|---|
| 01 Swagger e rotas | APROVADO |
| 02 Busca textual | BLOQUEADO |
| 03 Filtros combinados | BLOQUEADO |
| 04 Paginação e highlight | BLOQUEADO |
| 05 Busca interdisciplinar | BLOQUEADO |
| 06 Latência p50/p95/p99 | BLOQUEADO |
| 07 Hit rate Redis da busca | BLOQUEADO |
| 08 Carrinho e persistência | PARCIAL |
| 09 Login de estudante | APROVADO |
| 10 Login de professor | APROVADO |
| 11 Bloqueio de gabarito | BLOQUEADO |
| 12 HTTP 403 | APROVADO |
| 13 Kerberos entre serviços | PARCIAL |
| 14 Exportações JSON/PDF | PARCIAL |

Os CSVs de métricas têm somente cabeçalho, sem valores inventados. Capturas parciais comprovam identidade, perfil e 403; não comprovam a busca. Reexecutar `bash evaluation/run_lab_staged.sh` em laboratório NOVO com 4 GiB ou mais é a recomendação para completar a validação, não uma garantia de sucesso. Não é necessário autorizar GitHub Actions para executar localmente.
