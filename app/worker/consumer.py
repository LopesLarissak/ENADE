
import json
import logging
import os
import time

from confluent_kafka import Consumer, Producer
from elasticsearch import Elasticsearch
from redis import Redis

from app.config import KAFKA, ELASTIC_URL, REDIS_URL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)

INDEX = "enade-questions"
DLQ_TOPIC = "enade.questions.dlq"
MAIN_TOPIC = "enade.questions"
MAX_RETRIES = 3

es = Elasticsearch(ELASTIC_URL)
redis_client = Redis.from_url(REDIS_URL, decode_responses=True)


def ensure_index():
    if es.indices.exists(index=INDEX):
        logging.info("Índice %s já existe.", INDEX)
        return

    es.indices.create(
        index=INDEX,
        settings={"analysis": {"filter": {"enade_synonyms": {
            "type": "synonym", "synonyms": ["tecnologia da informação, TI", "inteligência artificial, IA",
                "segurança da informação, cibersegurança", "sistema de informação, sistemas de informação"]}},
            "analyzer": {"ptbr_enade": {"tokenizer": "standard", "filter": ["lowercase", "brazilian_stop", "brazilian_stemmer", "enade_synonyms"]}}}},
        mappings={"properties": {
            "id": {"type": "keyword"}, "statement": {"type": "text", "analyzer": "ptbr_enade"},
            "alternatives": {"type": "text", "analyzer": "ptbr_enade"},
            "area": {"type": "keyword"}, "course": {"type": "keyword"}, "year": {"type": "integer"},
            "exam_type": {"type": "keyword"}, "question_type": {"type": "keyword"},
            "competencies": {"type": "keyword"}, "knowledge_objects": {"type": "keyword"},
            "source_pdf": {"type": "keyword"}, "source_page": {"type": "integer"},
            "source_pages": {"type": "integer"}, "annulled": {"type": "boolean"},
            "question_number": {"type": "keyword"}, "media_review_required": {"type": "boolean"},
            "media_references": {"type": "object", "enabled": True},
            "structured_media": {"type": "object", "enabled": True},
            "extraction_method": {"type": "keyword"}, "extraction_status": {"type": "keyword"}
        }}
    )

    logging.info("Índice %s criado.", INDEX)


def publish_to_dlq(producer, msg, error):
    delivery_errors = []

    def delivery_report(err, delivered_msg):
        if err is not None:
            delivery_errors.append(str(err))

    producer.produce(
        DLQ_TOPIC,
        key=msg.key(),
        value=msg.value(),
        headers=[
            ("processing_error", str(error).encode("utf-8"))
        ],
        on_delivery=delivery_report
    )

    remaining = producer.flush(15)

    if remaining or delivery_errors:
        raise RuntimeError(
            f"Falha na entrega à DLQ. Pendentes: {remaining}. "
            f"Erros: {delivery_errors}"
        )

    logging.warning(
        "Mensagem encaminhada para DLQ. Motivo: %s",
        error
    )


def process_message(msg):
    data = json.loads(msg.value().decode("utf-8"))

    required_fields = ["id", "statement", "source_pdf", "source_page"]

    for field in required_fields:
        if field not in data or data[field] is None:
            raise ValueError(f"Campo obrigatório ausente: {field}")

    if not isinstance(data["source_page"], int):
        raise ValueError("source_page precisa ser um número inteiro")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            es.index(
                index=INDEX,
                id=data["id"],
                document=data,
                refresh="wait_for"
            )
            # Reindexação/novos documentos invalidam resultados potencialmente desatualizados.
            try:
                cursor = 0
                while True:
                    cursor, keys = redis_client.scan(cursor=cursor, match="search:*", count=500)
                    if keys:
                        redis_client.delete(*keys)
                    if cursor == 0:
                        break
            except Exception:
                logging.exception("Documento indexado, mas a invalidação do cache Redis falhou")

            logging.info(
                "Questão indexada: %s | PDF: %s | Página: %s",
                data["id"],
                data["source_pdf"],
                data["source_page"]
            )

            return

        except Exception:
            logging.exception(
                "Falha no Elasticsearch. Tentativa %s/%s",
                attempt,
                MAX_RETRIES
            )

            if attempt == MAX_RETRIES:
                raise

            time.sleep(2 ** attempt)


def main():
    ensure_index()

    consumer = Consumer({
        "bootstrap.servers": KAFKA,
        "group.id": "enade-elastic-indexer-v1",
        "auto.offset.reset": "earliest",
        "enable.auto.commit": False
    })

    producer = Producer({
        "bootstrap.servers": KAFKA,
        "enable.idempotence": True,
        "acks": "all",
        "retries": 10
    })

    consumer.subscribe([MAIN_TOPIC])

    logging.info(
        "Worker iniciado. Kafka: %s | Tópico: %s",
        KAFKA,
        MAIN_TOPIC
    )

    try:
        while True:
            msg = consumer.poll(1.0)

            if msg is None:
                continue

            if msg.error():
                logging.error("Erro Kafka: %s", msg.error())
                continue

            try:
                process_message(msg)

            except Exception as exc:
                logging.exception("Falha definitiva no processamento.")

                try:
                    publish_to_dlq(producer, msg, exc)

                except Exception:
                    logging.exception(
                        "Falha na DLQ. Offset não será confirmado."
                    )
                    time.sleep(2)
                    continue

            try:
                consumer.commit(
                    message=msg,
                    asynchronous=False
                )
            except Exception:
                logging.exception("Falha ao confirmar offset Kafka.")

    finally:
        consumer.close()
        producer.flush(15)


if __name__ == "__main__":
    main()
