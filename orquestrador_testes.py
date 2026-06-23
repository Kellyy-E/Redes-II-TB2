import os
import subprocess
import time

EXECUCOES = 20  
ARQUIVO_ENTRADA = "data/arquivo_teste.bin"
CENARIOS = ["cenarioA","cenarioB", "cenarioC"]

def aplicar_rede(cenario):
    #Chama o script Bash para alterar as propriedades da rede via tc
    print(f"\nREDE CONFIGURADA NO CENARIO: {cenario}...")
    subprocess.run(["./docker/scripts/simular_rede.sh", cenario], check=True)
    time.sleep(2)  

def rodar_cliente(protocolo):
    #Executa o script cliente correspondente (TCP ou R-UDP)
    script = "src/tcp/cliente_tcp.py" if protocolo == "TCP" else "src/rudp/cliente_rudp.py"
    try:
        subprocess.run(["python3", script, ARQUIVO_ENTRADA], check=True)
    except subprocess.CalledProcessError as e:
        print(f"ERRO: Falha ao rodar o cliente {protocolo}: {e}")

def main():    
    subprocess.run(["./docker/scripts/simular_rede.sh", "limpar"], check=False)
    
    #ESCOLHA DO CENÁRIO A SER APLICADO
    aplicar_rede(CENARIOS[0])
        
    print(f"\n--- EXECUCOES RUDP ({CENARIOS[0]}) ---")
    for i in range(1, EXECUCOES + 1):
            print(f"[{i}/{EXECUCOES}] ", end="")
            #ESCOLHA DO PROTOCOLO QUE SERÁ UTILIZADO (TCP ou RUDP)
            rodar_cliente("TCP")
            time.sleep(0.5)  

    subprocess.run(["./docker/scripts/simular_rede.sh", "limpar"], check=True)

    print("="*20,"TESTES FINALIZADOS E SALVOS", "="*20)

if __name__ == "__main__":
    main()
