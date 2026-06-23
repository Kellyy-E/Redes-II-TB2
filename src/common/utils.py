import os
import hashlib
import struct
import csv
from datetime import datetime

FLAG_DATA = 0  # Pacote contendo uma parte do arquivo
FLAG_ACK  = 1  # Pacote de confirmação (sem dados)
FLAG_SYN  = 2  # Início de conexão 
FLAG_FIN  = 3  # Fim de transmissão 

def gerar_x_custom_auth(matricula, nome):
    string_base = f"{matricula}{nome.strip()}"
    return hashlib.sha256(string_base.encode()).hexdigest()

def calcular_checksum(dados):
    if len(dados) % 2 == 1:
        dados += b'\0'
    s = sum(struct.unpack("!%dH" % (len(dados) // 2), dados))
    s = (s >> 16) + (s & 0xffff)
    s += s >> 16
    return ~s & 0xffff

class Packet:
    # Estrutura: !I (Seq: 4b) + H (Checksum: 2b) + B (Flags: 1b) + 64s (Auth: 64b)
    HEADER_FORMAT = "!IHB64s"

    def __init__(self, seq, flags, auth_hash, data=b''):
        self.seq = seq
        self.flags = flags
        self.auth_hash = auth_hash.encode()
        self.data = data
        self.checksum = 0

    def pack(self):
        #Transforma o objeto em bytes para enviar pela rede

        # Primeiro calcula o checksum com campo zerado
        header_temp = struct.pack(self.HEADER_FORMAT, self.seq, 0, self.flags, self.auth_hash)
        self.checksum = calcular_checksum(header_temp + self.data)
        
        # Agora empacota com o checksum real
        header = struct.pack(self.HEADER_FORMAT, self.seq, self.checksum, self.flags, self.auth_hash)
        return header + self.data

    @staticmethod
    def unpack(packet_bytes):
        #Transforma bytes recebidos em um objeto Packet.
        header_size = struct.calcsize(Packet.HEADER_FORMAT)
        header_bytes = packet_bytes[:header_size]
        data = packet_bytes[header_size:]
        
        seq, checksum, flags, auth_hash = struct.unpack(Packet.HEADER_FORMAT, header_bytes)
        
        return Packet(seq, flags, auth_hash.decode(), data), checksum
    



def salvar_log_csv(protocolo, arquivo, tempo_inicio, tempo_fim, tamanho_bytes):    
    duracao = tempo_fim - tempo_inicio
    throughput = (tamanho_bytes / 1024) / duracao if duracao > 0 else 0
    
    log_file = f"{protocolo}metricas_desempenho.csv"
    file_exists = os.path.isfile(log_file)
    
    with open(log_file, mode='a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['Data/Hora', 'Protocolo', 'Arquivo', 'Duração(s)', 'Throughput(KB/s)'])
        
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            protocolo,
            arquivo,
            f"{duracao:.4f}",
            f"{throughput:.2f}"
        ])
    print(f"Log salvo em {log_file}")