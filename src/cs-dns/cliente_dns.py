import socket
import random

def resolver_nome(nome_dominio, dns_ip='127.0.0.1', dns_port=5354, timeout=2.0):
    """
    Resolve um nome de domínio consultando o Miniservidor DNS via UDP.
    Retorna o IP resolvido ou None em caso de falha/timeout.
    """
    # Geração de ID simplificado para a transação
    req_id = str(random.randint(1000, 9999))
    
    # Formato de requisição (ID|Name)
    mensagem = f"{req_id}|{nome_dominio}"
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout) # Timeout na aplicação cliente para evitar bloqueio infinito
    
    try:
        print(f"[Cliente DNS] Enviando query A para '{nome_dominio}' (ID: {req_id}) ao DNS {dns_ip}:{dns_port}")
        sock.sendto(mensagem.encode('utf-8'), (dns_ip, dns_port))
        
        # Aguarda a resposta (Formato: ID|Name|IP)
        dados, _ = sock.recvfrom(1024)
        resposta = dados.decode('utf-8')
        
        partes = resposta.split('|')
        if len(partes) == 3:
            resp_id, resp_name, resp_ip = partes
            
            # Validação do ID da transação
            if resp_id == req_id and resp_name == nome_dominio:
                if resp_ip == "0.0.0.0":
                    print(f"[Cliente DNS] Falha na resolução: Domínio '{nome_dominio}' não encontrado.")
                    return None
                print(f"[Cliente DNS] Resolução concluída: '{nome_dominio}' -> {resp_ip}")
                return resp_ip
            else:
                print("[Cliente DNS] ERRO: ID ou Nome da resposta não correspondem à requisição.")
                return None
                
    except socket.timeout:
        print(f"[Cliente DNS] Timeout da requisição UDP para {nome_dominio}. O pacote pode ter sido perdido.")
        return None
    except Exception as e:
        print(f"[Cliente DNS] Erro inesperado: {e}")
        return None
    finally:
        sock.close()

# Bloco de teste independente
if __name__ == "__main__":
    ip = resolver_nome("servidor-web")
    print(f"IP final obtido no teste: {ip}")