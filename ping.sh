#!/bin/bash

# Script para testar conectividade total da rede
# Este script verifica se cada roteador consegue pingar todos os outros roteadores e hosts

# Cores para saída
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Função para obter o endereço IP correto de um container em suas redes
get_ip_addresses() {
    local container=$1
    local ips=()
    
    # Obter todas as redes do container
    local networks=$(docker inspect -f '{{range $key, $value := .NetworkSettings.Networks}}{{$key}} {{end}}' $container)
    
    # Para cada rede, obter o IP correspondente
    for network in $networks; do
        local ip=$(docker inspect -f "{{with index .NetworkSettings.Networks \"$network\"}}{{.IPAddress}}{{end}}" $container)
        if [ ! -z "$ip" ]; then
            ips+=("$ip")
        fi
    done
    
    # Retornar os IPs encontrados
    echo "${ips[@]}"
}

# Função para testar ping entre dois containers
test_ping() {
    local source=$1
    local target=$2
    local target_ip=$3
    
    echo -n "  Ping de $source para $target ($target_ip): "
    
    # Executar ping a partir do container de origem
    PING_RESULT=$(docker exec $source ping -c 2 -w 2 $target_ip 2>&1)
    PING_STATUS=$?
    
    # Verificar o resultado do ping
    if [ $PING_STATUS -eq 0 ]; then
        echo -e "${GREEN}✓ Sucesso${NC}"
        return 0
    else
        echo -e "${RED}✗ Falha${NC}"
        return 1
    fi
}

# Função para testar conectividade de todos os roteadores com todos os outros roteadores
test_connectivity_routers() {
    local router=$1
    local routers=$2
    local ip_function=$3
    
    echo -e "\n${YELLOW}TESTE DE CONECTIVIDADE COM OUTROS ROTEADORES:${NC}"
    local router_total=0
    local router_success=0
    local router_failure=0
    
    for target_router in $routers; do
        if [ "$router" != "$target_router" ]; then
            # Obter IPs do roteador alvo
            local target_ips=($(get_ip_addresses $target_router))
            
            # Tentar pingar cada IP do roteador alvo
            local ping_success=0
            for target_ip in "${target_ips[@]}"; do
                router_total=$((router_total + 1))
                TOTAL_TESTS=$((TOTAL_TESTS + 1))
                
                if test_ping "$router" "$target_router" "$target_ip"; then
                    router_success=$((router_success + 1))
                    TOTAL_SUCCESS=$((TOTAL_SUCCESS + 1))
                    ping_success=1
                    break
                else
                    router_failure=$((router_failure + 1))
                    TOTAL_FAILURE=$((TOTAL_FAILURE + 1))
                fi
            done
        fi
    done
    
    # Exibir resumo para este roteador
    echo -e "\n${YELLOW}RESUMO PARA $router:${NC}"
    echo "Total de componentes testados: $router_total"
    echo -e "Componentes alcançáveis: ${GREEN}$router_success${NC}"
    echo -e "Componentes não alcançáveis: ${RED}$router_failure${NC}"
    
    # Calcular taxa de sucesso para este roteador
    if [ $router_total -gt 0 ]; then
        local success_rate=$(( (router_success * 100) / router_total ))
        echo -e "Taxa de sucesso: $success_rate%"
    fi
}

# Função para testar conectividade de todos os roteadores com todos os hosts
test_connectivity_hosts() {
    local router=$1
    local hosts=$2
    local ip_function=$3
    
    echo -e "\n${BLUE}TESTE DE CONECTIVIDADE COM HOSTS:${NC}"
    for host in $hosts; do
        # Obter IPs do host alvo
        local target_ips=($(get_ip_addresses $host))
        
        # Tentar pingar cada IP do host alvo
        local ping_success=0
        for target_ip in "${target_ips[@]}"; do
            ROUTER_TOTAL=$((ROUTER_TOTAL + 1))
            TOTAL_TESTS=$((TOTAL_TESTS + 1))
            
            if test_ping "$router" "$host" "$target_ip"; then
                ROUTER_SUCCESS=$((ROUTER_SUCCESS + 1))
                TOTAL_SUCCESS=$((TOTAL_SUCCESS + 1))
                ping_success=1
                break  # Se conseguir pingar pelo menos um IP, considera sucesso
            else
                ROUTER_FAILURE=$((ROUTER_FAILURE + 1))
                TOTAL_FAILURE=$((TOTAL_FAILURE + 1))
            fi
        done
    done
}

# Obter lista de todos os roteadores
ROUTERS=$(docker ps --format '{{.Names}}' | grep "^router[0-9]\+$")

# Obter lista de todos os hosts
HOSTS=$(docker ps --format '{{.Names}}' | grep "_host[0-9]\+$")

# Exibir título do teste
echo -e "${CYAN}===========================================================${NC}"
echo -e "${CYAN}TESTE DE CONECTIVIDADE TOTAL DA REDE${NC}"
echo -e "${CYAN}===========================================================${NC}"

# Inicializar estatísticas globais
TOTAL_TESTS=0
TOTAL_SUCCESS=0
TOTAL_FAILURE=0

# Para cada roteador como origem
for ROUTER in $ROUTERS; do
    echo -e "\n${MAGENTA}===========================================================${NC}"
    echo -e "${MAGENTA}TESTANDO CONECTIVIDADE A PARTIR DE: ${ROUTER}${NC}"
    echo -e "${MAGENTA}===========================================================${NC}"
    
    # Teste de conectividade com outros roteadores
    test_connectivity_routers "$ROUTER" "$ROUTERS" get_ip_addresses

    # Teste de conectividade com hosts
    test_connectivity_hosts "$ROUTER" "$HOSTS" get_ip_addresses
done

# Exibir resumo global
echo -e "\n${CYAN}===========================================================${NC}"
echo -e "${CYAN}RESUMO GLOBAL DOS TESTES${NC}"
echo -e "${CYAN}===========================================================${NC}"
echo "Total de testes realizados: $TOTAL_TESTS"
echo -e "Testes bem-sucedidos: ${GREEN}$TOTAL_SUCCESS${NC}"
echo -e "Testes com falha: ${RED}$TOTAL_FAILURE${NC}"

# Calcular taxa de sucesso global
if [ $TOTAL_TESTS -gt 0 ]; then
    GLOBAL_SUCCESS_RATE=$(( (TOTAL_SUCCESS * 100) / TOTAL_TESTS ))
    echo -e "Taxa de sucesso global: $GLOBAL_SUCCESS_RATE%"
fi

# Gerar relatório de conectividade
echo -e "\n${CYAN}===========================================================${NC}"
echo -e "${CYAN}GERANDO RELATÓRIO DE CONECTIVIDADE${NC}"
echo -e "${CYAN}===========================================================${NC}"

# Contar número de roteadores e hosts
NUM_ROUTERS=$(echo "$ROUTERS" | wc -w)
NUM_HOSTS=$(echo "$HOSTS" | wc -w)
echo -e "Número total de roteadores: $NUM_ROUTERS"
echo -e "Número total de hosts: $NUM_HOSTS"

# Verificar conectividade total
if [ $GLOBAL_SUCCESS_RATE -eq 100 ]; then
    echo -e "\n${GREEN}✓ REDE TOTALMENTE CONECTADA${NC}"
    echo "Todos os roteadores conseguem alcançar todos os componentes da rede."
elif [ $GLOBAL_SUCCESS_RATE -ge 80 ]; then
    echo -e "\n${YELLOW}⚠ REDE PARCIALMENTE CONECTADA${NC}"
    echo "A maioria dos roteadores consegue alcançar a maioria dos componentes da rede."
    echo "Verifique os logs acima para identificar problemas específicos."
else
    echo -e "\n${RED}✗ PROBLEMAS SIGNIFICATIVOS DE CONECTIVIDADE${NC}"
    echo "Há problemas graves de conectividade na rede."
    echo "Revise as configurações de roteamento e as tabelas de rotas."
fi

exit 0
