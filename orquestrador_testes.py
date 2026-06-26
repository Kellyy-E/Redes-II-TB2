"""
Orquestrador de Testes — Terceira Avaliação
Uso (no Git Bash, fora do container):
    python orquestrador_testes.py <protocolo> <cenario> <tamanho>

    protocolo : tcp | rudp
    cenario   : cenarioA | cenarioB | cenarioC
    tamanho   : 100KB | 1MB | 10MB

Exemplos:
    python orquestrador_testes.py tcp  cenarioA 100KB
    python orquestrador_testes.py rudp cenarioB 1MB
    python orquestrador_testes.py tcp  cenarioC 10MB

O orquestrador aplica o cenário de rede e roda os clientes
todos dentro do container via 'docker exec'.
"""

import subprocess
import time
import sys

EXECUCOES  = 10
IP_DNS     = "servidor-dns"
PORTA_DNS  = 53
NOME_HOST  = "servidor-web"

# Nome do container cliente definido no docker-compose.yml
CONTAINER_CLIENTE = "cliente"

ARQUIVOS = {
    "100KB": "arquivo_100kb.bin",
    "500KB": "arquivo_500kb.bin",
    "1MB":   "arquivo_1mb.bin",
}

CENARIOS   = ["cenarioA", "cenarioB", "cenarioC"]
PROTOCOLOS = ["tcp", "rudp"]


def exec_container(comando_lista):
    """Executa um comando dentro do container cliente via docker exec."""
    cmd = ["docker", "exec", CONTAINER_CLIENTE] + comando_lista
    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[ERRO] {e}")


def aplicar_cenario(cenario):
    print(f"[REDE] Aplicando {cenario} dentro do container...")
    exec_container(["bash", "docker/scripts/simular_rede.sh", cenario])
    time.sleep(2)


def limpar_rede():
    print("[REDE] Limpando regras tc...")
    exec_container(["bash", "docker/scripts/simular_rede.sh", "limpar"])


def rodar_cliente(protocolo, arquivo, cenario):
    if protocolo == "tcp":
        script = "src/http/cliente_http_tcp.py"
    else:
        script = "src/http/cliente_http_rudp.py"

    exec_container([
        "python3", script,
        NOME_HOST, arquivo, cenario, IP_DNS, str(PORTA_DNS)
    ])


def main():
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(1)

    protocolo = sys.argv[1].lower()
    cenario   = sys.argv[2]
    tamanho   = sys.argv[3].upper()

    if protocolo not in PROTOCOLOS:
        print(f"[ERRO] Protocolo inválido: '{protocolo}'. Use: tcp | rudp")
        sys.exit(1)
    if cenario not in CENARIOS:
        print(f"[ERRO] Cenário inválido: '{cenario}'. Use: {CENARIOS}")
        sys.exit(1)
    if tamanho not in ARQUIVOS:
        print(f"[ERRO] Tamanho inválido: '{tamanho}'. Use: {list(ARQUIVOS.keys())}")
        sys.exit(1)

    arquivo = ARQUIVOS[tamanho]

    print(f"\n{'='*60}")
    print(f" Protocolo : {protocolo.upper()}")
    print(f" Cenário   : {cenario}")
    print(f" Arquivo   : {arquivo} ({tamanho})")
    print(f" Execuções : {EXECUCOES}")
    print(f"{'='*60}\n")

    aplicar_cenario(cenario)

    for i in range(1, EXECUCOES + 1):
        print(f"[{i:02d}/{EXECUCOES:02d}]")
        rodar_cliente(protocolo, arquivo, cenario)
        time.sleep(0.5)

    limpar_rede()

    print(f"\n[OK] Concluído. CSVs salvos em data/logs/:")
    print(f"     HTTP-{protocolo.upper()}_{tamanho}.csv")
    print(f"     DNS-{protocolo.upper()}_{tamanho}.csv")


if __name__ == "__main__":
    main()
