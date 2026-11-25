"""Documenta bloqueios reais. Nunca converte falha/ausência de medição em aprovação."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path

from redis import Redis
from evaluation.collect_pessoa2 import OUT, auth_only, request, login, text_report, write_json, csv_file


def main():
    OUT.mkdir(exist_ok=True)
    auth_only()
    student = login("estudante", "EVAL_STUDENT_PASSWORD")
    teacher = login("professor", "EVAL_TEACHER_PASSWORD")
    context = ("Elasticsearch não ficou saudável em 600 segundos. As sondagens HTTP abaixo "
               "foram feitas após sua parada; 503 é evidência de dependência indisponível, "
               "não aprovação nem diagnóstico de defeito na busca.")
    probes = []
    for scenario, path in [
        ("textual", "/questions?q=tecnologia"),
        ("filtros", "/questions?q=tecnologia&area=Computacao&year=2021&annulled=false"),
        ("paginacao_highlight", "/questions?q=tecnologia&page=2&size=5"),
        ("interdisciplinar", "/questions?q=sustentabilidade"),
    ]:
        code, body, _ = request(path, student)
        probes.append({"cenario": scenario, "rota": path, "http": code, "resposta": body})
    write_json("resultado_busca.json", {"estado": "BLOQUEADO", "contexto": context, "sondagens": probes})
    write_json("busca_cenarios.json", {"estado": "BLOQUEADO", "sondagens": probes})
    # Somente cabeçalhos: nenhum percentil ou hit rate de busca foi coletado.
    csv_file("latencia_busca.csv", [], ["modo", "iteracao", "latencia_ms", "http"])
    csv_file("redis_metricas.csv", [], ["modo", "amostras", "p50_ms", "p95_ms", "p99_ms",
                                      "hits", "misses", "hit_rate", "erros_http"])
    redis = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    stats = redis.info("stats")
    write_json("redis_snapshot.json", {
        "coleta_utc": datetime.now(timezone.utc).isoformat(),
        "escopo": "snapshot global da instância; NÃO mede hit rate da busca",
        "ping": redis.ping(), "keyspace_hits": stats["keyspace_hits"],
        "keyspace_misses": stats["keyspace_misses"], "chaves": redis.dbsize(),
    })
    cart = []
    session = "parcial-sem-indice"
    for name, bearer in [("ESTUDANTE", student), ("PROFESSOR", teacher)]:
        code, body, _ = request("/cart/" + session, bearer)
        cart.append({"perfil": name, "operacao": "ler carrinho vazio", "http": code, "resposta": body})
    code, body, _ = request("/cart/" + session, student, "POST", {"question_id": "nao-inserida-sem-indice"})
    cart.append({"operacao": "adicionar", "http": code, "resposta": body})
    cart.append({"estado": "BLOQUEADO", "limite": "Não se comprovou inclusão, persistência, isolamento com itens ou TTL."})
    text_report("teste_carrinho.txt", cart)
    access = []
    for role, bearer in [("SEM_LOGIN", None), ("ESTUDANTE", student), ("PROFESSOR", teacher)]:
        code, body, _ = request("/analytics/courses", bearer)
        access.append({"perfil": role, "rota": "/analytics/courses", "http": code, "resposta": body})
    text_report("teste_perfis_403.txt", access + [{
        "limite": "403 do estudante comprovado; professor consultando índice e proteção de gabarito NÃO comprovados."}])
    exports = []
    for kind in ["json", "pdf"]:
        denied, _, _ = request(f"/cart/{session}/export.{kind}", student)
        code, document, _ = request(f"/cart/{session}/export.{kind}", teacher)
        exports.append({"formato": kind, "estudante_http": denied, "professor_http": code,
                        "escopo": "somente carrinho VAZIO; não comprova exportação de questões"})
        if code == 200:
            if kind == "json":
                write_json("exportacao_vazia.json", document)
            else:
                (OUT / "exportacao_vazia.pdf").write_bytes(document)
    text_report("teste_exportacao.txt", exports)
    kerberos_records = []
    for mode in ["api", "worker"]:
        kafka = json.loads((OUT / f"kerberos_{mode}_kafka.json").read_text())
        evidence = {"resultado": "PARCIAL", "principal_esperado": kafka["principal_esperado"],
                    "kafka_real": kafka, "elasticsearch_spnego": "BLOQUEADO: serviço não ficou saudável"}
        write_json(f"kerberos_{mode}.json", evidence)
        kerberos_records.append(evidence)
    text_report("teste_kerberos.txt", kerberos_records)
    states = [
        ("01 Swagger e rotas", "APROVADO", "14 operações extraídas do OpenAPI em execução."),
        ("02 Busca textual", "BLOQUEADO", context),
        ("03 Filtros combinados", "BLOQUEADO", context),
        ("04 Paginação e highlight", "BLOQUEADO", context),
        ("05 Busca interdisciplinar", "BLOQUEADO", context),
        ("06 Latência p50/p95/p99", "BLOQUEADO", "CSV contém somente cabeçalho; nenhuma latência aprovada foi medida."),
        ("07 Hit rate Redis da busca", "BLOQUEADO", "Somente PING e snapshot global; não há hit rate de busca."),
        ("08 Carrinho e persistência", "PARCIAL", "Leitura vazia 200; inclusão/persistência com itens bloqueadas."),
        ("09 Login de estudante", "APROVADO", "OpenLDAP real e /auth/me confirmam estudante/ESTUDANTE."),
        ("10 Login de professor", "APROVADO", "OpenLDAP real e /auth/me confirmam professor/PROFESSOR."),
        ("11 Bloqueio de gabarito", "BLOQUEADO", "Não houve resposta de busca com questões para testar vazamento."),
        ("12 HTTP 403", "APROVADO", "Estudante autenticado 403; sem login 401; professor não consultou índice."),
        ("13 Kerberos entre serviços", "PARCIAL", "API e worker no Kafka aprovados; Elasticsearch/SPNEGO não validado."),
        ("14 Exportações JSON/PDF", "PARCIAL", "Somente lista vazia: professor 200 e estudante 403; questões pendentes."),
    ]
    checks = [{"teste": name, "resultado": state, "detalhe": detail} for name, state, detail in states]
    write_json("verificacoes.json", checks)
    private = Path("/app/.evaluation-private")
    events = []
    for line in (private / "es-startup.log").read_text(errors="replace").splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        message = event.get("message", "")
        if message.startswith(("version[", "heap size [", "node name [", "Registered local node features",
                               "fatal exception", "Security is enabled", "started")):
            events.append({"utc": event.get("@timestamp"), "nivel": event.get("log.level"),
                           "evento": message[:300], "erro_tipo": event.get("error.type")})
    write_json("elasticsearch_diagnostico.json", {
        "prazo_espera_s": 600, "resultado": "application not healthy after 10m0s",
        "estado_ao_terminar": (private / "es-state.txt").read_text().strip(),
        "eventos_selecionados": events[-8:],
        "conclusao": "Não houve inicialização saudável no prazo. A causa única não foi confirmada.",
        "acoes": "Correções de configuração e várias tentativas, incluindo execução sem Kafka e JVM reduzida.",
    })
    (OUT / "STATUS.md").write_text(
        "# Entrega PARCIAL — não representa 14/14 testes aprovados\n\n"
        + context + "\n\n"
        "| Requisito | Estado |\n|---|---|\n"
        + "\n".join(f"| {name} | {state} |" for name, state, _ in states)
        + "\n\nOs CSVs de métricas têm somente cabeçalho, sem valores inventados. "
          "Capturas parciais comprovam identidade, perfil e 403; não comprovam a busca. "
          "Reexecutar `bash evaluation/run_lab_staged.sh` em laboratório NOVO com 4 GiB ou mais "
          "é a recomendação para completar a validação, não uma garantia de sucesso. "
          "Não é necessário autorizar GitHub Actions para executar localmente.\n")
    print("Entrega PARCIAL registrada; buscas e métricas permanecem explicitamente bloqueadas.")


if __name__ == "__main__":
    main()
