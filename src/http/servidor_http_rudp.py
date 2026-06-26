"""
Miniservidor HTTP/1.1 sobre R-UDP (Stop-and-Wait).
Recebe a requisição GET empacotada em R-UDP, processa e devolve
a resposta HTTP completa também via R-UDP.
Inclui o cabeçalho X-Custom-Auth em todas as respostas.

Uso:
    python3 servidor_http_rudp.py [porta]
    Padrão: porta 8081
"""

import socket
import os
import sys



sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from src.common.utils import (Packet, calcular_checksum, gerar_x_custom_auth,
                               FLAG_DATA, FLAG_ACK, FLAG_FIN)

MATRICULA    = "20249016916"
NOME         = "Eurikelly Luiza"
PASTA_WWW    = os.path.join(os.path.dirname(__file__), "../../data/www")
BUFFER_SIZE  = 4096
TIMEOUT_RUDP = 0.5  # segundos


def detectar_content_type(caminho):
    ext = os.path.splitext(caminho)[1].lower()
    tipos = {
        ".html": "text/html; charset=utf-8",
        ".htm":  "text/html; charset=utf-8",
        ".css":  "text/css",
        ".js":   "application/javascript",
        ".txt":  "text/plain; charset=utf-8",
        ".bin":  "application/octet-stream",
        ".png":  "image/png",
        ".jpg":  "image/jpeg",
    }
    return tipos.get(ext, "application/octet-stream")


def montar_resposta(status_code, status_text, corpo, content_type, auth_hash):
    cabecalho = (
        f"HTTP/1.1 {status_code} {status_text}\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(corpo)}\r\n"
        f"X-Custom-Auth: {auth_hash}\r\n"
        f"Connection: close\r\n"
        f"\r\n"
    )
    return cabecalho.encode() + corpo


def montar_404(auth_hash):
    corpo = b"<html><body><h1>404 Not Found</h1></body></html>"
    return montar_resposta(404, "Not Found", corpo,
                           "text/html; charset=utf-8", auth_hash)


def parsear_get(dados_brutos):
    try:
        linha = dados_brutos.decode(errors="replace").split("\r\n")[0].split()
        if len(linha) >= 2 and linha[0].upper() == "GET":
            return linha[1]
    except Exception:
        pass
    return None


def receber_request_rudp(sock):
    """
    Recebe a requisição GET enviada via R-UDP pelo cliente.
    Retorna (dados_brutos, addr_cliente) ou (None, None) em caso de erro.
    """
    dados = b""
    addr_cliente = None
    seq_esperado = 0

    while True:
        try:
            raw, addr = sock.recvfrom(8192)
            pacote, checksum_recebido = Packet.unpack(raw)

            # Validação de checksum
            dados_para_cs = raw[:4] + b'\x00\x00' + raw[6:]
            if checksum_recebido != calcular_checksum(dados_para_cs):
                print("[HTTP-RUDP] Checksum inválido. Descartando.")
                continue

            addr_cliente = addr

            if pacote.flags == FLAG_FIN:
                # Fim da requisição — confirma e sai do loop
                ack_fin = Packet(seq=pacote.seq, flags=FLAG_ACK,
                                 auth_hash=pacote.auth_hash.decode())
                for _ in range(3):  # envia 3x para garantir chegada do FIN-ACK
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
                    # Duplicado — reenvia ACK sem acumular dados
                    ack_dup = Packet(seq=pacote.seq, flags=FLAG_ACK,
                                     auth_hash=pacote.auth_hash.decode())
                    sock.sendto(ack_dup.pack(), addr)

        except socket.timeout:
            # Aguarda mais chunks; o FIN indica o fim real da requisição
            continue

    return dados, addr_cliente


def enviar_resposta_rudp(sock, addr, dados, auth_hash):
    """
    Envia a resposta HTTP completa (cabeçalho + corpo) via R-UDP Stop-and-Wait.
    """
    seq = 0
    offset = 0
    total = len(dados)

    while offset < total:
        chunk = dados[offset: offset + BUFFER_SIZE]
        pacote = Packet(seq=seq, flags=FLAG_DATA, auth_hash=auth_hash, data=chunk)

        confirmado = False
        while not confirmado:
            sock.sendto(pacote.pack(), addr)
            try:
                ack_bytes, addr_ack = sock.recvfrom(8192)
                if addr_ack != addr:
                    continue
                ack_obj, _ = Packet.unpack(ack_bytes)
                if ack_obj.flags == FLAG_ACK and ack_obj.seq == seq:
                    confirmado = True
                    seq = 1 - seq
                    offset += len(chunk)
            except socket.timeout:
                print(f"[HTTP-RUDP] Timeout no chunk offset={offset}. Reenviando...")

    # Sinaliza fim da resposta com FIN
    pacote_fin = Packet(seq=seq, flags=FLAG_FIN, auth_hash=auth_hash, data=b'')
    fin_confirmado = False
    tentativas_fin = 0  # <--- NOVA VARIÁVEL
    
    # <--- ADICIONADO O LIMITE DE TENTATIVAS NO WHILE
    while not fin_confirmado and tentativas_fin < 10: 
        sock.sendto(pacote_fin.pack(), addr)
        try:
            ack_bytes, addr_ack = sock.recvfrom(8192)
            if addr_ack != addr:
                continue
            ack_obj, _ = Packet.unpack(ack_bytes)
            if ack_obj.flags == FLAG_ACK and ack_obj.seq == seq:
                fin_confirmado = True
        except socket.timeout:
            tentativas_fin += 1 # <--- INCREMENTA A TENTATIVA
            print(f"[HTTP-RUDP] Timeout no FIN. Reenviando ({tentativas_fin}/10)...")


def iniciar_servidor_http_rudp(porta=8081):
    auth_hash = gerar_x_custom_auth(MATRICULA, NOME)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", porta))
    sock.settimeout(TIMEOUT_RUDP)
    print(f"[HTTP-RUDP] Servidor HTTP/R-UDP escutando na porta {porta}...")
    print(f"[HTTP-RUDP] Servindo arquivos de: {PASTA_WWW}")

    while True:
        try:
            # ── Recebe a requisição GET ────────────────────────────────────
            dados_req, addr_cliente = receber_request_rudp(sock)

            if not dados_req or not addr_cliente:
                continue

            # ── Processa e monta a resposta ───────────────────────────────
            caminho_req = parsear_get(dados_req)
            if not caminho_req:
                print("[HTTP-RUDP] Requisição inválida. Ignorando.")
                continue

            caminho_req = caminho_req.split("?")[0].lstrip("/") or "index.html"
            caminho_local = os.path.normpath(os.path.join(PASTA_WWW, caminho_req))

            print(f"\n[HTTP-RUDP] GET /{caminho_req} de {addr_cliente}", end=" ")

            if (os.path.isfile(caminho_local) and
                    caminho_local.startswith(os.path.normpath(PASTA_WWW))):
                with open(caminho_local, "rb") as f:
                    corpo = f.read()
                resposta = montar_resposta(200, "OK", corpo,
                                           detectar_content_type(caminho_local),
                                           auth_hash)
                print(f"→ 200 OK ({len(corpo)} bytes)")
            else:
                resposta = montar_404(auth_hash)
                print(f"→ 404 Not Found")

            # ── Envia resposta via R-UDP ───────────────────────────────────
            enviar_resposta_rudp(sock, addr_cliente, resposta, auth_hash)

        except KeyboardInterrupt:
            print("\n[HTTP-RUDP] Encerrado pelo usuário.")
            break
        except Exception as e:
            print(f"[HTTP-RUDP][ERRO] {e}")
            continue

    sock.close()


if __name__ == "__main__":
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 8081
    iniciar_servidor_http_rudp(porta)
