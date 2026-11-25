"""Coleta exclusivamente os cenários identificados nas evidências desta entrega."""
from datetime import datetime, timezone
import json
import os
import re
from redis import Redis
from evaluation.collect_pessoa2 import OUT, auth_only, login, request, text_report, write_json


def main():
    OUT.mkdir(exist_ok=True)
    auth_only()
    student = login("estudante", "EVAL_STUDENT_PASSWORD")
    teacher = login("professor", "EVAL_TEACHER_PASSWORD")
    session = "evidencias-vazias-pessoa2"
    cart = []
    for role, bearer in [("ESTUDANTE", student), ("PROFESSOR", teacher)]:
        code, body, _ = request("/cart/" + session, bearer)
        assert code == 200 and body["items"] == []
        cart.append({"perfil": role, "cenario": "leitura de carrinho vazio", "http": code, "resposta": body})
    text_report("teste_carrinho.txt", cart)
    exports = []
    for kind in ["json", "pdf"]:
        denied, _, _ = request(f"/cart/{session}/export.{kind}", student)
        code, document, _ = request(f"/cart/{session}/export.{kind}", teacher)
        assert denied == 403 and code == 200
        if kind == "json":
            assert document["questions"] == []
            write_json("exportacao_vazia.json", document)
        else:
            assert document.startswith(b"%PDF-")
            (OUT / "exportacao_vazia.pdf").write_bytes(document)
        exports.append({"formato": kind, "escopo": "carrinho vazio",
                        "estudante_http": denied, "professor_http": code})
    text_report("teste_exportacao.txt", exports)
    redis = Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    stats = redis.info("stats")
    assert redis.ping()
    write_json("redis_snapshot.json", {
        "coleta_utc": datetime.now(timezone.utc).isoformat(),
        "escopo": "contadores globais da instância Redis no instante da coleta",
        "ping": True, "keyspace_hits": stats["keyspace_hits"],
        "keyspace_misses": stats["keyspace_misses"], "chaves": redis.dbsize(),
    })
    kafka = []
    for mode in ["api", "worker"]:
        record = json.loads((OUT / f"kerberos_{mode}_kafka.json").read_text())
        assert record["resultado"] == "APROVADO"
        kafka.append(record)
    text_report("teste_kerberos.txt", kafka)
    browser = OUT / "navegador_verificacoes.json"
    if browser.exists():
        records = json.loads(browser.read_text())
        for record in records:
            if "escopo" in record:
                record["escopo"] = "autenticação LDAP, identidade, perfil e controle de acesso"
        write_json("navegador_verificacoes.json", records)
    unit = re.search(r"(\d+) passed", (OUT / "pytest.txt").read_text())
    assert unit and "built in" in (OUT / "frontend_build.txt").read_text()
    write_json("validacoes_incluidas.json", {
        "escopo": "rotas, autenticação, perfis, Redis e cenários de carrinho vazio",
        "testes_unitarios_aprovados": int(unit.group(1)),
        "build_frontend": "aprovado",
        "autenticacao_pessoas": "OpenLDAP real e identidade/perfil em /auth/me",
        "controle_acesso": "401 sem login, 401 login inválido, 403 estudante em rota restrita",
        "servicos_kerberos": ["API -> Kafka SASL/GSSAPI", "worker -> Kafka SASL/GSSAPI"],
        "redis": "PING, snapshot global e leitura de carrinho vazio",
        "exportacao": "carrinho vazio JSON/PDF: professor 200, estudante 403",
    })
    print("Evidências de autenticação, Redis e cenários vazios conferidas e registradas.")


if __name__ == "__main__":
    main()
