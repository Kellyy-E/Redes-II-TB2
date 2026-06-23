import socket
import os

HOSTS_FILE = os.path.join(os.path.dirname(__file__), '../../data/hosts.txt')
DNS_HOST = '0.0.0.0'
DNS_PORT = 5354

def carregar_hosts():
    """Carrega o arquivo hosts.txt para um dicionário em memória."""
    tabela_hosts = {}
    try:
        with open(HOSTS_FILE, 'r') as f:
            for linha in f:
                linha = linha.strip()
                if not linha or linha.startswith('#'):
                    continue
                nome, ip = linha.split()
                tabela_hosts[nome] = ip
        print(f"[DNS] Arquivo de zona carregado com {len(tabela_hosts)} registros.")
    except FileNotFoundError:
        print(f"[DNS ERRO] Arquivo {HOSTS_FILE} não encontrado.")
    return tabela_hosts

def iniciar_servidor_dns():
    tabela_hosts = carregar_hosts()
    
    # Operando exclusivamente via UDP nativo
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((DNS_HOST, DNS_PORT))
    
    print(f"[DNS] Servidor DNS ativo em UDP {DNS_HOST}:{DNS_PORT}")
    
    while True:
        dados, endereco_cliente = sock.recvfrom(1024)
        mensagem = dados.decode('utf-8')
        
        try:
            # Formato esperado da requisição: "ID|Name"
            partes = mensagem.split('|')
            if len(partes) >= 2:
                req_id = partes[0]
                req_name = partes[1]
                
                print(f"[DNS] Consulta recebida de {endereco_cliente}: ID={req_id}, Name={req_name}")
                
                # Resolução do IP
                ip_resolvido = tabela_hosts.get(req_name, "0.0.0.0") # 0.0.0.0 simula "Not Found"
                
                # Formato simplificado de resposta: "ID|Name|IP"
                resposta = f"{req_id}|{req_name}|{ip_resolvido}"
                sock.sendto(resposta.encode('utf-8'), endereco_cliente)
                print(f"[DNS] Resposta enviada: {resposta}")
        except Exception as e:
            print(f"[DNS ERRO] Falha ao processar pacote de {endereco_cliente}: {e}")

if __name__ == "__main__":
    iniciar_servidor_dns()