"""Coleta evidências reais da API. Não exporta credenciais nem usa mocks."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

from redis import Redis
from evaluation.benchmark import percentile

OUT = Path("/app/entrega_pessoa_2")
BASE = os.getenv("EVAL_API_URL", "http://api:8000").rstrip("/")
RESULTS = []


def write_json(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def csv_file(name, rows, fields=None):
    with (OUT / name).open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def request(path, bearer=None, method="GET", data=None):
    headers = {"Content-Type": "application/json"}
    if bearer:
        headers["Authorization"] = "Bearer " + bearer
    payload = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(BASE + path, data=payload, method=method, headers=headers)
    start = time.perf_counter()
    try:
        response = urllib.request.urlopen(req, timeout=30)
    except urllib.error.HTTPError as exc:
        response = exc
    raw = response.read()
    elapsed = (time.perf_counter() - start) * 1000
    if "json" in response.headers.get("Content-Type", ""):
        body = json.loads(raw)
    elif "application/pdf" in response.headers.get("Content-Type", ""):
        body = raw
    else:
        body = raw.decode("utf-8", errors="replace")
    return response.status, body, elapsed


def check(name, passed, detail):
    RESULTS.append({"teste": name, "resultado": "APROVADO" if passed else "FALHOU", "detalhe": detail})
    print(name + ": " + RESULTS[-1]["resultado"])


def login(username, env_name):
    status, body, _ = request("/auth/login", method="POST",
                              data={"username": username, "password": os.environ[env_name]})
    if status != 200:
        raise RuntimeError(f"Login {username} retornou HTTP {status}; nenhuma credencial foi registrada.")
    return body["access_token"]


def text_report(name, records):
    (OUT / name).write_text(
        f"Coleta UTC: {datetime.now(timezone.utc).isoformat()}\n"
        "Ambiente: Docker Compose de laboratório, dados sintéticos, sem mocks.\n\n"
        + "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n"
    )


def kerberos(mode, service="all"):
    from app.kerberos_elasticsearch import KerberosElasticsearch
    from app.kafka_security import kafka_client_config
    from confluent_kafka.admin import AdminClient
    import requests
    evidence = {"principal_esperado": os.environ["KRB5_PRINCIPAL"], "modo": mode,
                "coleta_utc": datetime.now(timezone.utc).isoformat(), "etapa": service}
    if service == "kafka":
        try:
            metadata = AdminClient(kafka_client_config()).list_topics(timeout=30)
            evidence["kafka_gssapi"] = {"brokers": len(metadata.brokers), "topics": sorted(metadata.topics)}
            evidence["klist"] = subprocess.run(["klist"], capture_output=True, text=True, check=True).stdout
            evidence["resultado"] = "APROVADO" if metadata.brokers else "FALHOU"
        except Exception as exc:
            evidence["resultado"] = "BLOQUEADO"
            evidence["erro_tipo"] = type(exc).__name__
        write_json(f"kerberos_{mode}_kafka.json", evidence)
        print(f"Kerberos {mode}/Kafka: {evidence['resultado']}")
        return evidence
    client = KerberosElasticsearch()
    try:
        evidence["identidade_elasticsearch"] = client._request("GET", "/_security/_authenticate").json()
        evidence["leitura_indice"] = client.search(index="enade-questions", body={"size": 0})["hits"]["total"]
        anonymous = requests.get(client.url, verify=client.session.verify, timeout=10)
        evidence["elasticsearch_sem_ticket_http"] = anonymous.status_code
        if mode == "api":
            from app.kerberos_elasticsearch import ElasticsearchHTTPError
            try:
                # Operação não destrutiva em documento inexistente; deve ser barrada pelo RBAC.
                client._request("DELETE", "/enade-questions/_doc/lab-inexistente-autorizacao")
                evidence["escrita_api_http"] = "ERRO: permitida"
            except ElasticsearchHTTPError as exc:
                evidence["escrita_api_http"] = exc.status_code
        if service == "all":
            metadata = AdminClient(kafka_client_config()).list_topics(timeout=30)
            evidence["kafka_gssapi"] = {"brokers": len(metadata.brokers), "topics": sorted(metadata.topics)}
        else:
            evidence["etapa_kafka_anterior"] = json.loads((OUT / f"kerberos_{mode}_kafka.json").read_text())
            evidence["kafka_gssapi"] = evidence["etapa_kafka_anterior"].get("kafka_gssapi", {})
        evidence["klist"] = subprocess.run(["klist"], capture_output=True, text=True, check=True).stdout
        evidence["resultado"] = "APROVADO" if (
            evidence["identidade_elasticsearch"]["username"] == mode + "/" + mode
            and anonymous.status_code == 401
            and (mode != "api" or evidence["escrita_api_http"] == 403)
            and evidence["kafka_gssapi"].get("brokers", 0) > 0
            and (service == "all" or evidence["etapa_kafka_anterior"]["resultado"] == "APROVADO")
        ) else "FALHOU"
        if service == "all":
            write_json(f"kerberos_{mode}_kafka.json", {
                "principal_esperado": evidence["principal_esperado"], "modo": mode,
                "coleta_utc": evidence["coleta_utc"], "etapa": "kafka",
                "kafka_gssapi": evidence["kafka_gssapi"], "klist": evidence["klist"],
                "resultado": "APROVADO" if evidence["kafka_gssapi"]["brokers"] > 0 else "FALHOU",
            })
    except Exception as exc:
        # Exceções podem carregar URLs de infraestrutura; não incluir valores de configuração.
        evidence["resultado"] = "BLOQUEADO"
        evidence["erro_tipo"] = type(exc).__name__
    write_json(f"kerberos_{mode}.json", evidence)
    if mode == "worker" and evidence["resultado"] == "APROVADO":
        api_file = OUT / "kerberos_api.json"
        if api_file.exists():
            api_evidence = json.loads(api_file.read_text())
            if api_evidence.get("resultado") == "APROVADO":
                text_report("teste_kerberos.txt", [api_evidence, evidence])
    print(f"Kerberos {mode}: {evidence['resultado']}")
    return evidence


def collect(iterations):
    redis = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    status, schema, _ = request("/openapi.json")
    check("01 Swagger/OpenAPI", status == 200 and "paths" in schema, f"HTTP {status}")
    routes = []
    for path, methods in schema["paths"].items():
        for method, operation in methods.items():
            if method in {"get", "post", "delete", "put", "patch"}:
                routes.append({"metodo": method.upper(), "rota": path, "operation_id": operation["operationId"],
                               "parametros": ";".join(p["name"] for p in operation.get("parameters", []))})
    csv_file("rotas_api.csv", routes)
    write_json("openapi.json", schema)

    student = login("estudante", "EVAL_STUDENT_PASSWORD")
    teacher = login("professor", "EVAL_TEACHER_PASSWORD")
    identities = []
    for bearer, expected in [(student, "ESTUDANTE"), (teacher, "PROFESSOR")]:
        code, identity, _ = request("/auth/me", bearer)
        identities.append({"endpoint": "/auth/me", "http": code, "identidade": identity})
        check("09/10 Login " + expected, code == 200 and identity["role"] == expected, identity)
    invalid, _, _ = request("/auth/login", method="POST",
                            data={"username": "estudante", "password": secrets.token_hex(24)})
    injected, _, _ = request("/auth/login", method="POST",
                             data={"username": "*)(uid=*)", "password": secrets.token_hex(24)})
    check("LDAP rejeita login inválido e injeção", invalid == injected == 401,
          {"login_invalido": invalid, "filtro_escapado": injected})
    text_report("teste_ldap.txt", identities + [{"login_invalido_http": invalid, "injecao_http": injected}])
    write_json("autenticacao_validada.json", identities)

    code, found, _ = request("/questions?" + urllib.parse.urlencode({"q": "tecnologia", "size": 5}), student)
    check("02 Busca textual", code == 200 and found["total"] >= 1, {"http": code, "total": found.get("total")})
    write_json("resultado_busca.json", {"origem": "fixtures sintéticas, não acervo oficial", "http": code, "resposta": found})
    filters = {"q": "tecnologia", "area": "Computação", "course": "Sistemas de Informação",
               "year": 2021, "exam_type": "CE", "question_type": "objetiva", "competency": "Ética",
               "annulled": "false"}
    code, filtered, _ = request("/questions?" + urllib.parse.urlencode(filters), student)
    check("03 Filtros combinados", code == 200 and filtered["total"] > 0 and all(
        item["question"]["area"] == "Computação" and item["question"]["course"] == filters["course"]
        and item["question"]["year"] == 2021 and item["question"]["exam_type"] == "CE"
        and item["question"]["question_type"] == "objetiva" and not item["question"]["annulled"]
        and "Ética" in item["question"]["competencies"] for item in filtered["items"]),
        {"http": code, "total": filtered.get("total")})
    _, second, _ = request("/questions?q=tecnologia&page=2&size=5", student)
    ids = {item["id"] for item in found["items"]}
    second_ids = {item["id"] for item in second["items"]}
    highlighted = any("<mark>" in " ".join(item["highlight"].get("statement", [])) for item in found["items"])
    check("04 Paginação e highlight", bool(ids and second_ids) and ids.isdisjoint(second_ids) and highlighted,
          {"pagina1": sorted(ids), "pagina2": sorted(second_ids), "mark_presente": highlighted})
    _, interdisciplinary, _ = request("/questions?q=sustentabilidade&size=100", student)
    areas = sorted({item["question"]["area"] for item in interdisciplinary["items"]})
    check("05 Busca interdisciplinar", len(areas) >= 2, {"tema": "sustentabilidade", "areas": areas,
          "limite": "recuperação textual entre áreas; não comprova busca semântica"})
    write_json("busca_cenarios.json", {"filtros": {"parametros": filters, "resposta": filtered},
               "pagina2": second, "interdisciplinar": interdisciplinary})

    access = []
    for role, bearer in [("SEM_LOGIN", None), ("ESTUDANTE", student), ("PROFESSOR", teacher)]:
        status, body, _ = request("/analytics/courses", bearer)
        access.append({"perfil": role, "rota": "/analytics/courses", "http": status, "resposta": body})
        expected = {"SEM_LOGIN": 401, "ESTUDANTE": 403, "PROFESSOR": 200}[role]
        check("12 Acesso " + role, status == expected, {"http": status, "esperado": expected})
    _, teacher_results, _ = request("/questions?q=tecnologia&size=5", teacher)
    _, student_after_teacher, _ = request("/questions?q=tecnologia&size=5", student)
    no_leak = all("answer_key" not in item["question"] for item in student_after_teacher["items"])
    has_key = any(item["question"].get("answer_key") for item in teacher_results["items"])
    question_id = found["items"][0]["id"]
    _, student_detail, _ = request("/questions/" + question_id, student)
    check("11 Gabarito e isolamento do cache por perfil",
          no_leak and has_key and "answer_key" not in student_detail,
          {"estudante_sem_gabarito": no_leak, "professor_com_gabarito": has_key,
           "detalhe_estudante_sem_gabarito": "answer_key" not in student_detail})
    text_report("teste_perfis_403.txt", identities + access + [RESULTS[-1]])

    session = "evidencia-" + secrets.token_hex(6)
    status, added, _ = request("/cart/" + session, student, "POST", {"question_id": question_id})
    # Novo login e nova conexão HTTP; o carrinho é recuperado pela identidade + sessão.
    student_new = login("estudante", "EVAL_STUDENT_PASSWORD")
    _, persisted, _ = request("/cart/" + session, student_new)
    _, isolated, _ = request("/cart/" + session, teacher)
    missing, _, _ = request("/cart/" + session, student, "POST", {"question_id": "lab-inexistente"})
    ttl = redis.ttl("cart:estudante:" + session)
    check("08 Carrinho e persistência da sessão",
          status == 200 and question_id in added["items"] and question_id in persisted["items"]
          and not isolated["items"] and missing == 404 and 0 < ttl <= 86400,
          {"adicionar_http": status, "novo_login": persisted, "outro_usuario": isolated,
           "id_inexistente_http": missing, "ttl_s": ttl,
           "escopo": "persistência entre conexões e logins; reinício do Redis é testado separadamente"})
    text_report("teste_carrinho.txt", [RESULTS[-1]])
    (OUT / "cart_probe.json").write_text(json.dumps({"session_id": session, "question_id": question_id}))

    request("/cart/" + session, teacher, "POST", {"question_id": question_id})
    exports = []
    for kind in ["json", "pdf"]:
        denied, _, _ = request(f"/cart/{session}/export.{kind}", student)
        success, document, _ = request(f"/cart/{session}/export.{kind}", teacher)
        raw = json.dumps(document, ensure_ascii=False).encode() if kind == "json" else document
        valid = bool(document.get("questions")) if kind == "json" else raw.startswith(b"%PDF-")
        (OUT / ("exportacao." + kind)).write_bytes(raw)
        exports.append({"formato": kind, "estudante_http": denied, "professor_http": success,
                        "conteudo_valido": valid, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
        check("14 Exportação " + kind.upper(), denied == 403 and success == 200 and valid, exports[-1])
    text_report("teste_exportacao.txt", exports)

    samples = []
    metrics = []
    for mode in ["cold", "warm"]:
        if mode == "warm":
            request("/questions?q=tecnologia&size=10", teacher)
        before = redis.info("stats")
        measurements = []
        statuses = []
        for iteration in range(iterations):
            if mode == "cold":
                invalidation, _, _ = request("/admin/cache/invalidate", teacher, "POST")
                if invalidation != 200:
                    raise RuntimeError("Não foi possível invalidar o cache no laboratório.")
            status, _, elapsed = request("/questions?q=tecnologia&size=10", teacher)
            measurements.append(elapsed)
            statuses.append(status)
            samples.append({"modo": mode, "iteracao": iteration + 1, "latencia_ms": round(elapsed, 4), "http": status})
        after = redis.info("stats")
        hits = after["keyspace_hits"] - before["keyspace_hits"]
        misses = after["keyspace_misses"] - before["keyspace_misses"]
        metrics.append({"modo": mode, "amostras": iterations, "p50_ms": round(percentile(measurements, .50), 4),
                        "p95_ms": round(percentile(measurements, .95), 4), "p99_ms": round(percentile(measurements, .99), 4),
                        "hits": hits, "misses": misses, "hit_rate": hits / (hits + misses) if hits + misses else "",
                        "erros_http": sum(code != 200 for code in statuses)})
    csv_file("latencia_busca.csv", samples)
    csv_file("redis_metricas.csv", metrics)
    check("06 Latência p50/p95/p99", all(row["erros_http"] == 0 for row in metrics),
          {"resumo": metrics, "metodo": "sequencial, 1 cliente, RTT HTTP interno, 18 fixtures; não produção"})
    check("07 Hit rate Redis", metrics[1]["hits"] > 0 and metrics[0]["misses"] > 0,
          {"fonte": "delta INFO stats; laboratório sem tráfego concorrente", "resumo": metrics})
    evidence = kerberos("api", os.getenv("EVAL_KERBEROS_SERVICES", "all"))
    check("13 Kerberos real da API", evidence["resultado"] == "APROVADO",
          {"arquivo": "kerberos_api.json", "resultado": evidence["resultado"]})
    write_json("verificacoes.json", RESULTS)
    if any(row["resultado"] != "APROVADO" for row in RESULTS):
        raise SystemExit(1)
    snapshot = redis.info("stats")
    write_json("redis_snapshot.json", {
        "coleta_utc": datetime.now(timezone.utc).isoformat(),
        "escopo": "contadores globais da instância Redis no instante da coleta",
        "ping": redis.ping(), "keyspace_hits": snapshot["keyspace_hits"],
        "keyspace_misses": snapshot["keyspace_misses"], "chaves": redis.dbsize(),
    })
    unit = re.search(r"(\d+) passed", (OUT / "pytest.txt").read_text())
    write_json("validacoes_incluidas.json", {
        "escopo": "cenários aprovados da execução corrente",
        "testes_unitarios_aprovados": int(unit.group(1)) if unit else None,
        "verificacoes": RESULTS,
    })


def persistence():
    probe = json.loads((OUT / "cart_probe.json").read_text())
    bearer = login("estudante", "EVAL_STUDENT_PASSWORD")
    status, body, _ = request("/cart/" + probe["session_id"], bearer)
    record = {"teste": "Carrinho após reinício do processo Redis", "http": status,
              "preservado": probe["question_id"] in body.get("items", [])}
    with (OUT / "teste_carrinho.txt").open("a") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    if not record["preservado"]:
        raise SystemExit(1)
    print("Carrinho preservado após reinício real do Redis.")


def auth_only():
    """Evidência parcial independente do índice. Não aprova os demais testes."""
    status, schema, _ = request("/openapi.json")
    if status != 200:
        raise SystemExit("OpenAPI indisponível.")
    csv_file("rotas_api.csv", [
        {"metodo": method.upper(), "rota": path, "operation_id": operation["operationId"],
         "parametros": ";".join(p["name"] for p in operation.get("parameters", []))}
        for path, methods in schema["paths"].items() for method, operation in methods.items()
        if method in {"get", "post", "delete", "put", "patch"}
    ])
    write_json("openapi.json", schema)
    records = []
    for username, role, key in [("estudante", "ESTUDANTE", "EVAL_STUDENT_PASSWORD"),
                                 ("professor", "PROFESSOR", "EVAL_TEACHER_PASSWORD")]:
        bearer = login(username, key)
        code, identity, _ = request("/auth/me", bearer)
        assert code == 200 and identity == {"username": username, "role": role}
        records.append({"endpoint": "/auth/me", "http": code, "identidade": identity})
        if role == "ESTUDANTE":
            denied, body, _ = request("/analytics/courses", bearer)
            assert denied == 403
            records.append({"endpoint": "/analytics/courses", "http": denied, "perfil": role, "resposta": body})
    anonymous, _, _ = request("/analytics/courses")
    assert anonymous == 401
    invalid, _, _ = request("/auth/login", method="POST",
                            data={"username": "estudante", "password": secrets.token_hex(24)})
    assert invalid == 401
    records.append({"sem_login_http": anonymous, "login_invalido_http": invalid})
    text_report("teste_ldap.txt", records)
    text_report("teste_perfis_403.txt", records)
    write_json("autenticacao_validada.json", records)
    print("LDAP real: identidades e perfis confirmados; estudante 403, sem login 401, login inválido 401.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--kerberos", choices=["api", "worker"])
    parser.add_argument("--kerberos-service", choices=["all", "kafka", "elasticsearch"], default="all")
    parser.add_argument("--auth-only", action="store_true")
    parser.add_argument("--persistence", action="store_true")
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    if args.kerberos:
        if kerberos(args.kerberos, args.kerberos_service)["resultado"] != "APROVADO":
            raise SystemExit(1)
    elif args.auth_only:
        auth_only()
    elif args.persistence:
        persistence()
    else:
        collect(args.iterations)
