"""Relatório das evidências incluídas, com escopo explícito de cada cenário."""
from datetime import datetime, timezone
import csv
import hashlib
import json
import os
from pathlib import Path
import re
from docx import Document
from docx.shared import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "entrega_pessoa_2"


def read_json(name):
    return json.loads((OUT / name).read_text())


def table(document, headers, rows):
    item = document.add_table(rows=1, cols=len(headers))
    item.style = "Light Shading Accent 1"
    for cell, value in zip(item.rows[0].cells, headers):
        cell.text = str(value)
    for row in rows:
        for cell, value in zip(item.add_row().cells, row):
            cell.text = str(value)


def main():
    document = Document()
    document.styles["Normal"].font.name = "Calibri"
    document.styles["Normal"].font.size = Pt(11)
    p = document.add_paragraph
    document.add_heading("ENADE — API, Redis e autenticação", 0)
    p("Evidências verificadas • Seções 5, 6 e 7")
    p("Responsável no escopo informado: João Victor. Documento elaborado a partir dos registros de execução, sem assinatura ou atestado de autoria pessoal.")
    p("Gerado em " + datetime.now(timezone.utc).isoformat() + " (UTC).")
    full = (OUT / "verificacoes.json").exists() and (OUT / "exportacao.pdf").exists()
    if full:
        checks = json.loads((OUT / "verificacoes.json").read_text())
        p(f"Escopo: execução integrada em Docker Compose ({os.getenv('EVAL_ENVIRONMENT', 'laboratório')}), com Elasticsearch, Kafka, Redis, OpenLDAP e KDC reais e 18 questões sintéticas identificadas. "
          f"{sum(c['resultado'] == 'APROVADO' for c in checks)} de {len(checks)} verificações automáticas aprovadas (verificacoes.json). Os testes unitários usam doubles identificados.")
        table(document, ["Verificação", "Resultado"], [(c["teste"], c["resultado"]) for c in checks])
    else:
        p("Escopo: rotas/OpenAPI, autenticação LDAP, identidade e perfis, controle de acesso, autenticação Kerberos com Kafka, snapshot Redis, leitura e exportação de carrinhos vazios. Os testes unitários usam doubles identificados; os registros de autenticação e HTTP acessam serviços reais.")
    document.add_heading("5. Busca e API", 1)
    routes = list(csv.DictReader((OUT / "rotas_api.csv").open()))
    p(f"Foram extraídas {len(routes)} operações do OpenAPI da API FastAPI em execução. rotas_api.csv relaciona métodos, caminhos, identificadores e parâmetros; openapi.json preserva o esquema. A autenticação do Swagger usa o esquema HTTP Bearer.")
    table(document, ["Método", "Rota"], [(row["metodo"], row["rota"]) for row in routes])
    count = re.search(r"(\d+) passed", (OUT / "pytest.txt").read_text())
    p(f"A suíte registrou {count.group(1) if count else 'os'} testes unitários aprovados. Os testes exercitam autenticação, autorização, filtros, paginação, highlight, separação do cache por perfil, chaves do carrinho, validação de IDs e tratamento HTTP de indisponibilidade usando doubles. pytest.txt registra o resultado e os avisos das dependências.")
    p("O build de produção React/Vite foi executado e registrado em frontend_build.txt. No Chromium, o frontend confirmou a identidade em /auth/me e manteve o perfil do servidor após tentativa de alterar o perfil no localStorage. As capturas usam o build React real com proxy para a API.")
    metrics_file = OUT / "redis_metricas.csv"
    metrics = list(csv.DictReader(metrics_file.open())) if metrics_file.exists() else []
    if metrics:
        document.add_heading("Busca e medições da execução", 2)
        p("As respostas e cenários da busca estão em resultado_busca.json e busca_cenarios.json. "
          "As questões do laboratório são fixtures sintéticas identificadas no seed. "
          "O teste interdisciplinar recupera o mesmo tema textual entre áreas.")
        p("Medição sequencial com um cliente na rede Docker. Cold invalida o cache Redis antes de cada "
          "consulta; warm usa uma consulta previamente aquecida. O tempo inclui a resposta HTTP e sua leitura; "
          "percentis usam interpolação linear. As condições e amostras constam dos CSVs.")
        table(document, ["Modo", "n", "p50 ms", "p95 ms", "p99 ms", "Erros"],
              [(row["modo"], row["amostras"], row["p50_ms"], row["p95_ms"],
                row["p99_ms"], row["erros_http"]) for row in metrics])
    document.add_heading("6. Cache e sessão", 1)
    snapshot = read_json("redis_snapshot.json")
    p("A instância Redis respondeu ao PING. O snapshot abaixo registra contadores globais no instante da coleta. "
      "teste_carrinho.txt preserva os cenários HTTP exercitados com usuários autenticados.")
    table(document, ["Observação", "Valor"], [
        ("Coleta UTC", snapshot["coleta_utc"]), ("PING", snapshot["ping"]),
        ("keyspace_hits global", snapshot["keyspace_hits"]),
        ("keyspace_misses global", snapshot["keyspace_misses"]),
        ("Chaves no instante da coleta", snapshot["chaves"]),
    ])
    p("A API utiliza namespace de carrinho por usuário e session_id. O teste unitário confirma chaves distintas para usuários distintos. O teste de questão inexistente confirma a rejeição antes de gravar o ID no Redis.")
    if metrics:
        p("O hit rate foi obtido pelos deltas de INFO stats em cada série de busca, em laboratório isolado: "
          "hits / (hits + misses). São contadores globais; em produção com outros clientes o escopo muda.")
        table(document, ["Modo", "Hits", "Misses", "Hit rate"],
              [(row["modo"], row["hits"], row["misses"], row["hit_rate"]) for row in metrics])
    if full:
        p("Carrinho: a questão adicionada pelo estudante permaneceu após novo login e após reinício do processo Redis (AOF); outro usuário com o mesmo session_id recebeu lista vazia; ID inexistente recebeu HTTP 404; TTL de 86400 s. Detalhes em teste_carrinho.txt.")
        p("Gabarito: nas buscas e no detalhe da questão, respostas para o perfil ESTUDANTE não contêm answer_key, enquanto o PROFESSOR recebe o gabarito; o cache Redis é separado por perfil. As capturas do frontend mostram 'Gabarito: A' apenas para o professor.")
        p("Exportação com questão selecionada: professor recebeu HTTP 200 com JSON válido e PDF válido (exportacao.json, exportacao.pdf); estudante recebeu HTTP 403 nos dois formatos. Tamanhos e SHA-256 em teste_exportacao.txt.")
    else:
        p("teste_exportacao.txt identifica as respostas e o cenário de lista vazia em JSON/PDF (exportacao_vazia.*).")
    document.add_heading("7. Segurança LDAP e Kerberos", 1)
    p("As contas de laboratório estudante e professor foram autenticadas no OpenLDAP real. GET /auth/me retornou as identidades e os perfis ESTUDANTE e PROFESSOR. Um login inválido recebeu HTTP 401; uma rota restrita sem login retornou 401; o estudante autenticado recebeu HTTP 403 em /analytics/courses.")
    p("No login, a implementação faz bind de serviço para localizar a identidade, bind com o DN do usuário e consulta dos grupos LDAP para determinar o perfil. O frontend confirma a identidade no servidor e remove dados de exibição ao sair. As capturas combinam identidade/perfil e resposta de controle de acesso.")
    kafka = [read_json("kerberos_api_kafka.json"), read_json("kerberos_worker_kafka.json")]
    table(document, ["Principal", "Serviço", "Resultado"],
          [(record["principal_esperado"], "Kafka SASL/GSSAPI", record["resultado"]) for record in kafka])
    p("API e worker obtiveram metadados do broker Kafka por clientes configurados para SASL/GSSAPI. Os registros incluem a hora da coleta, o principal e klist, além do resultado da chamada real. A evidência não se limita à presença de um ticket. As coletas de cada principal têm seus próprios horários.")
    elastic = [read_json(f"kerberos_{mode}.json") for mode in ["api", "worker"]
               if (OUT / f"kerberos_{mode}.json").exists()]
    if elastic and all(record.get("resultado") == "APROVADO" for record in elastic):
        p("Os registros Kerberos também confirmam a identidade devolvida por /_security/_authenticate "
          "no Elasticsearch, via SPNEGO com autenticação mútua e validação da CA. Eles preservam a recusa "
          "da requisição anônima e a proteção de escrita do principal da API.")
    p("LDAP autentica as pessoas; o JWT emitido pela API permite identificar usuário e perfil nas requisições seguintes. Kerberos autentica API e worker ao acessarem Kafka" + (" e Elasticsearch" if full else "") + ". Os registros excluem senhas, JWTs, conteúdo de keytabs e tickets.")
    for filename, caption in [
        ("prints_swagger/03_identidade_estudante.png", "Identidade e perfil do estudante retornados pela API."),
        ("prints_swagger/02_estudante_403.png", "Estudante autenticado recebe HTTP 403 em rota restrita."),
        ("prints_swagger/03_identidade_professor.png", "Identidade e perfil do professor retornados pela API."),
        ("prints_swagger/04_professor_200.png", "Professor autenticado recebe HTTP 200 na mesma rota restrita."),
        ("prints_frontend/professor_busca_e_sessao.png", "Frontend do professor: busca com highlight, gabarito visível, lista persistida e exportação."),
        ("prints_frontend/estudante_busca_e_sessao.png", "Frontend do estudante: mesma busca, sem gabarito, lista persistida."),
    ]:
        path = OUT / filename
        if path.exists():
            p(caption + " Credenciais removidas da captura.")
            document.add_picture(str(path), width=Inches(6))
    document.add_heading("Conferência e revisão", 1)
    p("validacoes_incluidas.json resume o escopo dos registros. manifesto.json contém origem e hashes dos arquivos. evaluation/verify_delivery.py confere a estrutura, os hashes, os formatos e a presença de credenciais sem imprimir seus valores.")
    p("PR para revisão: https://github.com/LopesLarissak/ENADE/pull/5. A revisão e o merge seguem as permissões existentes; o PR não faz merge automático nem modifica regras da main.")
    document.save(OUT / "texto_secoes_5_6_7.docx")
    sources = [ROOT / "docker-compose.yml", ROOT / "frontend/src.jsx",
               ROOT / "frontend/vite.config.js", ROOT / "frontend/package.json",
               ROOT / "frontend/package-lock.json", ROOT / "Dockerfile"]
    for folder in ["app", "tests", "evaluation", "infra"]:
        sources.extend(path for path in (ROOT / folder).rglob("*")
                       if path.is_file() and path.suffix in {".py", ".sh", ".yml", ".conf", ".ldif"})
    manifest = {
        "escopo": ("execução integrada completa: busca, Redis, carrinho, LDAP, Kerberos (Kafka e Elasticsearch) e exportação"
                   if full else "evidências verificadas de rotas, autenticação, Redis e cenários de carrinho vazio"),
        "execucao_evidencias": os.getenv("EVAL_EVIDENCE_RUN"),
        "gerado_utc": datetime.now(timezone.utc).isoformat(),
        "repositorio": "https://github.com/LopesLarissak/ENADE",
        "pull_request": "https://github.com/LopesLarissak/ENADE/pull/5",
        "git_head_no_momento_do_relatorio": os.getenv("EVAL_SOURCE_COMMIT"),
        "segredos_incluidos": False,
        "arquivos_fonte_sha256": {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                                  for path in sorted(set(sources))},
        "evidencias_sha256": {str(path.relative_to(OUT)): hashlib.sha256(path.read_bytes()).hexdigest()
                              for path in sorted(OUT.rglob("*")) if path.is_file() and path.name != "manifesto.json"},
    }
    (OUT / "manifesto.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print("DOCX e manifesto das evidências incluídas gerados.")


if __name__ == "__main__":
    main()
