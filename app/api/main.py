import hashlib
import io
import json
import logging
import secrets
import time
from typing import Optional

import jwt
from fastapi import FastAPI, HTTPException, Query, Header, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from app.kerberos_elasticsearch import KerberosElasticsearch, ElasticsearchHTTPError
from redis import Redis
from confluent_kafka.admin import AdminClient
from ldap3 import Server, Connection
from app.config import LDAP_HOST, LDAP_USER_DN, LDAP_PASSWORD
from app.kafka_security import kafka_client_config
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.config import (ELASTIC_URL, REDIS_URL, API_SECRET, API_TOKEN_TTL,
                        API_ALLOWED_ORIGINS)
from app.api.auth import authenticate_ldap

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI(title="ENADE Distribuído API", version="2.0.0",
              description="Plataforma distribuída de ingestão, indexação e busca do acervo ENADE.")
app.add_middleware(CORSMiddleware, allow_origins=API_ALLOWED_ORIGINS,
                   allow_credentials=True, allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
                   allow_headers=["Authorization", "Content-Type"])
es = KerberosElasticsearch(ELASTIC_URL, request_timeout=10)
redis = Redis.from_url(REDIS_URL, decode_responses=True)
INDEX = "enade-questions"

class LoginPayload(BaseModel):
    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=256)

class CartPayload(BaseModel):
    question_id: str = Field(min_length=1, max_length=128)


def user_from_header(authorization: Optional[str], required: bool = False):
    if not authorization:
        if required:
            raise HTTPException(401, "Autenticação necessária", headers={"WWW-Authenticate": "Bearer"})
        return {"username": "anonymous", "role": "ESTUDANTE"}
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Formato de autenticação inválido")
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, API_SECRET, algorithms=["HS256"])
        if payload.get("typ") != "access":
            raise ValueError("tipo de token inválido")
        return {"username": payload["sub"], "role": payload["role"]}
    except Exception:
        raise HTTPException(401, "Token inválido ou expirado")


def professor(authorization: Optional[str]):
    user = user_from_header(authorization, required=True)
    if user["role"] != "PROFESSOR":
        raise HTTPException(403, "Acesso restrito a professores")
    return user


def invalidate_search_cache():
    cursor = 0
    while True:
        cursor, keys = redis.scan(cursor=cursor, match="search:*", count=500)
        if keys:
            redis.delete(*keys)
        if cursor == 0:
            break


def _ldap_health():
    if not LDAP_PASSWORD:
        raise RuntimeError("LDAP service password is not configured")
    conn = Connection(Server(LDAP_HOST, connect_timeout=2), user=LDAP_USER_DN,
                      password=LDAP_PASSWORD, receive_timeout=2)
    try:
        return conn.bind()
    finally:
        conn.unbind()


@app.get("/health")
def health():
    checks = {}
    probes = {
        "elasticsearch": es.ping,
        "redis": redis.ping,
        "kafka": lambda: AdminClient(kafka_client_config()).list_topics(timeout=3),
        "ldap": lambda: _ldap_health(),
    }
    for name, fn in probes.items():
        try:
            result = fn()
            checks[name] = bool(result) if name in ("elasticsearch", "redis", "ldap") else True
        except Exception as exc:
            checks[name] = False
            logger.warning("Healthcheck %s falhou: %s", name, exc)
    ok = all(checks.values())
    return {"status": "ok" if ok else "degraded", "services": checks}


@app.post("/auth/login")
def login(payload: LoginPayload):
    try:
        user = authenticate_ldap(payload.username, payload.password)
    except Exception as exc:
        logger.exception("Erro de integração LDAP")
        raise HTTPException(503, "Serviço de autenticação indisponível") from exc
    if not user:
        raise HTTPException(401, "Credenciais inválidas")
    if not API_SECRET or len(API_SECRET) < 32 or API_SECRET.startswith("replace_with_"):
        raise HTTPException(503, "Defina um API_SECRET aleatório com pelo menos 32 caracteres no .env")
    token = jwt.encode({"sub": user["username"], "role": user["role"], "typ": "access",
                        "jti": secrets.token_hex(16), "exp": time.time() + API_TOKEN_TTL},
                       API_SECRET, algorithm="HS256")
    return {"access_token": token, "token_type": "bearer", "expires_in": API_TOKEN_TTL, "user": user}


@app.get("/auth/me")
def me(authorization: Optional[str] = Header(None)):
    return user_from_header(authorization, required=True)


@app.get("/questions")
def search_questions(q: str = "", area: str | None = None, course: str | None = None,
                    year: int | None = None, exam_type: str | None = None,
                    question_type: str | None = None, competency: str | None = None,
                    annulled: bool | None = None, page: int = Query(1, ge=1),
                    size: int = Query(10, ge=1, le=100),
                    authorization: Optional[str] = Header(None)):
    user = user_from_header(authorization)
    params = [q, area, course, year, exam_type, question_type, competency, annulled, page, size, user["role"]]
    cache_key = "search:" + hashlib.sha256(json.dumps(params, ensure_ascii=False).encode()).hexdigest()
    cached = redis.get(cache_key)
    if cached:
        return json.loads(cached)
    filters = []
    for field, value in [("area", area), ("course", course), ("year", year),
                         ("exam_type", exam_type), ("question_type", question_type),
                         ("competencies", competency), ("annulled", annulled)]:
        if value is not None:
            filters.append({"term": {field: value}})
    body = {"query": {"bool": {
        "must": [{"multi_match": {"query": q, "fields": ["statement^3", "alternatives", "knowledge_objects", "competencies"], "type": "best_fields"}}] if q else [{"match_all": {}}],
        "filter": filters}}, "from": (page - 1) * size, "size": size,
        "highlight": {"pre_tags": ["<mark>"], "post_tags": ["</mark>"], "fields": {"statement": {"number_of_fragments": 2, "fragment_size": 220}}}}
    try:
        result = es.search(index=INDEX, body=body)
    except Exception as exc:
        raise HTTPException(503, "Índice de busca indisponível") from exc
    items = []
    for hit in result["hits"]["hits"]:
        source = dict(hit["_source"])
        if user["role"] != "PROFESSOR":
            source.pop("answer_key", None)
        items.append({"id": hit["_id"], "score": hit.get("_score"), "question": source,
                      "highlight": hit.get("highlight", {})})
    response = {"total": result["hits"]["total"]["value"], "page": page, "size": size, "items": items}
    redis.setex(cache_key, 60, json.dumps(response, ensure_ascii=False))
    return response


@app.get("/questions/{question_id}")
def get_question(question_id: str, authorization: Optional[str] = Header(None)):
    user = user_from_header(authorization)
    try: doc = dict(es.get(index=INDEX, id=question_id)["_source"])
    except ElasticsearchHTTPError as exc:
        if exc.status_code == 404:
            raise HTTPException(404, "Questão não encontrada")
        raise HTTPException(503, "Índice indisponível") from exc
    except Exception as exc: raise HTTPException(503, "Índice indisponível") from exc
    if user["role"] != "PROFESSOR": doc.pop("answer_key", None)
    return doc


@app.get("/analytics/courses")
def analytics_courses(authorization: Optional[str] = Header(None)):
    professor(authorization)
    r = es.search(index=INDEX, size=0, aggs={"courses": {"terms": {"field": "course", "size": 200}}})
    return [{"course": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["courses"]["buckets"]]


@app.get("/analytics/competencies")
def analytics_competencies(authorization: Optional[str] = Header(None)):
    professor(authorization)
    r = es.search(index=INDEX, size=0, aggs={"competencies": {"terms": {"field": "competencies", "size": 200}}})
    return [{"competency": b["key"], "count": b["doc_count"]} for b in r["aggregations"]["competencies"]["buckets"]]


@app.get("/analytics/competencies/timeline")
def competency_timeline(authorization: Optional[str] = Header(None)):
    professor(authorization)
    r = es.search(index=INDEX, size=0, aggs={"years": {"histogram": {"field": "year", "interval": 1, "min_doc_count": 1},
        "aggs": {"competencies": {"terms": {"field": "competencies", "size": 100}}}}})
    return [{"year": y["key"], "competencies": [{"competency": c["key"], "count": c["doc_count"]} for c in y["competencies"]["buckets"]]} for y in r["aggregations"]["years"]["buckets"]]


def cart_key(user, session_id):
    # A sessão enviada pelo cliente é namespaced pelo usuário autenticado.
    return f"cart:{user['username']}:{session_id}"


@app.post("/cart/{session_id}")
def add_cart(session_id: str, payload: CartPayload, authorization: Optional[str] = Header(None)):
    user = user_from_header(authorization, required=True)
    try: exists = es.exists(index=INDEX, id=payload.question_id)
    except Exception as exc: raise HTTPException(503, "Índice indisponível") from exc
    if not exists:
        raise HTTPException(404, "Questão não encontrada")
    key = cart_key(user, session_id)
    redis.sadd(key, payload.question_id); redis.expire(key, 86400)
    return {"session_id": session_id, "items": sorted(redis.smembers(key))}


@app.get("/cart/{session_id}")
def get_cart(session_id: str, authorization: Optional[str] = Header(None)):
    user = user_from_header(authorization, required=True)
    return {"session_id": session_id, "items": sorted(redis.smembers(cart_key(user, session_id)))}


@app.delete("/cart/{session_id}/{question_id}")
def remove_cart(session_id: str, question_id: str, authorization: Optional[str] = Header(None)):
    user = user_from_header(authorization, required=True)
    key = cart_key(user, session_id); redis.srem(key, question_id)
    return {"items": sorted(redis.smembers(key))}


def selected_documents(user, session_id):
    ids = sorted(redis.smembers(cart_key(user, session_id)))
    if not ids: return []
    result = es.mget(index=INDEX, ids=ids)
    docs = []
    for item in result["docs"]:
        if item.get("found"):
            doc = dict(item["_source"])
            if user["role"] != "PROFESSOR": doc.pop("answer_key", None)
            docs.append(doc)
    return docs


@app.get("/cart/{session_id}/export.json")
def export_json(session_id: str, authorization: Optional[str] = Header(None)):
    user = user_from_header(authorization, required=True)
    if user["role"] != "PROFESSOR": raise HTTPException(403, "Exportação restrita a professores")
    return {"format": "enade-question-set-v1", "questions": selected_documents(user, session_id)}


@app.get("/cart/{session_id}/export.pdf")
def export_pdf(session_id: str, authorization: Optional[str] = Header(None)):
    user = user_from_header(authorization, required=True)
    if user["role"] != "PROFESSOR": raise HTTPException(403, "Exportação restrita a professores")
    docs = selected_documents(user, session_id)
    buffer = io.BytesIO(); pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4; y = height - 50
    pdf.setTitle("Simulado ENADE")
    pdf.setFont("Helvetica-Bold", 15); pdf.drawString(45, y, "Simulado - Acervo ENADE"); y -= 35
    for i, doc in enumerate(docs, 1):
        text = f"{i}. {doc.get('statement', '')}"
        pdf.setFont("Helvetica", 10)
        for line in [text[j:j+105] for j in range(0, len(text), 105)]:
            if y < 55: pdf.showPage(); y = height - 50; pdf.setFont("Helvetica", 10)
            pdf.drawString(45, y, line.encode("latin-1", "replace").decode("latin-1")); y -= 15
        for alt in doc.get("alternatives", []):
            if y < 55: pdf.showPage(); y = height - 50; pdf.setFont("Helvetica", 10)
            pdf.drawString(60, y, alt[:110].encode("latin-1", "replace").decode("latin-1")); y -= 14
        y -= 15
    pdf.save(); buffer.seek(0)
    return Response(buffer.getvalue(), media_type="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=simulado-enade.pdf"})


@app.post("/admin/cache/invalidate")
def cache_invalidate(authorization: Optional[str] = Header(None)):
    professor(authorization)
    invalidate_search_cache()
    return {"status": "invalidated"}
