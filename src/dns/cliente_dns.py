import socket
import random

def resolver_nome(nome_dominio, dns_ip='127.0.0.1', dns_port=53, timeout=2.0, max_tentativas=3):
    req_id = str(random.randint(1000, 9999))
    mensagem = f"{req_id}|{nome_dominio}"
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout) 
    
    try:
        # Loop de tentativas para lidar com perda de pacotes no UDP puro
        for tentativa in range(1, max_tentativas + 1):
            try:
                print(f"[Cliente DNS] Enviando query A '{nome_dominio}' (ID: {req_id}) [Tentativa {tentativa}/{max_tentativas}]")
                sock.sendto(mensagem.encode('utf-8'), (dns_ip, dns_port))
                
                dados, _ = sock.recvfrom(1024)
                resposta = dados.decode('utf-8')
                
                partes = resposta.split('|')
                if len(partes) == 3:
                    resp_id, resp_name, resp_ip = partes
                    
                    if resp_id == req_id and resp_name == nome_dominio:
                        if resp_ip == "0.0.0.0":
                            print(f"[Cliente DNS] Falha: Domínio '{nome_dominio}' não encontrado.")
                            return None
                        print(f"[Cliente DNS] Resolução concluída: '{nome_dominio}' -> {resp_ip}")
                        return resp_ip
                    else:
                        print("[Cliente DNS] ERRO: ID ou Nome da resposta não correspondem.")
                        return None
                        
            except socket.timeout:
                print(f"[Cliente DNS] Timeout na tentativa {tentativa}. O pacote DNS pode ter sido perdido.")
                continue # Tenta de novo se ainda não atingiu max_tentativas
                
        print(f"[Cliente DNS] Falha total: Sem resposta após {max_tentativas} tentativas.")
        return None

    except Exception as e:
        print(f"[Cliente DNS] Erro inesperado: {e}")
        return None
    finally:
        sock.close()

if __name__ == "__main__":
    ip = resolver_nome("servidor-web")
    print(f"IP final obtido no teste: {ip}")