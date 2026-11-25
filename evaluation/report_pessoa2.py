"""Gera DOCX e manifesto somente a partir de evidências coletadas."""
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess

from docx import Document
from docx.shared import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "entrega_pessoa_2"


def read_json(name):
    return json.loads((OUT / name).read_text())


def paragraph(document, text):
    document.add_paragraph(text)


def table(document, headers, rows):
    element = document.add_table(rows=1, cols=len(headers))
    element.style = "Light Shading Accent 1"
    for cell, header in zip(element.rows[0].cells, headers):
        cell.text = str(header)
    for row in rows:
        for cell, value in zip(element.add_row().cells, row):
            cell.text = str(value)


def main():
    metrics = list(csv.DictReader((OUT / "redis_metricas.csv").open()))
    checks = read_json("verificacoes.json")
    api = read_json("kerberos_api.json")
    worker = read_json("kerberos_worker.json")
    browser = read_json("navegador_verificacoes.json")
    kerberos_text = (
        "AUTENTICAÇÃO KERBEROS REAL — laboratório Docker\n"
        "Não foram usados mocks. Keytabs e tickets não são incluídos.\n"
        "Identidades retornadas pelo Elasticsearch via SPNEGO, metadados Kafka via GSSAPI "
        "e klist de cada principal:\n\n" + json.dumps([api, worker], ensure_ascii=False, indent=2)
        + "\nLimites: LDAP autentica pessoas; Redis usa autenticação própria. "
        "A licença Elastic trial é exclusiva deste laboratório e expira.\n"
    )
    (OUT / "teste_kerberos.txt").write_text(kerberos_text)
    document = Document()
    normal = document.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    document.add_heading("ENADE — API, busca, cache e segurança", 0)
    paragraph(document, "Entrega da pessoa 2 • Seções 5, 6 e 7")
    paragraph(document, "Responsável no escopo informado: João Victor. Documento gerado a partir dos registros de execução, sem assinatura ou atestado de autoria pessoal.")
    paragraph(document, "Coleta em " + datetime.now(timezone.utc).isoformat() + " (UTC).")
    document.add_heading("Escopo e método", 1)
    paragraph(document, "Validação de laboratório com FastAPI, React/Vite, Elasticsearch 8.14.3, Redis 7, OpenLDAP, MIT Kerberos e Kafka 3.8.1 reais. O índice contém 18 questões sintéticas em três áreas; nenhum PDF ou questão oficial do acervo foi fornecido. Os resultados não demonstram completude do acervo, relevância em produção, alta disponibilidade ou desempenho sob carga.")
    paragraph(document, "Testes unitários usam doubles e são identificados como tal. A coleta integrada e o Chromium acessam serviços reais. Credenciais são geradas localmente, nunca incluídas nos arquivos. Capturas do Swagger têm somente credenciais removidas; respostas e códigos HTTP são preservados.")
    document.add_heading("5. Busca e API", 1)
    paragraph(document, "A relação de rotas foi extraída do OpenAPI em execução e salva em rotas_api.csv, acompanhada de openapi.json. Foram exercitados busca textual, oito filtros combinados, paginação sem sobreposição e highlight com <mark>. O mesmo tema foi recuperado em Computação, Saúde e Engenharias: isso comprova busca textual transversal às áreas, não um modelo semântico interdisciplinar.")
    search_checks = [row for row in checks if row["teste"].startswith(("01", "02", "03", "04", "05", "14"))]
    table(document, ["Verificação", "Resultado"], [(row["teste"], row["resultado"]) for row in search_checks])
    paragraph(document, "As exportações JSON e PDF foram baixadas por professor, tiveram conteúdo validado e foram negadas ao estudante com HTTP 403. O PDF inclui as questões e alternativas selecionadas; não se afirma que inclua figuras ou gabarito. Ver teste_exportacao.txt, exportacao.json e exportacao.pdf.")
    document.add_heading("Latência de busca", 2)
    paragraph(document, "Medição com relógio monotônico, um cliente sequencial, 100 amostras por modo e RTT HTTP na rede interna Docker. Modo cold: cache de busca invalidado por professor antes de cada requisição; não significa cache de disco/JVM frio. Modo warm: consulta previamente aquecida. Percentis calculados por interpolação linear, incluindo tempos de todas as respostas; erros HTTP são contados separadamente. A amostra de p99 é pequena e não permite promessas de SLA.")
    table(document, ["Modo", "n", "p50 (ms)", "p95 (ms)", "p99 (ms)", "Erros"],
          [(row["modo"], row["amostras"], row["p50_ms"], row["p95_ms"], row["p99_ms"], row["erros_http"]) for row in metrics])
    document.add_heading("6. Cache e sessão", 1)
    paragraph(document, "A chave do cache inclui os parâmetros e o perfil. O teste aquece o cache como professor e consulta depois como estudante, verificando que answer_key não vaze. O TTL de busca é 60 segundos. O carrinho é um conjunto Redis com namespace por usuário e sessão e TTL de 86.400 segundos.")
    table(document, ["Modo", "Hits", "Misses", "Hit rate"],
          [(row["modo"], row["hits"], row["misses"], f'{float(row["hit_rate"]):.2%}') for row in metrics])
    paragraph(document, "O hit rate é delta keyspace_hits / (delta keyspace_hits + delta keyspace_misses), obtido de INFO stats antes/depois de cada série em laboratório isolado. Esses contadores são globais da instância e não devem ser interpretados como exclusivos da busca em produção com outros clientes.")
    paragraph(document, (OUT / "teste_carrinho.txt").read_text())
    document.add_heading("7. Segurança LDAP e Kerberos", 1)
    paragraph(document, "O login foi executado contra OpenLDAP real. A API faz bind de serviço para localizar o DN, bind com a identidade do usuário e consulta de grupos para determinar ESTUDANTE ou PROFESSOR. O perfil foi confirmado por GET /auth/me, e não por uma imagem isolada do formulário de login.")
    paragraph(document, "A matriz em teste_perfis_403.txt distingue sem login (401), estudante autenticado (403) e professor autorizado (200). As respostas de busca e de detalhe do estudante não incluem answer_key. Os prints do Swagger registram a identidade e o retorno da rota protegida para cada perfil. O frontend confirma o perfil no servidor mesmo após tentativa de alterar o perfil no localStorage.")
    table(document, ["Principal", "Resultado Kerberos", "Serviços"],
          [(api["principal_esperado"], api["resultado"], "Elasticsearch/SPNEGO e Kafka/GSSAPI"),
           (worker["principal_esperado"], worker["resultado"], "Elasticsearch/SPNEGO e Kafka/GSSAPI")])
    paragraph(document, "A identidade do Elasticsearch é a retornada por /_security/_authenticate sob negociação SPNEGO com autenticação mútua e certificado validado. A API é somente leitura; tentativa controlada de escrita é negada com 403. Requisição sem ticket é negada com 401. Kafka retorna metadados pelo cliente configurado exclusivamente para SASL/GSSAPI; os tickets de serviço aparecem no klist.")
    paragraph(document, "As autenticações podem ter sido coletadas em etapas independentes para reduzir uso de RAM; seus horários estão registrados e não demonstram execução simultânea de todos os serviços. Kerberos não foi atribuído indevidamente ao Redis ou ao LDAP. Limites de segurança do laboratório: LDAP sem TLS e Kafka SASL_PLAINTEXT não fornecem confidencialidade de transporte; keytabs são compartilhados entre containers confiáveis no Compose atual; o JWT fica em localStorage e requer atenção a XSS. Para produção: LDAPS/StartTLS, SASL_SSL, volumes individuais de keytabs, gestão e rotação de credenciais, renovação de tickets e avaliação do armazenamento de sessão. A licença Elastic trial não é licença de produção.")
    document.add_heading("Evidências visuais", 1)
    for filename, caption in [
        ("prints_swagger/02_estudante_403.png", "Estudante autenticado: rota de professor retorna HTTP 403."),
        ("prints_swagger/04_professor_200.png", "Professor autenticado: mesma rota retorna HTTP 200."),
    ]:
        path = OUT / filename
        if path.exists():
            paragraph(document, caption)
            document.add_picture(str(path), width=Inches(6))
    document.add_heading("Correções e reprodução", 1)
    paragraph(document, "O PR corrige o import do cliente Elasticsearch, filtros do analisador brasileiro, inicialização do KDC e permissões de leitura dos keytabs, dependência de certificados do Elasticsearch, interpolação do healthcheck Docker, conflito de configuração Kafka, privilégios mínimos de ping, falso positivo do health LDAP e inserção de questões inexistentes no carrinho. No frontend, corrige confirmação de identidade, limpeza de dados ao sair, paginação e requisição autenticada de indicadores.")
    paragraph(document, "Reproduzir em um laboratório novo conforme entrega_pessoa_2/README.md. Scripts recusam popular um índice não vazio. Nenhum comando de destruição de volumes ou invalidação em produção foi utilizado. A invalidação de cache e o reinício Redis ocorreram somente na instância descartável desta execução.")
    document.add_heading("Matriz final", 1)
    table(document, ["Teste", "Estado"], [(row["teste"], row["resultado"]) for row in checks])
    paragraph(document, f"Verificações do navegador registradas: {len(browser)}. Resultados unitários em pytest.txt e build em frontend_build.txt. Hashes e origem da execução em manifesto.json.")
    document.save(OUT / "texto_secoes_5_6_7.docx")
    source_files = list((ROOT / "app").rglob("*.py")) + list((ROOT / "tests").rglob("*.py"))
    source_files += [ROOT / "docker-compose.yml", ROOT / "frontend/src.jsx"]
    source_files += list((ROOT / "evaluation").glob("*.py")) + list((ROOT / "evaluation").glob("*.yml"))
    source_files += [path for path in (ROOT / "infra").rglob("*") if path.is_file()]
    manifest = {
        "coleta_utc": datetime.now(timezone.utc).isoformat(),
        "repositorio": "https://github.com/LopesLarissak/ENADE",
        "git_head_no_momento_do_relatorio": os.getenv("EVAL_SOURCE_COMMIT", "consultar hashes dos arquivos-fonte"),
        "dados": "18 fixtures sintéticas, não oficiais; 3 áreas e 3 cursos",
        "ambiente": os.getenv("EVAL_ENVIRONMENT", "Docker local com aproximadamente 1.5 GiB RAM; worker efêmero"),
        "memoria_docker_bytes": read_json("memoria_docker_bytes.json") if (OUT / "memoria_docker_bytes.json").exists() else None,
        "python_relatorio": platform.python_version(),
        "segredos_incluidos": False,
        "arquivos_fonte_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                  for p in sorted(set(source_files))},
        "evidencias_sha256": {str(p.relative_to(OUT)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in sorted(OUT.rglob("*")) if p.is_file() and p.name != "manifesto.json"},
    }
    (OUT / "manifesto.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print("Relatório e manifesto gerados a partir dos arquivos de evidência.")


if __name__ == "__main__":
    main()
