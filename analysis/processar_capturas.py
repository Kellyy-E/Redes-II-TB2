"""
Processador de CSVs de Captura de Tráfego e Logs de Aplicação
==============================================================
Gera:
  data/processados/unificado_{tamanho}.csv   — throughput por sessão
  data/tabelas/overhead_rede.csv             — overhead de rede por protocolo/cenário/tamanho

Uso:
    python3 analysis/processar_capturas.py
"""

import os
import re
import pandas as pd

# Define o BASE_DIR como a raiz do projeto
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

if os.path.exists(os.path.join(SCRIPT_DIR, "data")):
    BASE_DIR = SCRIPT_DIR
elif os.path.exists(os.path.join(os.path.dirname(SCRIPT_DIR), "data")):
    BASE_DIR = os.path.dirname(SCRIPT_DIR)
else:
    BASE_DIR = SCRIPT_DIR

DIR_LOGS     = os.path.join(BASE_DIR, "data", "logs")
DIR_CAP_TCP  = os.path.join(BASE_DIR, "data", "capturas", "csv-capturas-tcp")
DIR_CAP_RUDP = os.path.join(BASE_DIR, "data", "capturas", "csv-capturas-rudp")
DIR_SAIDA    = os.path.join(BASE_DIR, "data", "processados")
DIR_TABELAS  = os.path.join(BASE_DIR, "data", "tabelas")

TAMANHOS    = ["100KB", "500KB", "1MB"]
CENARIO_MAP = {"cenA": "cenarioA", "cenB": "cenarioB", "cenC": "cenarioC"}
TAMANHO_KB  = {"100KB": 100, "500KB": 500, "1MB": 1024}
TAMANHO_BYTES = {"100KB": 102400, "500KB": 512000, "1MB": 1048576}

IP_CLIENTE  = "172.20.0.4"
IP_SERVIDOR = "172.20.0.3"
IP_DNS      = "172.20.0.2"


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
    sessoes = []
    inicio = None
    bytes_sessao = 0

    for _, row in df_raw.iterrows():
        info = str(row.get("Info", ""))
        src  = str(row.get("Source", ""))
        dst  = str(row.get("Destination", ""))
        t    = float(row.get("Time", 0))
        try:
            length = int(row.get("Length", 0))
        except (ValueError, TypeError):
            length = 0

        if IP_DNS in (src, dst):
            continue

        if (src == IP_CLIENTE and dst == IP_SERVIDOR
                and "[SYN]" in info and "[SYN, ACK]" not in info):
            inicio = t
            bytes_sessao = length

        elif inicio is not None:
            bytes_sessao += length
            if src == IP_CLIENTE and dst == IP_SERVIDOR and "[FIN, ACK]" in info:
                sessoes.append((inicio, t, bytes_sessao))
                inicio = None
                bytes_sessao = 0

    return sessoes


def processar_captura_tcp(cenario_label, tamanho):
    nome = f"tcp_{cenario_label}_{tamanho.lower()}.csv"
    caminho = os.path.join(DIR_CAP_TCP, nome)
    if not os.path.exists(caminho):
        print(f"  [AVISO] Captura TCP não encontrada: {caminho}")
        return pd.DataFrame(), []

    df_raw = pd.read_csv(caminho)
    df_raw.columns = df_raw.columns.str.strip().str.replace('"', '')

    sessoes = extrair_sessoes_tcp(df_raw)
    if not sessoes:
        print(f"  [AVISO] Nenhuma sessão TCP em: {nome}")
        return pd.DataFrame(), []

    cenario_nome = CENARIO_MAP.get(cenario_label, cenario_label)
    tam_kb = TAMANHO_KB[tamanho]
    bytes_uteis = TAMANHO_BYTES[tamanho]

    registros = []
    overhead_registros = []

    for t_ini, t_fim, bytes_cap in sessoes:
        dur = t_fim - t_ini
        registros.append({
            "Fonte":            "Captura",
            "Protocolo":        "TCP",
            "Cenário":          cenario_nome,
            "Tamanho":          tamanho,
            "Duração(s)":       round(dur, 4),
            "Throughput(KB/s)": round(tam_kb / dur, 2) if dur > 0 else 0,
        })
        overhead_registros.append({
            "Protocolo":        "TCP",
            "Cenário":          cenario_nome,
            "Tamanho":          tamanho,
            "Bytes úteis":      bytes_uteis,
            "Bytes capturados": bytes_cap,
        })

    print(f"  [CAP-TCP] {nome}: {len(registros)} sessões")
    return pd.DataFrame(registros), overhead_registros


# ── Capturas R-UDP ─────────────────────────────────────────────────────────────

def extrair_sessoes_rudp(df_raw):
    """
    Identifica sessões R-UDP pela porta efêmera do cliente → porta 8081.
    Lida com a fragmentação IP reconstruindo o tamanho provável do datagrama UDP.
    """
    sessoes_por_porta = {}

    for _, row in df_raw.iterrows():
        src  = str(row.get("Source", ""))
        dst  = str(row.get("Destination", ""))
        info = str(row.get("Info", ""))
        t    = float(row.get("Time", 0))
        try:
            length = int(row.get("Length", 0))
        except (ValueError, TypeError):
            length = 0

        if IP_DNS in (src, dst):
            continue
        if IP_CLIENTE not in (src, dst) or IP_SERVIDOR not in (src, dst):
            continue

        m = re.search(r'(\d+)\s*>\s*(\d+)', info)
        if not m:
            continue
        p1, p2 = m.group(1), m.group(2)

        if src == IP_CLIENTE and p2 == "8081":
            porta = p1
        elif dst == IP_CLIENTE and p1 == "8081":
            porta = p2
        else:
            continue

        # Início da sessão: Pacote do cliente para servidor com tamanho compatível com GET (260-275 bytes)
        # O tamanho varia conforme o nome do arquivo na requisição GET (100kb vs 1mb)
        if src == IP_CLIENTE and (260 <= length <= 275) and porta not in sessoes_por_porta:
            sessoes_por_porta[porta] = {
                "t_ini": t, "t_fim": t,
                "aguardando_fim": False,
            }
            continue

        if porta in sessoes_por_porta:
            s = sessoes_por_porta[porta]
            s["t_fim"] = t
            if src == IP_SERVIDOR and length == 297:
                s["aguardando_fim"] = True

    sessoes = []
    for porta, s in sessoes_por_porta.items():
        dur = s["t_fim"] - s["t_ini"]
        if dur <= 0:
            continue

        mask = (
            (df_raw["Time"].astype(float) >= s["t_ini"]) &
            (df_raw["Time"].astype(float) <= s["t_fim"]) &
            (
                ((df_raw["Source"] == IP_CLIENTE) & (df_raw["Destination"] == IP_SERVIDOR)) |
                ((df_raw["Source"] == IP_SERVIDOR) & (df_raw["Destination"] == IP_CLIENTE))
            )
        )
        
        sessao_df = df_raw.loc[mask]
        bytes_total = 0
        for _, p in sessao_df.iterrows():
            if p["Length"] == 1514 and "Fragmented IP" in str(p["Info"]):
                bytes_total += 4160 
            else:
                bytes_total += int(p["Length"])
        
        sessoes.append((s["t_ini"], s["t_fim"], bytes_total))

    return sorted(sessoes, key=lambda x: x[0])


def processar_captura_rudp(cenario_label, tamanho):
    nome = f"rudp_{cenario_label}_{tamanho.lower()}.csv"
    caminho = os.path.join(DIR_CAP_RUDP, nome)
    if not os.path.exists(caminho):
        print(f"  [AVISO] Captura RUDP não encontrada: {caminho}")
        return pd.DataFrame(), []

    df_raw = pd.read_csv(caminho)
    df_raw.columns = df_raw.columns.str.strip().str.replace('"', '')

    sessoes = extrair_sessoes_rudp(df_raw)
    if not sessoes:
        print(f"  [AVISO] Nenhuma sessão R-UDP em: {nome}")
        return pd.DataFrame(), []

    cenario_nome = CENARIO_MAP.get(cenario_label, cenario_label)
    tam_kb = TAMANHO_KB[tamanho]
    bytes_uteis = TAMANHO_BYTES[tamanho]

    registros = []
    overhead_registros = []

    for t_ini, t_fim, bytes_cap in sessoes:
        dur = t_fim - t_ini
        registros.append({
            "Fonte":            "Captura",
            "Protocolo":        "RUDP",
            "Cenário":          cenario_nome,
            "Tamanho":          tamanho,
            "Duração(s)":       round(dur, 4),
            "Throughput(KB/s)": round(tam_kb / dur, 2) if dur > 0 else 0,
        })
        overhead_registros.append({
            "Protocolo":        "RUDP",
            "Cenário":          cenario_nome,
            "Tamanho":          tamanho,
            "Bytes úteis":      bytes_uteis,
            "Bytes capturados": bytes_cap,
        })

    print(f"  [CAP-RUDP] {nome}: {len(registros)} sessões")
    return pd.DataFrame(registros), overhead_registros


# ── Tabela de overhead ─────────────────────────────────────────────────────────

def gerar_tabela_overhead(todos_overheads):
    if not todos_overheads:
        print("  [AVISO] Nenhum dado de overhead coletado.")
        return

    df = pd.DataFrame(todos_overheads)

    resumo = (df.groupby(["Protocolo", "Cenário", "Tamanho"])
                .agg(
                    Bytes_uteis     =("Bytes úteis",      "first"),
                    Bytes_cap_media =("Bytes capturados", "mean"),
                    N               =("Bytes capturados", "count"),
                )
                .reset_index())

    resumo["Overhead (%)"] = (
        (resumo["Bytes_cap_media"] - resumo["Bytes_uteis"])
        / resumo["Bytes_uteis"] * 100
    ).round(2)

    resumo["Bytes_cap_media"] = resumo["Bytes_cap_media"].round(0).astype(int)

    resumo = resumo.rename(columns={
        "Bytes_uteis":     "Bytes úteis",
        "Bytes_cap_media": "Bytes capturados",
    })[["Protocolo", "Cenário", "Tamanho",
        "Bytes úteis", "Bytes capturados", "Overhead (%)", "N"]]

    ordem_cen = {"cenarioA": 0, "cenarioB": 1, "cenarioC": 2}
    ordem_tam = {"100KB": 0, "500KB": 1, "1MB": 2}
    resumo["_oc"] = resumo["Cenário"].map(ordem_cen)
    resumo["_ot"] = resumo["Tamanho"].map(ordem_tam)
    resumo = (resumo.sort_values(["Protocolo", "_oc", "_ot"])
                     .drop(columns=["_oc", "_ot"])
                     .reset_index(drop=True))

    os.makedirs(DIR_TABELAS, exist_ok=True)
    caminho = os.path.join(DIR_TABELAS, "overhead_rede.csv")
    resumo.to_csv(caminho, index=False)
    print(f"\n  [OK] Tabela de overhead: {caminho}")
    print(resumo.to_string(index=False))


# ── Pipeline principal ─────────────────────────────────────────────────────────

def main():
    os.makedirs(DIR_SAIDA,   exist_ok=True)
    os.makedirs(DIR_TABELAS, exist_ok=True)

    todos_overheads = []

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
            df_tcp, oh_tcp = processar_captura_tcp(cenario_label, tamanho)
            if not df_tcp.empty:
                partes.append(df_tcp)
                todos_overheads.extend(oh_tcp)

            df_rudp, oh_rudp = processar_captura_rudp(cenario_label, tamanho)
            if not df_rudp.empty:
                partes.append(df_rudp)
                todos_overheads.extend(oh_rudp)

        if not partes:
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

    print(f"\n{'='*55}")
    print(" TABELA DE OVERHEAD DE REDE")
    print(f"{'='*55}")
    gerar_tabela_overhead(todos_overheads)


if __name__ == "__main__":
    main()
