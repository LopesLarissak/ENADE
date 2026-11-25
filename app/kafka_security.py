"""Configuração comum SASL/GSSAPI para os clientes Kafka do ENADE."""
import os


def kafka_client_config() -> dict:
    """Retorna as opções Confluent/librdkafka para autenticação Kerberos."""
    return {
        "bootstrap.servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"),
        "security.protocol": "SASL_PLAINTEXT",
        "sasl.mechanism": "GSSAPI",
        "sasl.kerberos.service.name": os.getenv("KAFKA_KERBEROS_SERVICE_NAME", "kafka"),
        "sasl.kerberos.principal": os.getenv("KRB5_PRINCIPAL", ""),
        "sasl.kerberos.keytab": os.getenv("KRB5_KEYTAB", ""),
        "enable.ssl.certificate.verification": True,
    }
