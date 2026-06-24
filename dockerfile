FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    iproute2 \
    tcpdump \
    iputils-ping \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY src/ ./src/
COPY data/ ./data/
COPY docker/ ./docker/
COPY orquestrador_testes.py ./orquestrador_testes.py
COPY gerar_arquivos_teste.py ./gerar_arquivos_teste.py

RUN chmod +x ./docker/scripts/simular_rede.sh

RUN mkdir -p data/www data/recebidos data/capturas

CMD ["python3", "--version"]
