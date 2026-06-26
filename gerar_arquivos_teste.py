import os
import sys

DESTINO = os.path.join(os.path.dirname(__file__), "data/www")

ARQUIVOS = {
    "arquivo_100kb.bin": 100 * 1024,           #  100 KB
    "arquivo_500kb.bin": 500 * 1024,           #  100 KB
    "arquivo_1mb.bin":   1 * 1024 * 1024,      #    1 MB
}


def gerar(nome, tamanho_bytes):
    caminho = os.path.join(DESTINO, nome)

    if os.path.exists(caminho):
        tam_atual = os.path.getsize(caminho)
        if tam_atual == tamanho_bytes:
            print(f"  [OK] {nome} já existe com o tamanho correto. Pulando.")
            return

    print(f"  Gerando {nome} ({tamanho_bytes / 1024:.0f} KB)...", end=" ", flush=True)
    with open(caminho, "wb") as f:
        # Escreve em blocos de 64 KB para não estourar memória no caso do 10 MB
        bloco = 64 * 1024
        restante = tamanho_bytes
        while restante > 0:
            chunk = min(bloco, restante)
            f.write(os.urandom(chunk))
            restante -= chunk
    print("feito.")


def main():
    os.makedirs(DESTINO, exist_ok=True)
    print(f"Gerando arquivos de teste em: {os.path.abspath(DESTINO)}\n")

    for nome, tamanho in ARQUIVOS.items():
        gerar(nome, tamanho)

    print("\nArquivos disponíveis em data/www/:")
    for nome in ARQUIVOS:
        caminho = os.path.join(DESTINO, nome)
        tam = os.path.getsize(caminho)
        print(f"  {nome}: {tam / 1024:.1f} KB")

if __name__ == "__main__":
    main()
