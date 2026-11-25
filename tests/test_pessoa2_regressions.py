"""Testes UNITÁRIOS com doubles; não comprovam LDAP/Kerberos/Redis reais."""
import json
import secrets
from types import SimpleNamespace

from fastapi.testclient import TestClient
import jwt
import pytest

from app.api import main
from app.worker import consumer


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "API_SECRET", secrets.token_hex(32))
    return TestClient(main.app)


def authorization(role):
    value = jwt.encode({"sub": "unit-user", "role": role, "typ": "access", "exp": 4102444800},
                       main.API_SECRET, algorithm="HS256")
    return {"Authorization": "Bearer " + value}


def test_canonical_kerberos_import():
    from app.kerberos_elasticsearch import KerberosElasticsearch
    from app.kerberos_elastisearch import KerberosElasticsearch as legacy
    assert KerberosElasticsearch is legacy


def test_kafka_gssapi_config_includes_keytab(monkeypatch):
    from app.kafka_security import kafka_client_config
    monkeypatch.setenv("KRB5_KEYTAB", "/unit/worker.keytab")
    monkeypatch.setenv("KRB5_PRINCIPAL", "worker/worker@ENADE.LOCAL")
    config = kafka_client_config()
    assert config["sasl.kerberos.keytab"] == "/unit/worker.keytab"
    assert config["sasl.mechanism"] == "GSSAPI"


def test_swagger_declares_bearer_instead_of_ignored_authorization_header(client):
    schema = client.get("/openapi.json").json()
    assert schema["components"]["securitySchemes"]["HTTPBearer"]["scheme"] == "bearer"
    operation = schema["paths"]["/auth/me"]["get"]
    assert {"HTTPBearer": []} in operation["security"]
    assert not any(parameter["name"].lower() == "authorization"
                   for parameter in operation.get("parameters", []))


def test_health_ldap_false_is_degraded(monkeypatch, client):
    monkeypatch.setattr(main, "es", SimpleNamespace(ping=lambda: True))
    monkeypatch.setattr(main, "redis", SimpleNamespace(ping=lambda: True))
    monkeypatch.setattr(main, "AdminClient", lambda _: SimpleNamespace(list_topics=lambda **_: object()))
    monkeypatch.setattr(main, "_ldap_health", lambda: False)
    body = client.get("/health").json()
    assert body["services"]["ldap"] is False
    assert body["status"] == "degraded"


def test_missing_cart_question_is_not_stored(monkeypatch, client):
    monkeypatch.setattr(main, "es", SimpleNamespace(exists=lambda **_: False))
    monkeypatch.setattr(main, "redis", SimpleNamespace())  # sadd não pode ser chamado.
    response = client.post("/cart/unit-session", json={"question_id": "missing"},
                           headers=authorization("ESTUDANTE"))
    assert response.status_code == 404


def test_cart_keys_are_user_scoped():
    assert main.cart_key({"username": "one"}, "session") != main.cart_key({"username": "two"}, "session")


@pytest.mark.parametrize("path", ["/analytics/courses", "/analytics/competencies",
                                 "/analytics/competencies/timeline",
                                 "/cart/unit/export.json", "/cart/unit/export.pdf"])
def test_student_receives_http_403(client, path):
    assert client.get(path, headers=authorization("ESTUDANTE")).status_code == 403


@pytest.mark.parametrize("path", ["/auth/me", "/cart/unit", "/analytics/courses"])
def test_private_routes_require_login(client, path):
    assert client.get(path).status_code == 401


@pytest.mark.parametrize("path", ["/analytics/courses", "/analytics/competencies",
                                 "/analytics/competencies/timeline"])
def test_analytics_unavailable_returns_503(monkeypatch, client, path):
    def unavailable(**kwargs):
        raise ConnectionError("unit: dependência indisponível")
    monkeypatch.setattr(main, "es", SimpleNamespace(search=unavailable))
    response = client.get(path, headers=authorization("PROFESSOR"))
    assert response.status_code == 503


def test_search_filters_paging_highlight_and_profile_cache(monkeypatch, client):
    cache = {}
    queries = []

    def search(**kwargs):
        queries.append(kwargs["body"])
        return {"hits": {"total": {"value": 1}, "hits": [
            {"_id": "unit", "_source": {"statement": "tecnologia", "answer_key": "A"},
             "highlight": {"statement": ["<mark>tecnologia</mark>"]}}]}}

    monkeypatch.setattr(main, "es", SimpleNamespace(search=search))
    monkeypatch.setattr(main, "redis", SimpleNamespace(
        get=lambda key: cache.get(key), setex=lambda key, ttl, value: cache.__setitem__(key, value)))
    url = "/questions?q=tecnologia&course=Computacao&year=2021&annulled=false&page=2&size=5"
    teacher = client.get(url, headers=authorization("PROFESSOR")).json()
    student = client.get(url, headers=authorization("ESTUDANTE")).json()
    assert teacher["items"][0]["question"]["answer_key"] == "A"
    assert "answer_key" not in student["items"][0]["question"]
    assert student["items"][0]["highlight"]["statement"] == ["<mark>tecnologia</mark>"]
    assert len(cache) == 2
    assert queries[0]["from"] == 5 and queries[0]["size"] == 5
    assert {"term": {"annulled": False}} in queries[0]["query"]["bool"]["filter"]
    assert {"term": {"course": "Computacao"}} in queries[0]["query"]["bool"]["filter"]
    assert {"term": {"year": 2021}} in queries[0]["query"]["bool"]["filter"]
    client.get(url, headers=authorization("ESTUDANTE"))
    assert len(queries) == 2


def test_worker_defines_every_custom_analysis_filter(monkeypatch):
    payload = {}
    monkeypatch.setattr(consumer, "es", SimpleNamespace(indices=SimpleNamespace(
        exists=lambda **_: False, create=lambda **kwargs: payload.update(kwargs))))
    consumer.ensure_index()
    analysis = payload["settings"]["analysis"]
    filters = analysis["analyzer"]["ptbr_enade"]["filter"]
    assert set(filters) - {"lowercase"} <= analysis["filter"].keys()


@pytest.mark.parametrize("page,size", [(0, 10), (1, 0), (1, 101)])
def test_invalid_pagination_returns_422(client, page, size):
    assert client.get(f"/questions?page={page}&size={size}").status_code == 422
