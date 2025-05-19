#!/bin/bash

# Gerencia a tabela de roteamento de um roteador.
# Este script verifica se cada roteador consegue pingar todos os outros roteadores e hosts.

# Cores para saída
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # Sem cor

# Obtém os endereços IP de um container em suas redes.
get_ip_addresses() {
    local container=$1
    local ips=()
    local networks=$(docker inspect -f '{{range $key, $value := .NetworkSettings.Networks}}{{$key}} {{end}}' "$container")
    
    for network in $networks; do
        local ip=$(docker inspect -f "{{with index .NetworkSettings.Networks \"$network\"}}{{.IPAddress}}{{end}}" "$container")
        if [ -n "$ip" ]; then
            ips+=("$ip")
        fi
    done
    
    echo "${ips[@]}"
}

# Testa o ping entre dois containers.
test_ping() {
    local source=$1
    local target=$2
    local target_ip=$3
    
    echo -n "Testando ping de $source para $target ($target_ip)... "
    if docker exec "$source" ping -c 2 -w 2 "$target_ip" &>/dev/null; then
        echo -e "${GREEN}✓ Conectado${NC}"
        return 0
    else
        echo -e "${RED}✗ Falha${NC}"
        return 1
    fi
}

# Testa a conectividade de um roteador com outros roteadores.
test_connectivity_routers() {
    local router=$1
    local routers=$2
    
    echo -e "\n${YELLOW}Verificando conectividade com outros roteadores...${NC}"
    local router_total=0
    local router_success=0
    local router_failure=0
    
    for target_router in $routers; do
        if [ "$router" != "$target_router" ]; then
            local target_ips=($(get_ip_addresses "$target_router"))
            
            for target_ip in "${target_ips[@]}"; do
                router_total=$((router_total + 1))
                TOTAL_TESTS=$((TOTAL_TESTS + 1))
                
                if test_ping "$router" "$target_router" "$target_ip"; then
                    router_success=$((router_success + 1))
                    TOTAL_SUCCESS=$((TOTAL_SUCCESS + 1))
                    break
                else
                    router_failure=$((router_failure + 1))
                    TOTAL_FAILURE=$((TOTAL_FAILURE + 1))
                fi
            done
        fi
    done
    
    echo -e "\nResumo de conectividade para $router:"
    echo "  Total de roteadores testados: $router_total"
    echo -e "  Conectados: ${GREEN}$router_success${NC}"
    echo -e "  Não conectados: ${RED}$router_failure${NC}"
    
    if [ $router_total -gt 0 ]; then
        local success_rate=$(( (router_success * 100) / router_total ))
        echo "  Taxa de sucesso: $success_rate%"
    fi
}

# Testa a conectividade de um roteador com hosts.
test_connectivity_hosts() {
    local router=$1
    local hosts=$2
    
    echo -e "\n${BLUE}Verificando conectividade com hosts...${NC}"
    local router_total=0
    local router_success=0
    local router_failure=0
    
    for host in $hosts; do
        local target_ips=($(get_ip_addresses "$host"))
        
        for target_ip in "${target_ips[@]}"; do
            router_total=$((router_total + 1))
            TOTAL_TESTS=$((TOTAL_TESTS + 1))
            
            if test_ping "$router" "$host" "$target_ip"; then
                router_success=$((router_success + 1))
                TOTAL_SUCCESS=$((TOTAL_SUCCESS + 1))
                break
            else
                router_failure=$((router_failure + 1))
                TOTAL_FAILURE=$((TOTAL_FAILURE + 1))
            fi
        done
    done
    
    echo -e "\nResumo de conectividade para $router:"
    echo "  Total de hosts testados: $router_total"
    echo -e "  Conectados: ${GREEN}$router_success${NC}"
    echo -e "  Não conectados: ${RED}$router_failure${NC}"
}

# Obtém a lista de roteadores e hosts.
ROUTERS=$(docker ps --format '{{.Names}}' | grep "^router[0-9]\+$")
HOSTS=$(docker ps --format '{{.Names}}' | grep "_host[0-9]\+$")

# Exibe o título do teste.
echo -e "${CYAN}===========================================================${NC}"
echo -e "${CYAN}TESTE DE CONECTIVIDADE DA REDE${NC}"
echo -e "${CYAN}===========================================================${NC}"

# Inicializa estatísticas globais
TOTAL_TESTS=0
TOTAL_SUCCESS=0
TOTAL_FAILURE=0

# Testa a conectividade para cada roteador.
for ROUTER in $ROUTERS; do
    echo -e "\n${MAGENTA}Testando conectividade a partir de: $ROUTER${NC}"
    echo -e "${MAGENTA}===========================================================${NC}"
    
    test_connectivity_routers "$ROUTER" "$ROUTERS"
    test_connectivity_hosts "$ROUTER" "$HOSTS"
done

# Exibe o resumo global.
echo -e "\n${CYAN}===========================================================${NC}"
echo -e "${CYAN}RESUMO FINAL DOS TESTES${NC}"
echo -e "${CYAN}===========================================================${NC}"
echo "Total de testes realizados: $TOTAL_TESTS"
echo -e "Testes bem-sucedidos: ${GREEN}$TOTAL_SUCCESS${NC}"
echo -e "Testes com falha: ${RED}$TOTAL_FAILURE${NC}"

if [ $TOTAL_TESTS -gt 0 ]; then
    GLOBAL_SUCCESS_RATE=$(( (TOTAL_SUCCESS * 100) / TOTAL_TESTS ))
    echo "Taxa de sucesso global: $GLOBAL_SUCCESS_RATE%"
fi

# Gera o relatório de conectividade.
echo -e "\n${CYAN}===========================================================${NC}"
echo -e "${CYAN}GERANDO RELATÓRIO DE CONECTIVIDADE${NC}"
echo -e "${CYAN}===========================================================${NC}"
NUM_ROUTERS=$(echo "$ROUTERS" | wc -w)
NUM_HOSTS=$(echo "$HOSTS" | wc -w)
echo "Número total de roteadores: $NUM_ROUTERS"
echo "Número total de hosts: $NUM_HOSTS"

if [ "${GLOBAL_SUCCESS_RATE:-0}" -eq 100 ]; then
    echo -e "\n${GREEN}✓ REDE TOTALMENTE CONECTADA${NC}"
elif [ "${GLOBAL_SUCCESS_RATE:-0}" -ge 80 ]; then
    echo -e "\n${YELLOW}⚠ REDE PARCIALMENTE CONECTADA${NC}"
else
    echo -e "\n${RED}✗ PROBLEMAS SIGNIFICATIVOS DE CONECTIVIDADE${NC}"
fi

exit 0
