FROM python:3.14-slim

RUN apt-get update && apt-get install -y \
    iproute2 \
    tcpdump \
    && rm -rf /var/lib/apt/lists/*

# Define o diretório de trabalho dentro do container
WORKDIR /app

ENV PYTHONPATH=/app

# Copia todo o conteúdo do meu projeto para dentro do container
COPY . /app/

# O container inicia sem fazer nada 
CMD ["tail", "-f", "/dev/null"]