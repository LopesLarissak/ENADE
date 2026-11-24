"""Criação idempotente dos tópicos necessários ao pipeline ENADE."""
from confluent_kafka.admin import AdminClient, NewTopic
from confluent_kafka import KafkaException
from app.kafka_security import kafka_client_config


def ensure_topics() -> None:
    admin = AdminClient(kafka_client_config())
    topics = [
        NewTopic("enade.questions", num_partitions=3, replication_factor=1),
        NewTopic("enade.questions.dlq", num_partitions=1, replication_factor=1),
    ]
    for topic, future in admin.create_topics(topics, operation_timeout=20).items():
        try:
            future.result()
        except KafkaException as exc:
            error = exc.args[0]
            if getattr(error, "code", lambda: None)() != 36:  # TOPIC_ALREADY_EXISTS
                raise
