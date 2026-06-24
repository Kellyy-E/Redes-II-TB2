"""
Cliente HTTP sobre R-UDP (Stop-and-Wait).
Fluxo: DNS → envia GET via R-UDP → recebe resposta via R-UDP → salva → CSV.

Uso:
    python3 cliente_http_rudp.py <nome_host> <arquivo> <cenario> [ip_dns] [porta_dns]
    Exemplos:
        python3 cliente_http_rudp.py servidor-web arquivo_100kb.bin cenarioA servidor-dns 5354
        python3 cliente_http_rudp.py servidor-web arquivo_10mb.bin  cenarioC servidor-dns 5354
"""

import socket
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from src.common.utils import (Packet, calcular_checksum, gerar_x_custom_auth,
                               FLAG_DATA, FLAG_ACK, FLAG_FIN, salvar_log_csv)
from src.dns.cliente_dns import resolver_nome

MATRICULA        = "20249016916"
NOME             = "Eurikelly Luiza"
PORTA_HTTP_RUDP  = 8081
BUFFER_SIZE      = 4096
TIMEOUT_RUDP     = 0.5


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


def enviar_via_rudp(sock, ip_servidor, porta, dados, auth_hash):
    seq = 0
    offset = 0
    total = len(dados)

    while offset < total:
        chunk = dados[offset: offset + BUFFER_SIZE]
        pacote = Packet(seq=seq, flags=FLAG_DATA, auth_hash=auth_hash, data=chunk)

        confirmado = False
        while not confirmado:
            sock.sendto(pacote.pack(), (ip_servidor, porta))
            try:
                ack_bytes, _ = sock.recvfrom(8192)
                ack_obj, _ = Packet.unpack(ack_bytes)
                if ack_obj.flags == FLAG_ACK and ack_obj.seq == seq:
                    confirmado = True
                    seq = 1 - seq
                    offset += len(chunk)
            except socket.timeout:
                print(f"[RUDP] Timeout offset={offset}. Reenviando...")

    pacote_fin = Packet(seq=seq, flags=FLAG_FIN, auth_hash=auth_hash, data=b'')
    fin_ok = False
    while not fin_ok:
        sock.sendto(pacote_fin.pack(), (ip_servidor, porta))
        try:
            ack_bytes, _ = sock.recvfrom(8192)
            ack_obj, _ = Packet.unpack(ack_bytes)
            if ack_obj.flags == FLAG_ACK and ack_obj.seq == seq:
                fin_ok = True
        except socket.timeout:
            print("[RUDP] Timeout FIN. Reenviando...")


def receber_via_rudp(sock):
    dados = b""
    seq_esperado = 0

    while True:
        try:
            raw, addr = sock.recvfrom(8192)
            pacote, checksum_recebido = Packet.unpack(raw)

            dados_para_cs = raw[:4] + b'\x00\x00' + raw[6:]
            if checksum_recebido != calcular_checksum(dados_para_cs):
                print("[RUDP] Checksum inválido. Descartando.")
                continue

            if pacote.flags == FLAG_FIN:
                ack_fin = Packet(seq=pacote.seq, flags=FLAG_ACK,
                                 auth_hash=pacote.auth_hash.decode())
                sock.sendto(ack_fin.pack(), addr)
                break

            elif pacote.flags == FLAG_DATA:
                if pacote.seq == seq_esperado:
                    dados += pacote.data
                    ack = Packet(seq=pacote.seq, flags=FLAG_ACK,
                                 auth_hash=pacote.auth_hash.decode())
                    sock.sendto(ack.pack(), addr)
                    seq_esperado = 1 - seq_esperado
                else:
                    ack_dup = Packet(seq=pacote.seq, flags=FLAG_ACK,
                                     auth_hash=pacote.auth_hash.decode())
                    sock.sendto(ack_dup.pack(), addr)

        except socket.timeout:
            continue

    return dados


def requisitar_arquivo_rudp(nome_host, arquivo, cenario,
                             ip_dns="servidor-dns", porta_dns=5354):
    auth_hash = gerar_x_custom_auth(MATRICULA, NOME)

    print(f"\n{'='*60}")
    print(f"[RUDP] Arquivo: {arquivo} | Cenário: {cenario}")

    # ── Passo 1: resolução DNS ────────────────────────────────────────────────
    t_dns_ini = time.time()
    ip_servidor = resolver_nome(nome_host, ip_dns, porta_dns)
    t_dns_fim = time.time()

    if not ip_servidor:
        print(f"[RUDP][ERRO] Não foi possível resolver '{nome_host}'. Abortando.")
        return
    print(f"[RUDP] DNS: {ip_servidor} ({(t_dns_fim-t_dns_ini)*1000:.1f} ms)")

    # ── Passo 2: envia GET e recebe resposta via R-UDP ────────────────────────
    t_http_ini = time.time()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(TIMEOUT_RUDP)

        request = montar_get_request(nome_host, arquivo, auth_hash)
        enviar_via_rudp(sock, ip_servidor, PORTA_HTTP_RUDP, request, auth_hash)
        dados_brutos = receber_via_rudp(sock)
        sock.close()

    except Exception as e:
        print(f"[RUDP][ERRO] {e}")
        return

    t_http_fim = time.time()

    # ── Passo 3: processar resposta ───────────────────────────────────────────
    cabecalho_bytes, corpo = extrair_corpo(dados_brutos)
    status  = parsear_status(cabecalho_bytes)
    tamanho = len(corpo)

    print(f"[RUDP] Status: {status} | Corpo: {tamanho} bytes")
    print(f"[RUDP] DNS: {(t_dns_fim-t_dns_ini)*1000:.1f} ms | "
          f"HTTP: {(t_http_fim-t_http_ini)*1000:.1f} ms | "
          f"Total: {(t_http_fim-t_dns_ini)*1000:.1f} ms")

    # ── Passo 4: salvar arquivo e logs ────────────────────────────────────────
    if status == 200 and corpo:
        os.makedirs("data/recebidos", exist_ok=True)
        nome_saida = f"data/recebidos/rudp_{os.path.basename(arquivo)}"
        with open(nome_saida, "wb") as f:
            f.write(corpo)
        print(f"[RUDP] Arquivo salvo: {nome_saida}")

        salvar_log_csv("DNS-RUDP",  arquivo, t_dns_ini,  t_dns_fim,  0,       cenario)
        salvar_log_csv("HTTP-RUDP", arquivo, t_http_ini, t_http_fim, tamanho, cenario)
    else:
        print(f"[RUDP] Resposta {status} — arquivo não salvo.")

    print(f"{'='*60}\n")


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Uso: python3 cliente_http_rudp.py <nome_host> <arquivo> <cenario> "
              "[ip_dns] [porta_dns]")
        sys.exit(1)

    nome_host = sys.argv[1]
    arquivo   = sys.argv[2]
    cenario   = sys.argv[3]
    ip_dns    = sys.argv[4] if len(sys.argv) > 4 else "servidor-dns"
    porta_dns = int(sys.argv[5]) if len(sys.argv) > 5 else 5354

    requisitar_arquivo_rudp(nome_host, arquivo, cenario, ip_dns, porta_dns)
