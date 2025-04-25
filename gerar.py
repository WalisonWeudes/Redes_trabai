import networkx as nx
import matplotlib.pyplot as plt
import random
import yaml

QUANTIDADE_ROTEADORES = 3
HOSTS_POR_ROTEADOR = 2

topologia = nx.connected_watts_strogatz_graph(QUANTIDADE_ROTEADORES, k=2, p=0.7)
for u, v in topologia.edges():
    topologia.edges[u, v]['weight'] = random.randint(1, 10)

compose = {'services': {}, 'networks': {}}
contador_subrede = 1
contador_p2p = 1

for roteador in topologia.nodes():
    nome_roteador = f"router{roteador}"
    redes_do_roteador = []

    for h in range(HOSTS_POR_ROTEADOR):
        nome_host = f"host{roteador}_{h}"
        nome_rede = f"net_r{roteador}_h{h}"
        subnet = f"192.168.{contador_subrede}.0/24"
        ip_host = f"192.168.{contador_subrede}.10"
        ip_router = f"192.168.{contador_subrede}.1"

        # Host
        compose['services'][nome_host] = {
            'build': './host',
            'networks': {
                nome_rede: {'ipv4_address': ip_host}
            }
        }

        # Rede entre host e roteador
        compose['networks'][nome_rede] = {
            'driver': 'bridge',
            'ipam': {'config': [{'subnet': subnet}]}
        }

        redes_do_roteador.append({nome_rede: {'ipv4_address': ip_router}})
        contador_subrede += 1

    # Roteador
    compose['services'][nome_roteador] = {
        'build': './router',
        'networks': {}
    }

    for rede in redes_do_roteador:
        compose['services'][nome_roteador]['networks'].update(rede)

for u, v in topologia.edges():
    nome_rede_p2p = f"net_r{u}_r{v}"
    subnet_p2p = f"10.{contador_p2p}.0.0/30"
    ip_u = f"10.{contador_p2p}.0.1"
    ip_v = f"10.{contador_p2p}.0.2"

    compose['networks'][nome_rede_p2p] = {
        'driver': 'bridge',
        'ipam': {'config': [{'subnet': subnet_p2p}]}
    }

    compose['services'][f"router{u}"]['networks'][nome_rede_p2p] = {'ipv4_address': ip_u}
    compose['services'][f"router{v}"]['networks'][nome_rede_p2p] = {'ipv4_address': ip_v}

    contador_p2p += 1

with open('docker-compose.yml', 'w') as arquivo:
    yaml.dump(compose, arquivo, sort_keys=False)

print("✅ docker-compose.yml gerado com sucesso!")

grafo_visual = nx.Graph()

# Adiciona nós e arestas
for r in topologia.nodes():
    nome_roteador = f"router{r}"
    grafo_visual.add_node(nome_roteador, tipo='router')

    for h in range(HOSTS_POR_ROTEADOR):
        nome_host = f"host{r}_{h}"
        grafo_visual.add_node(nome_host, tipo='host')
        grafo_visual.add_edge(nome_roteador, nome_host)

for u, v in topologia.edges():
    grafo_visual.add_edge(f"router{u}", f"router{v}")

# Cores diferentes para roteadores e hosts
cores = ['lightgreen' if dados['tipo'] == 'router' else 'lightblue'
         for _, dados in grafo_visual.nodes(data=True)]

# Desenho
plt.figure(figsize=(10, 8))
posicoes = nx.spring_layout(grafo_visual, seed=42)
nx.draw(
    grafo_visual,
    posicoes,
    with_labels=True,
    node_color=cores,
    node_size=1500,
    font_size=10,
    edge_color='gray'
)
plt.title("Topologia de Rede Visual")
plt.show()
