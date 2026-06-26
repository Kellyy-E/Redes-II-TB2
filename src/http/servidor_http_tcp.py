import socket
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
from src.common.utils import gerar_x_custom_auth

MATRICULA   = "20249016916"
NOME        = "Eurikelly Luiza"
PASTA_WWW   = os.path.join(os.path.dirname(__file__), "../../data/www")
BUFFER_SIZE = 4096


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
    """Extrai o caminho do arquivo da requisição GET. Retorna None se inválida."""
    try:
        linha = dados_brutos.decode(errors="replace").split("\r\n")[0].split()
        if len(linha) >= 2 and linha[0].upper() == "GET":
            return linha[1]
    except Exception:
        pass
    return None


def tratar_conexao(conn, addr, auth_hash):
    try:
        dados = b""
        while b"\r\n\r\n" not in dados:
            fragmento = conn.recv(BUFFER_SIZE)
            if not fragmento:
                break
            dados += fragmento

        caminho_req = parsear_get(dados)
        if not caminho_req:
            conn.close()
            return

        caminho_req = caminho_req.split("?")[0].lstrip("/") or "index.html"
        caminho_local = os.path.normpath(os.path.join(PASTA_WWW, caminho_req))

        if not caminho_local.startswith(os.path.normpath(PASTA_WWW)):
            conn.sendall(montar_404(auth_hash))
            conn.close()
            return

        print(f"[HTTP-TCP] GET /{caminho_req} de {addr}", end=" ")

        if os.path.isfile(caminho_local):
            with open(caminho_local, "rb") as f:
                corpo = f.read()
            resposta = montar_resposta(200, "OK", corpo,
                                       detectar_content_type(caminho_local), auth_hash)
            print(f"→ 200 OK ({len(corpo)} bytes)")
        else:
            resposta = montar_404(auth_hash)
            print(f"→ 404 Not Found")

        conn.sendall(resposta)

    except Exception as e:
        print(f"[HTTP-TCP][ERRO] {e}")
    finally:
        conn.close()


def iniciar_servidor_http_tcp(porta=8080):
    auth_hash = gerar_x_custom_auth(MATRICULA, NOME)

    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    servidor.bind(("0.0.0.0", porta))
    servidor.listen(5)
    print(f"[HTTP-TCP] Servidor HTTP/TCP escutando na porta {porta}...")
    print(f"[HTTP-TCP] Servindo arquivos de: {PASTA_WWW}")

    while True:
        try:
            conn, addr = servidor.accept()
            print(f"\n[HTTP-TCP] Nova conexão de {addr}")
            tratar_conexao(conn, addr, auth_hash)
        except KeyboardInterrupt:
            print("\n[HTTP-TCP] Encerrado pelo usuário.")
            break

    servidor.close()


if __name__ == "__main__":
    porta = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    iniciar_servidor_http_tcp(porta)
