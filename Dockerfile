FROM python:3.11-slim
WORKDIR /app
ENV PYTHONPATH=/app PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DEBIAN_FRONTEND=noninteractive
COPY requirements.txt .
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-por tesseract-ocr-eng \
    krb5-user libkrb5-dev libsasl2-2 libsasl2-dev libsasl2-modules-gssapi-mit \
    librdkafka-dev gcc g++ make \
    && rm -rf /var/lib/apt/lists/*
RUN WITH_SASL=1 pip install --no-cache-dir --no-binary=confluent-kafka -r requirements.txt
COPY app ./app
COPY scripts/with_kerberos.sh /app/scripts/with_kerberos.sh
RUN chmod 0755 /app/scripts/with_kerberos.sh
