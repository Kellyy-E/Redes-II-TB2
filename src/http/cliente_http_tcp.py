"""
Cliente HTTP sobre TCP nativo.
Fluxo: DNS → GET HTTP/TCP → salva arquivo → registra métricas em CSV.

Uso:
    python3 cliente_http_tcp.py <nome_host> <arquivo> <cenario> [ip_dns] [porta_dns]
    Exemplos:
        python3 cliente_http_tcp.py servidor-web arquivo_100kb.bin cenarioA servidor-dns 5354
        python3 cliente_http_tcp.py servidor-web arquivo_1mb.bin   cenarioB servidor-dns 5354
"""

import socket
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from src.common.utils import gerar_x_custom_auth, salvar_log_csv
from src.dns.cliente_dns import resolver_nome

MATRICULA      = "20249016916"
NOME           = "Eurikelly Luiza"
PORTA_HTTP_TCP = 8080
BUFFER_SIZE    = 4096


def montar_get_request(host, arquivo, auth_hash):
    return (
        f"GET /{arquivo} HTTP/1.1\r\n"
        f"Host: {host}\r\n"
        f"X-Custom-Auth: {auth_hash}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    ).encode()


def extrair_corpo(dados_brutos):
    sep = b"\r\n\r\n"
    pos = dados_brutos.find(sep)
    if pos == -1:
        return dados_brutos, b""
    return dados_brutos[:pos], dados_brutos[pos + len(sep):]


def parsear_status(cabecalho_bytes):
    try:
        linha = cabecalho_bytes.split(b"\r\n")[0].decode()
        return int(linha.split()[1])
    except Exception:
        return None


def requisitar_arquivo_tcp(nome_host, arquivo, cenario,
                           ip_dns="servidor-dns", porta_dns=5354):
    auth_hash = gerar_x_custom_auth(MATRICULA, NOME)

    print(f"\n{'='*60}")
    print(f"[TCP] Arquivo: {arquivo} | Cenário: {cenario}")

    # ── Passo 1: resolução DNS ────────────────────────────────────────────────
    t_dns_ini = time.time()
    ip_servidor = resolver_nome(nome_host, ip_dns, porta_dns)
    t_dns_fim = time.time()

    if not ip_servidor:
        print(f"[TCP][ERRO] Não foi possível resolver '{nome_host}'. Abortando.")
        return
    print(f"[TCP] DNS: {ip_servidor} ({(t_dns_fim-t_dns_ini)*1000:.1f} ms)")

    # ── Passo 2: requisição HTTP via TCP ──────────────────────────────────────
    t_http_ini = time.time()
    try:
        cliente = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        cliente.connect((ip_servidor, PORTA_HTTP_TCP))
        cliente.sendall(montar_get_request(nome_host, arquivo, auth_hash))

        dados_brutos = b""
        while True:
            chunk = cliente.recv(BUFFER_SIZE)
            if not chunk:
                break
            dados_brutos += chunk
        cliente.close()

    except ConnectionRefusedError:
        print(f"[TCP][ERRO] Conexão recusada em {ip_servidor}:{PORTA_HTTP_TCP}.")
        return
    except Exception as e:
        print(f"[TCP][ERRO] {e}")
        return

    t_http_fim = time.time()

    # ── Passo 3: processar resposta ───────────────────────────────────────────
    cabecalho_bytes, corpo = extrair_corpo(dados_brutos)
    status   = parsear_status(cabecalho_bytes)
    tamanho  = len(corpo)

    print(f"[TCP] Status: {status} | Corpo: {tamanho} bytes")
    print(f"[TCP] DNS: {(t_dns_fim-t_dns_ini)*1000:.1f} ms | "
          f"HTTP: {(t_http_fim-t_http_ini)*1000:.1f} ms | "
          f"Total: {(t_http_fim-t_dns_ini)*1000:.1f} ms")

    # ── Passo 4: salvar arquivo e logs ────────────────────────────────────────
    if status == 200 and corpo:
        os.makedirs("data/recebidos", exist_ok=True)
        nome_saida = f"data/recebidos/tcp_{os.path.basename(arquivo)}"
        with open(nome_saida, "wb") as f:
            f.write(corpo)
        print(f"[TCP] Arquivo salvo: {nome_saida}")

        # CSV separado por protocolo, cenário e tamanho
        salvar_log_csv("DNS-TCP",  arquivo, t_dns_ini,  t_dns_fim,  0,       cenario)
        salvar_log_csv("HTTP-TCP", arquivo, t_http_ini, t_http_fim, tamanho, cenario)
    else:
        print(f"[TCP] Resposta {status} — arquivo não salvo.")

    print(f"{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Uso: python3 cliente_http_tcp.py <nome_host> <arquivo> <cenario> "
              "[ip_dns] [porta_dns]")
        sys.exit(1)

    nome_host = sys.argv[1]
    arquivo   = sys.argv[2]
    cenario   = sys.argv[3]
    ip_dns    = sys.argv[4] if len(sys.argv) > 4 else "servidor-dns"
    porta_dns = int(sys.argv[5]) if len(sys.argv) > 5 else 5354

    requisitar_arquivo_tcp(nome_host, arquivo, cenario, ip_dns, porta_dns)
