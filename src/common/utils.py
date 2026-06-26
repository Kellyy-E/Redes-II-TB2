import os
import hashlib
import struct
import csv
from datetime import datetime

FLAG_DATA = 0
FLAG_ACK  = 1
FLAG_SYN  = 2
FLAG_FIN  = 3

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
    HEADER_FORMAT = "!IHB64s"

    def __init__(self, seq, flags, auth_hash, data=b''):
        self.seq = seq
        self.flags = flags
        self.auth_hash = auth_hash.encode()
        self.data = data
        self.checksum = 0

    def pack(self):
        header_temp = struct.pack(self.HEADER_FORMAT, self.seq, 0, self.flags, self.auth_hash)
        self.checksum = calcular_checksum(header_temp + self.data)
        header = struct.pack(self.HEADER_FORMAT, self.seq, self.checksum, self.flags, self.auth_hash)
        return header + self.data

    @staticmethod
    def unpack(packet_bytes):
        header_size = struct.calcsize(Packet.HEADER_FORMAT)
        header_bytes = packet_bytes[:header_size]
        data = packet_bytes[header_size:]
        seq, checksum, flags, auth_hash = struct.unpack(Packet.HEADER_FORMAT, header_bytes)
        return Packet(seq, flags, auth_hash.decode(), data), checksum


def salvar_log_csv(protocolo, arquivo, tempo_inicio, tempo_fim,
                   tamanho_bytes, cenario=""):
    """
    Salva métricas em um CSV separado por protocolo, cenário e tamanho de arquivo.

    Nome do arquivo gerado:
        data/logs/<PROTOCOLO>_<cenario>_<tamanho>.csv
    Exemplo:
        data/logs/HTTP-TCP_cenarioA_100KB.csv
        data/logs/HTTP-RUDP_cenarioB_1MB.csv
    """
    duracao   = tempo_fim - tempo_inicio
    throughput = (tamanho_bytes / 1024) / duracao if duracao > 0 else 0

    log_dir = os.path.join(os.path.dirname(__file__), "../../data/logs")
    os.makedirs(log_dir, exist_ok=True)

    # Deriva o tamanho legível a partir do nome do arquivo (ex: arquivo_1mb.bin -> 1MB)
    nome_base = os.path.basename(arquivo)          # arquivo_1mb.bin
    tamanho_label = nome_base.replace("arquivo_", "").replace(".bin", "").upper()
    # ex: "1MB", "100KB", "10MB"

 # Removemos o sufixo do cenário do nome do arquivo
    nome_csv = f"{protocolo}_{tamanho_label}.csv"
    log_file = os.path.join(log_dir, nome_csv)

    file_exists = os.path.isfile(log_file)
    with open(log_file, mode='a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['Data/Hora', 'Protocolo', 'Cenário', 'Arquivo',
                             'Duração(s)', 'Throughput(KB/s)'])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            protocolo,
            cenario,
            arquivo,
            f"{duracao:.4f}",
            f"{throughput:.2f}"
        ])

    print(f"[LOG] {log_file}")
