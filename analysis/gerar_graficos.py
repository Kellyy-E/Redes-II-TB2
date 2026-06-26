"""
Gerador de Gráficos e Tabelas Estatísticas — Terceira Avaliação
================================================================
Lê os CSVs unificados em data/processados/ e gera:

Gráficos (.png em data/graficos/):
  1. throughput_barras_{tamanho}.png  — Barras agrupadas TCP vs R-UDP por cenário
                                        (linhas separadas para Aplicação e Captura)
  2. throughput_boxplot_{tamanho}.png — Boxplot por protocolo × cenário
  3. duracao_dns_barras.png           — Tempo médio de resolução DNS por cenário
                                        (usando CSVs DNS-TCP / DNS-RUDP em data/logs/)
  4. tempo_empilhado_{tamanho}.png    — Barras empilhadas DNS + HTTP por protocolo × cenário

Tabelas (.csv em data/tabelas/):
  1. estatisticas_{tamanho}.csv       — Média, desvio padrão, mín, máx por grupo
  2. estatisticas_dns.csv             — Mesmas métricas para o tempo de resolução DNS

Uso:
  python3 analysis/gerar_graficos.py
"""

import os
import warnings
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

warnings.filterwarnings("ignore")

# ─── Caminhos ─────────────────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR_PROC      = os.path.join(BASE_DIR, "data", "processados")
DIR_LOGS      = os.path.join(BASE_DIR, "data", "logs")
DIR_GRAFICOS  = os.path.join(BASE_DIR, "data", "graficos")
DIR_TABELAS   = os.path.join(BASE_DIR, "data", "tabelas")

TAMANHOS = ["100KB", "500KB", "1MB"]
CENARIOS = ["cenarioA", "cenarioB", "cenarioC"]
CEN_LABEL = {"cenarioA": "Cenário A\n(0% perda / 10ms)",
             "cenarioB": "Cenário B\n(5% perda / 50ms)",
             "cenarioC": "Cenário C\n(10% perda / 100ms)"}

# Paleta consistente
COR = {
    ("TCP",  "Aplicação"): "#2196F3",
    ("TCP",  "Captura"):   "#0D47A1",
    ("RUDP", "Aplicação"): "#FF9800",
    ("RUDP", "Captura"):   "#E65100",
}
COR_PROT = {"TCP": "#2196F3", "RUDP": "#FF9800"}
COR_DNS  = {"TCP": "#4CAF50", "RUDP": "#9C27B0"}

DPI = 150


# ─── Utilitários ──────────────────────────────────────────────────────────────

def salvar(fig, nome):
    os.makedirs(DIR_GRAFICOS, exist_ok=True)
    caminho = os.path.join(DIR_GRAFICOS, nome)
    fig.savefig(caminho, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print(f"  [OK] {caminho}")


def estatisticas(df, grupo_cols):
    return (df.groupby(grupo_cols)["Throughput(KB/s)"]
              .agg(Media="mean", DesvPad="std", Minimo="min", Maximo="max", N="count")
              .round(2)
              .reset_index())


def carregar_unificado(tamanho):
    caminho = os.path.join(DIR_PROC, f"unificado_{tamanho}.csv")
    if not os.path.exists(caminho):
        print(f"  [AVISO] Não encontrado: {caminho}")
        return pd.DataFrame()
    return pd.read_csv(caminho)


def carregar_dns():
    """Carrega todos os CSVs de log DNS (DNS-TCP e DNS-RUDP) em um único DF."""
    frames = []
    for protocolo in ["TCP", "RUDP"]:
        for tamanho in TAMANHOS:
            nome = f"DNS-{protocolo}_{tamanho}.csv"
            caminho = os.path.join(DIR_LOGS, nome)
            if os.path.exists(caminho):
                df = pd.read_csv(caminho)
                df.columns = df.columns.str.strip()
                df["Protocolo"] = protocolo
                df["Tamanho"] = tamanho
                frames.append(df)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


# ─── Gráfico 1: Barras agrupadas de throughput ────────────────────────────────

def grafico_barras_throughput(tamanho):
    df = carregar_unificado(tamanho)
    if df.empty:
        return

    grupos = [("TCP", "Aplicação"), ("TCP", "Captura"),
              ("RUDP", "Aplicação"), ("RUDP", "Captura")]
    # Filtra só os grupos que existem
    grupos = [(p, f) for p, f in grupos
              if not df[(df["Protocolo"] == p) & (df["Fonte"] == f)].empty]

    n_grupos = len(CENARIOS)
    n_barras = len(grupos)
    largura  = 0.8 / n_barras
    x        = np.arange(n_grupos)

    fig, ax = plt.subplots(figsize=(10, 5))

    for i, (prot, fonte) in enumerate(grupos):
        subset = df[(df["Protocolo"] == prot) & (df["Fonte"] == fonte)]
        medias = []
        erros  = []
        for cen in CENARIOS:
            vals = subset[subset["Cenário"] == cen]["Throughput(KB/s)"]
            medias.append(vals.mean() if len(vals) > 0 else 0)
            erros.append(vals.std()  if len(vals) > 0 else 0)

        offset = (i - n_barras / 2 + 0.5) * largura
        bars = ax.bar(x + offset, medias, largura,
                      yerr=erros, capsize=4,
                      color=COR.get((prot, fonte), "#888"),
                      label=f"{prot} — {fonte}",
                      alpha=0.88, edgecolor="white", linewidth=0.5)

    ax.set_xticks(x)
    ax.set_xticklabels([CEN_LABEL[c] for c in CENARIOS], fontsize=9)
    ax.set_ylabel("Throughput médio (KB/s)", fontsize=10)
    ax.set_title(f"Throughput por Protocolo e Cenário — {tamanho}", fontsize=12, fontweight="bold")
    ax.legend(fontsize=8, ncol=2)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    salvar(fig, f"throughput_barras_{tamanho}.png")


# ─── Gráfico 2: Boxplot de throughput ─────────────────────────────────────────

def grafico_boxplot_throughput(tamanho):
    df = carregar_unificado(tamanho)
    if df.empty:
        return

    # Um boxplot por protocolo × cenário, colorido pelo protocolo
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=False)

    for ax, prot in zip(axes, ["TCP", "RUDP"]):
        dados  = []
        labels = []
        for cen in CENARIOS:
            sub = df[(df["Protocolo"] == prot) & (df["Cenário"] == cen)]
            # Mostra Aplicação e Captura sobrepostos se ambos existirem
            for fonte in ["Aplicação", "Captura"]:
                vals = sub[sub["Fonte"] == fonte]["Throughput(KB/s)"].dropna()
                if len(vals) > 0:
                    dados.append(vals.values)
                    labels.append(f"{CEN_LABEL[cen].split(chr(10))[0]}\n({fonte})")

        if not dados:
            ax.set_visible(False)
            continue

        bp = ax.boxplot(dados, patch_artist=True, notch=False,
                        medianprops=dict(color="black", linewidth=2))

        cor = COR_PROT[prot]
        for patch in bp["boxes"]:
            patch.set_facecolor(cor)
            patch.set_alpha(0.6)

        ax.set_xticklabels(labels, fontsize=7.5)
        ax.set_ylabel("Throughput (KB/s)", fontsize=9)
        ax.set_title(f"{prot} — {tamanho}", fontsize=11, fontweight="bold")
        ax.grid(axis="y", linestyle="--", alpha=0.4)

    fig.suptitle(f"Distribuição do Throughput — {tamanho}", fontsize=13, fontweight="bold")
    fig.tight_layout()
    salvar(fig, f"throughput_boxplot_{tamanho}.png")


# ─── Gráfico 3: Tempo de resolução DNS ────────────────────────────────────────

def grafico_dns():
    df = carregar_dns()
    if df.empty:
        print("  [AVISO] Nenhum log DNS encontrado. Pulando gráfico DNS.")
        return

    # Renomeia coluna de duração se necessário
    col_dur = "Duração(s)" if "Duração(s)" in df.columns else df.columns[3]
    df = df.rename(columns={col_dur: "Duração(s)"})
    df["Duração(ms)"] = df["Duração(s)"].astype(float) * 1000

    fig, ax = plt.subplots(figsize=(10, 5))

    protocolos = ["TCP", "RUDP"]
    n_cen   = len(CENARIOS)
    largura = 0.35
    x       = np.arange(n_cen)

    for i, prot in enumerate(protocolos):
        sub    = df[df["Protocolo"] == prot]
        medias = []
        erros  = []
        for cen in CENARIOS:
            vals = sub[sub["Cenário"] == cen]["Duração(ms)"]
            medias.append(vals.mean() if len(vals) > 0 else 0)
            erros.append(vals.std()   if len(vals) > 0 else 0)

        offset = (i - 0.5) * largura
        ax.bar(x + offset, medias, largura,
               yerr=erros, capsize=5,
               color=COR_DNS[prot], alpha=0.85,
               label=f"DNS-{prot}", edgecolor="white")

    ax.set_xticks(x)
    ax.set_xticklabels([CEN_LABEL[c] for c in CENARIOS], fontsize=9)
    ax.set_ylabel("Tempo médio de resolução DNS (ms)", fontsize=10)
    ax.set_title("Tempo de Resolução DNS por Cenário e Protocolo", fontsize=12, fontweight="bold")
    ax.legend(fontsize=9)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    salvar(fig, "duracao_dns_barras.png")


# ─── Gráfico 4: Barras empilhadas DNS + HTTP ──────────────────────────────────

def grafico_tempo_empilhado(tamanho):
    df_http = carregar_unificado(tamanho)
    df_dns  = carregar_dns()
    if df_http.empty or df_dns.empty:
        return

    col_dur = "Duração(s)" if "Duração(s)" in df_dns.columns else df_dns.columns[3]
    df_dns  = df_dns.rename(columns={col_dur: "Duração(s)"})
    df_dns["Duração(s)"] = df_dns["Duração(s)"].astype(float)

    # Usa só dados de Aplicação para o HTTP (mesmo nível de medição)
    df_app = df_http[df_http["Fonte"] == "Aplicação"].copy()
    df_app["Duração(s)"] = df_app["Duração(s)"].astype(float)

    protocolos = ["TCP", "RUDP"]
    n_cen   = len(CENARIOS)
    largura = 0.35
    x       = np.arange(n_cen)

    fig, ax = plt.subplots(figsize=(10, 5))

    for i, prot in enumerate(protocolos):
        medias_dns  = []
        medias_http = []

        for cen in CENARIOS:
            v_dns  = df_dns[(df_dns["Protocolo"] == prot) &
                            (df_dns["Cenário"]   == cen)  &
                            (df_dns["Tamanho"]   == tamanho)]["Duração(s)"]
            v_http = df_app[(df_app["Protocolo"] == prot) &
                            (df_app["Cenário"]   == cen)]["Duração(s)"]
            medias_dns.append(v_dns.mean()   if len(v_dns)  > 0 else 0)
            medias_http.append(v_http.mean() if len(v_http) > 0 else 0)

        medias_dns  = np.array(medias_dns)
        medias_http = np.array(medias_http)
        offset      = (i - 0.5) * largura

        cor_http = COR_PROT[prot]
        cor_dns  = COR_DNS[prot]

        ax.bar(x + offset, medias_dns,  largura,
               color=cor_dns,  alpha=0.9, label=f"DNS ({prot})")
        ax.bar(x + offset, medias_http, largura,
               bottom=medias_dns,
               color=cor_http, alpha=0.7, label=f"HTTP ({prot})")

    ax.set_xticks(x)
    ax.set_xticklabels([CEN_LABEL[c] for c in CENARIOS], fontsize=9)
    ax.set_ylabel("Tempo médio (s)", fontsize=10)
    ax.set_title(f"Tempo Total: DNS + HTTP por Protocolo e Cenário — {tamanho}",
                 fontsize=12, fontweight="bold")
    ax.legend(fontsize=8, ncol=2)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    salvar(fig, f"tempo_empilhado_{tamanho}.png")


# ─── Tabela 1: Estatísticas de throughput ─────────────────────────────────────

def tabela_estatisticas(tamanho):
    df = carregar_unificado(tamanho)
    if df.empty:
        return

    os.makedirs(DIR_TABELAS, exist_ok=True)
    est = estatisticas(df, ["Protocolo", "Cenário", "Fonte"])
    caminho = os.path.join(DIR_TABELAS, f"estatisticas_{tamanho}.csv")
    est.to_csv(caminho, index=False)
    print(f"  [OK] {caminho}")
    print(est.to_string(index=False))
    print()


# ─── Tabela 2: Estatísticas DNS ───────────────────────────────────────────────

def tabela_estatisticas_dns():
    df = carregar_dns()
    if df.empty:
        print("  [AVISO] Nenhum log DNS para tabela.")
        return

    col_dur = "Duração(s)" if "Duração(s)" in df.columns else df.columns[3]
    df = df.rename(columns={col_dur: "Duração(s)"})
    df["Duração(s)"] = df["Duração(s)"].astype(float) * 1000  # converte para ms

    os.makedirs(DIR_TABELAS, exist_ok=True)
    est = (df.groupby(["Protocolo", "Cenário"])["Duração(s)"]
             .agg(Media_ms="mean", DesvPad_ms="std",
                  Minimo_ms="min", Maximo_ms="max", N="count")
             .round(3)
             .reset_index())
    caminho = os.path.join(DIR_TABELAS, "estatisticas_dns.csv")
    est.to_csv(caminho, index=False)
    print(f"  [OK] {caminho}")
    print(est.to_string(index=False))
    print()


# ─── Pipeline principal ────────────────────────────────────────────────────────

def main():
    os.makedirs(DIR_GRAFICOS, exist_ok=True)
    os.makedirs(DIR_TABELAS,  exist_ok=True)

    print("\n" + "="*55)
    print(" TABELAS ESTATÍSTICAS")
    print("="*55)
    for tamanho in TAMANHOS:
        print(f"\n── {tamanho} ──")
        tabela_estatisticas(tamanho)

    print("\n── DNS ──")
    tabela_estatisticas_dns()

    print("\n" + "="*55)
    print(" GRÁFICOS")
    print("="*55)

    for tamanho in TAMANHOS:
        print(f"\n── {tamanho} ──")
        grafico_barras_throughput(tamanho)
        grafico_boxplot_throughput(tamanho)
        grafico_tempo_empilhado(tamanho)

    print("\n── DNS (geral) ──")
    grafico_dns()

    print(f"\nConcluído! Gráficos em: {DIR_GRAFICOS}")
    print(f"Tabelas em:   {DIR_TABELAS}")


if __name__ == "__main__":
    main()
