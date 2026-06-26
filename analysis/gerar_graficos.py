import os
import warnings
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

# Caminhos 
SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
if os.path.exists(os.path.join(SCRIPT_DIR, "data")):
    BASE_DIR = SCRIPT_DIR
elif os.path.exists(os.path.join(os.path.dirname(SCRIPT_DIR), "data")):
    BASE_DIR = os.path.dirname(SCRIPT_DIR)
else:
    BASE_DIR = SCRIPT_DIR

DIR_PROC      = os.path.join(BASE_DIR, "data", "processados")
DIR_LOGS      = os.path.join(BASE_DIR, "data", "logs")
DIR_GRAFICOS  = os.path.join(BASE_DIR, "data", "graficos")
DIR_TABELAS   = os.path.join(BASE_DIR, "data", "tabelas")

TAMANHOS = ["100KB", "500KB", "1MB"]
CENARIOS = ["cenarioA", "cenarioB", "cenarioC"]
CEN_LABEL = {"cenarioA": "Cenário A\n(0% perda / 10ms)",
             "cenarioB": "Cenário B\n(5% perda / 50ms)",
             "cenarioC": "Cenário C\n(10% perda / 100ms)"}

COR = {
    ("TCP",  "Aplicação"): "#2196F3",
    ("TCP",  "Captura"):   "#0D47A1",
    ("RUDP", "Aplicação"): "#FF9800",
    ("RUDP", "Captura"):   "#E65100",
}
COR_PROT = {"TCP": "#2196F3", "RUDP": "#FF9800"}
COR_DNS  = {"TCP": "#4CAF50", "RUDP": "#9C27B0"}

DPI = 150


#Utilitários

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
        return pd.DataFrame()
    return pd.read_csv(caminho)


def carregar_dns():
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


#Gráficos

def grafico_barras_throughput(tamanho):
    df = carregar_unificado(tamanho)
    if df.empty:
        return

    grupos = [("TCP", "Aplicação"), ("TCP", "Captura"),
              ("RUDP", "Aplicação"), ("RUDP", "Captura")]
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
        ax.bar(x + offset, medias, largura,
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



def grafico_boxplot_throughput(tamanho):
    df = carregar_unificado(tamanho)
    if df.empty:
        return

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), sharey=False)

    for ax, prot in zip(axes, ["TCP", "RUDP"]):
        dados  = []
        labels = []
        for cen in CENARIOS:
            sub = df[(df["Protocolo"] == prot) & (df["Cenário"] == cen)]
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


def grafico_dns():
    df = carregar_dns()
    if df.empty:
        return

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


def grafico_tempo_empilhado(tamanho):
    df_http = carregar_unificado(tamanho)
    df_dns  = carregar_dns()
    if df_http.empty or df_dns.empty:
        return

    col_dur = "Duração(s)" if "Duração(s)" in df_dns.columns else df_dns.columns[3]
    df_dns  = df_dns.rename(columns={col_dur: "Duração(s)"})
    df_dns["Duração(s)"] = df_dns["Duração(s)"].astype(float)

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

        ax.bar(x + offset, medias_dns,  largura,
               color=COR_DNS[prot],  alpha=0.9, label=f"DNS ({prot})")
        ax.bar(x + offset, medias_http, largura,
               bottom=medias_dns,
               color=COR_PROT[prot], alpha=0.7, label=f"HTTP ({prot})")

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


def grafico_overhead_rede():
    caminho = os.path.join(DIR_TABELAS, "overhead_rede.csv")
    if not os.path.exists(caminho):
        print("  [AVISO] Tabela overhead_rede.csv não encontrada.")
        return
    
    df = pd.read_csv(caminho)
    
    for tamanho in TAMANHOS:
        sub = df[df["Tamanho"] == tamanho]
        if sub.empty: continue
        
        fig, ax = plt.subplots(figsize=(10, 5))
        
        protocolos = ["TCP", "RUDP"]
        n_cen   = len(CENARIOS)
        largura = 0.35
        x       = np.arange(n_cen)
        
        for i, prot in enumerate(protocolos):
            medias = []
            for cen in CENARIOS:
                val = sub[(sub["Protocolo"] == prot) & (sub["Cenário"] == cen)]["Overhead (%)"]
                medias.append(val.iloc[0] if not val.empty else 0)
            
            offset = (i - 0.5) * largura
            bars = ax.bar(x + offset, medias, largura,
                          color=COR_PROT[prot], alpha=0.8,
                          label=prot, edgecolor="white")
            
            for bar in bars:
                height = bar.get_height()
                ax.annotate(f'{height:.1f}%',
                            xy=(bar.get_x() + bar.get_width() / 2, height),
                            xytext=(0, 3), textcoords="offset points",
                            ha='center', va='bottom', fontsize=8, fontweight='bold')

        ax.set_xticks(x)
        ax.set_xticklabels([CEN_LABEL[c] for c in CENARIOS], fontsize=9)
        ax.set_ylabel("Overhead de Rede (%)", fontsize=10)
        ax.set_title(f"Overhead de Rede por Protocolo e Cenário — {tamanho}",
                     fontsize=12, fontweight="bold")
        ax.legend(fontsize=9)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        ax.set_ylim(bottom=0, top=max(df["Overhead (%)"]) * 1.2 if not df.empty else 10)
        fig.tight_layout()
        salvar(fig, f"overhead_rede_barras_{tamanho}.png")


# Tabelas

def tabela_estatisticas(tamanho):
    df = carregar_unificado(tamanho)
    if df.empty:
        return

    os.makedirs(DIR_TABELAS, exist_ok=True)
    est = estatisticas(df, ["Protocolo", "Cenário", "Fonte"])
    caminho = os.path.join(DIR_TABELAS, f"estatisticas_{tamanho}.csv")
    est.to_csv(caminho, index=False)
    print(f"  [OK] {caminho}")



def tabela_estatisticas_dns():
    df = carregar_dns()
    if df.empty:
        return

    col_dur = "Duração(s)" if "Duração(s)" in df.columns else df.columns[3]
    df = df.rename(columns={col_dur: "Duração(s)"})
    df["Duração(s)"] = df["Duração(s)"].astype(float) * 1000

    os.makedirs(DIR_TABELAS, exist_ok=True)
    est = (df.groupby(["Protocolo", "Cenário"])["Duração(s)"]
             .agg(Media_ms="mean", DesvPad_ms="std",
                  Minimo_ms="min", Maximo_ms="max", N="count")
             .round(3)
             .reset_index())
    caminho = os.path.join(DIR_TABELAS, "estatisticas_dns.csv")
    est.to_csv(caminho, index=False)
    print(f"  [OK] {caminho}")



def main():
    os.makedirs(DIR_GRAFICOS, exist_ok=True)
    os.makedirs(DIR_TABELAS,  exist_ok=True)

    print("\n" + "="*55)
    print(" PROCESSANDO TABELAS ESTATÍSTICAS")
    print("="*55)
    for tamanho in TAMANHOS:
        tabela_estatisticas(tamanho)
    tabela_estatisticas_dns()

    print("\n" + "="*55)
    print(" GERANDO GRÁFICOS")
    print("="*55)

    for tamanho in TAMANHOS:
        print(f"  Processando {tamanho}...")
        grafico_barras_throughput(tamanho)
        grafico_boxplot_throughput(tamanho)
        grafico_tempo_empilhado(tamanho)

    print("  Processando DNS e Overhead...")
    grafico_dns()
    grafico_overhead_rede()

    print(f"\nConcluído! Gráficos em: {DIR_GRAFICOS}")
    print(f"Tabelas em:   {DIR_TABELAS}")


if __name__ == "__main__":
    main()
