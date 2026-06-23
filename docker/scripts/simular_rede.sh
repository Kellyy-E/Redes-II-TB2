#!/bin/bash

# Interface de rede padrão do container Docker
INTERFACE="eth0"

case "$1" in
    cenarioA)
        echo "[*] Aplicando Cenário A: 0% perda / 10ms delay"
        tc qdisc replace dev $INTERFACE root netem delay 10ms
        ;;
    cenarioB)
        echo "[*] Aplicando Cenário B: 5% perda / 50ms delay"
        tc qdisc replace dev $INTERFACE root netem delay 50ms loss 5%
        ;;
    cenarioC)
        echo "[*] Aplicando Cenário C: 10% perda / 100ms delay"
        tc qdisc replace dev $INTERFACE root netem delay 100ms loss 10%
        ;;
    limpar)
        echo "[*] Removendo todas as regras de rede (Voltar ao normal)..."
        tc qdisc del dev $INTERFACE root 2>/dev/null
        ;;
    *)
        echo "Uso correto: ./simular_rede.sh {cenarioA|cenarioB|cenarioC|limpar}"
        ;;
esac