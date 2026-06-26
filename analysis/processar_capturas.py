"""
Processador de CSVs de Captura de Tráfego e Logs de Aplicação
==============================================================
Unifica os dados de duas fontes em um formato comum por tamanho de arquivo:

Fonte 1 — Logs da aplicação (prefixo HTTP):
    data/logs/HTTP-TCP_100KB.csv   (todos os cenários juntos)
    data/logs/HTTP-RUDP_100KB.csv
    ...

Fonte 2 — Capturas de tráfego exportadas do Wireshark:
    data/capturas/csv-capturas-tcp/tcp_cenA_100kb.csv   (por cenário)
    data/capturas/csv-capturas-rudp/rudp_cenA_100kb.csv
    ...

Saída — CSVs unificados por tamanho, com colunas padronizadas:
    data/processados/unificado_100KB.csv
    data/processados/unificado_500KB.csv
    data/processados/unificado_1MB.csv

Colunas do CSV de saída:
    Fonte, Protocolo, Cenário, Tamanho, Duração(s), Throughput(KB/s)

Uso:
    python3 analysis/processar_capturas.py
"""

import os
import pandas as pd

BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR_LOGS     = os.path.join(BASE_DIR, "data", "logs")
DIR_CAP_TCP  = os.path.join(BASE_DIR, "data", "capturas", "csv-capturas-tcp")
DIR_CAP_RUDP = os.path.join(BASE_DIR, "data", "capturas", "csv-capturas-rudp")
DIR_SAIDA    = os.path.join(BASE_DIR, "data", "processados")

TAMANHOS    = ["100KB", "500KB", "1MB"]
CENARIO_MAP = {"cenA": "cenarioA", "cenB": "cenarioB", "cenC": "cenarioC"}
TAMANHO_KB  = {"100KB": 100, "500KB": 500, "1MB": 1024}

IP_CLIENTE  = "172.20.0.4"
IP_SERVIDOR = "172.20.0.3"


# ── Logs da aplicação ──────────────────────────────────────────────────────────

def processar_log_aplicacao(protocolo_label, tamanho):
    nome = f"HTTP-{protocolo_label}_{tamanho}.csv"
    caminho = os.path.join(DIR_LOGS, nome)
    if not os.path.exists(caminho):
        print(f"  [AVISO] Log não encontrado: {caminho}")
        return pd.DataFrame()

    df = pd.read_csv(caminho)
    df.columns = df.columns.str.strip()

    resultado = pd.DataFrame({
        "Fonte":            "Aplicação",
        "Protocolo":        protocolo_label,
        "Cenário":          df["Cenário"],
        "Tamanho":          tamanho,
        "Duração(s)":       df["Duração(s)"].astype(float),
        "Throughput(KB/s)": df["Throughput(KB/s)"].astype(float),
    })
    print(f"  [LOG] {nome}: {len(resultado)} registros")
    return resultado


# ── Capturas TCP ───────────────────────────────────────────────────────────────

def extrair_sessoes_tcp(df_raw):
    """
    Início: [SYN] do cliente para o servidor (sem ACK).
    Fim:    [FIN, ACK] do cliente para o servidor.
    """
    sessoes = []
    inicio = None
    for _, row in df_raw.iterrows():
        info = str(row.get("Info", ""))
        src  = str(row.get("Source", ""))
        dst  = str(row.get("Destination", ""))
        t    = float(row.get("Time", 0))

        if (src == IP_CLIENTE and dst == IP_SERVIDOR
                and "[SYN]" in info and "[SYN, ACK]" not in info):
            inicio = t
        elif (src == IP_CLIENTE and dst == IP_SERVIDOR
              and "[FIN, ACK]" in info and inicio is not None):
            sessoes.append((inicio, t))
            inicio = None
    return sessoes


def processar_captura_tcp(cenario_label, tamanho):
    nome = f"tcp_{cenario_label}_{tamanho.lower()}.csv"
    caminho = os.path.join(DIR_CAP_TCP, nome)
    if not os.path.exists(caminho):
        print(f"  [AVISO] Captura TCP não encontrada: {caminho}")
        return pd.DataFrame()

    df_raw = pd.read_csv(caminho)
    df_raw.columns = df_raw.columns.str.strip().str.replace('"', '')

    sessoes = extrair_sessoes_tcp(df_raw)
    if not sessoes:
        print(f"  [AVISO] Nenhuma sessão TCP em: {nome}")
        return pd.DataFrame()

    cenario_nome = CENARIO_MAP.get(cenario_label, cenario_label)
    tam_kb = TAMANHO_KB[tamanho]

    registros = []
    for t_ini, t_fim in sessoes:
        dur = t_fim - t_ini
        registros.append({
            "Fonte":            "Captura",
            "Protocolo":        "TCP",
            "Cenário":          cenario_nome,
            "Tamanho":          tamanho,
            "Duração(s)":       round(dur, 4),
            "Throughput(KB/s)": round(tam_kb / dur, 2) if dur > 0 else 0,
        })

    print(f"  [CAP-TCP] {nome}: {len(registros)} sessões")
    return pd.DataFrame(registros)


# ── Capturas R-UDP ─────────────────────────────────────────────────────────────

def extrair_sessoes_rudp(df_raw):
    """
    Padrão identificado nos dados reais:
      Início: pacote do cliente com Length=268 (GET empacotado em R-UDP, Len=226)
      Fim:    5 ACKs consecutivos do cliente com Length=113 (Len=71) que vêm
              logo após o pacote do servidor com Length=296 (FIN R-UDP, Len=254)

    Obs: Length é o tamanho do frame Ethernet, não do payload UDP.
    """
    sessoes = []
    inicio = None
    aguardando_acks = False
    acks = 0
    t_ult = None

    for _, row in df_raw.iterrows():
        src = str(row.get("Source", ""))
        dst = str(row.get("Destination", ""))
        t   = float(row.get("Time", 0))
        try:
            length = int(row.get("Length", 0))
        except (ValueError, TypeError):
            length = 0

        # Início: GET do cliente (Length=268)
        if src == IP_CLIENTE and dst == IP_SERVIDOR and length == 268:
            inicio = t
            aguardando_acks = False
            acks = 0

        # FIN do servidor (Length=296)
        elif (src == IP_SERVIDOR and dst == IP_CLIENTE
              and length == 296 and inicio is not None):
            aguardando_acks = True
            acks = 0

        # ACKs finais do cliente (Length=113) após o FIN
        elif (aguardando_acks and src == IP_CLIENTE
              and dst == IP_SERVIDOR and length == 113):
            acks += 1
            t_ult = t
            if acks >= 5:
                sessoes.append((inicio, t_ult))
                inicio = None
                aguardando_acks = False
                acks = 0

        else:
            # Qualquer outro pacote (DNS, fragmentos) não quebra a contagem
            # só reseta se vier do cliente para o servidor e não for Length=113
            if aguardando_acks and src == IP_CLIENTE and length != 113:
                aguardando_acks = False
                acks = 0

    return sessoes


def processar_captura_rudp(cenario_label, tamanho):
    nome = f"rudp_{cenario_label}_{tamanho.lower()}.csv"
    caminho = os.path.join(DIR_CAP_RUDP, nome)
    if not os.path.exists(caminho):
        print(f"  [AVISO] Captura RUDP não encontrada: {caminho}")
        return pd.DataFrame()

    df_raw = pd.read_csv(caminho)
    df_raw.columns = df_raw.columns.str.strip().str.replace('"', '')

    sessoes = extrair_sessoes_rudp(df_raw)
    if not sessoes:
        print(f"  [AVISO] Nenhuma sessão R-UDP em: {nome}")
        return pd.DataFrame()

    cenario_nome = CENARIO_MAP.get(cenario_label, cenario_label)
    tam_kb = TAMANHO_KB[tamanho]

    registros = []
    for t_ini, t_fim in sessoes:
        dur = t_fim - t_ini
        registros.append({
            "Fonte":            "Captura",
            "Protocolo":        "RUDP",
            "Cenário":          cenario_nome,
            "Tamanho":          tamanho,
            "Duração(s)":       round(dur, 4),
            "Throughput(KB/s)": round(tam_kb / dur, 2) if dur > 0 else 0,
        })

    print(f"  [CAP-RUDP] {nome}: {len(registros)} sessões")
    return pd.DataFrame(registros)


# ── Pipeline principal ─────────────────────────────────────────────────────────

def main():
    os.makedirs(DIR_SAIDA, exist_ok=True)

    for tamanho in TAMANHOS:
        print(f"\n{'='*55}")
        print(f" Processando tamanho: {tamanho}")
        print(f"{'='*55}")

        partes = []

        for protocolo in ["TCP", "RUDP"]:
            df = processar_log_aplicacao(protocolo, tamanho)
            if not df.empty:
                partes.append(df)

        for cenario_label in ["cenA", "cenB", "cenC"]:
            df = processar_captura_tcp(cenario_label, tamanho)
            if not df.empty:
                partes.append(df)

            df = processar_captura_rudp(cenario_label, tamanho)
            if not df.empty:
                partes.append(df)

        if not partes:
            print(f"  [AVISO] Nenhum dado para {tamanho}. Pulando.")
            continue

        df_unificado = pd.concat(partes, ignore_index=True)

        ordem = {"cenarioA": 0, "cenarioB": 1, "cenarioC": 2}
        df_unificado["_ord"] = df_unificado["Cenário"].map(ordem)
        df_unificado = (df_unificado
                        .sort_values(["Protocolo", "_ord", "Fonte"])
                        .drop(columns=["_ord"])
                        .reset_index(drop=True))

        caminho_saida = os.path.join(DIR_SAIDA, f"unificado_{tamanho}.csv")
        df_unificado.to_csv(caminho_saida, index=False)

        print(f"\n  Salvo: {caminho_saida}  ({len(df_unificado)} registros)")
        print(df_unificado.groupby(["Protocolo", "Cenário", "Fonte"]).size().to_string())


if __name__ == "__main__":
    main()
