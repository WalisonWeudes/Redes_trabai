import time
import socket
import threading
import json
import subprocess
import psutil
import os
import networkx as nx
import csv


def carregar_grafo(csv_path):
    """
    Carrega o grafo de rede com pesos a partir de um arquivo CSV.
    O arquivo CSV deve conter as colunas 'Origem', 'Destino' e 'Custo'.
    
    Args:
        csv_path (str): Caminho para o arquivo CSV contendo as informações do grafo.

    Returns:
        networkx.Graph: O grafo carregado com os nós e arestas definidos no CSV.
    """
    G = nx.Graph()
    with open(csv_path, newline='') as csvfile:
        leitor = csv.DictReader(csvfile)
        for linha in leitor:
            origem, destino, custo = linha['Origem'], linha['Destino'], linha['Custo']
            custo = int(custo) if custo != '-' else 1
            G.add_edge(origem, destino, weight=custo)
    return G


class TabelaRoteamento:
    """Gerencia a tabela de roteamento de um roteador."""

    def __init__(self, router_id: str, vizinhos: dict):
        self.router_id = router_id
        self.vizinhos = vizinhos
        self.tabela = {}
        self.roteamento = {}

    def atualizar(self, pacote):
        """
        Atualiza a tabela de roteamento com base em um novo pacote recebido.
        
        Args:
            pacote (dict): Um dicionário contendo informações sobre o pacote.
        
        Returns:
            bool: Retorna True se a tabela foi atualizada com sucesso, ou False se não.
        """
        id_rota = pacote["id_rota"]
        seq = pacote["numero_sequencia"]
        entrada = self.tabela.get(id_rota)
        
        if entrada and seq <= entrada["numero_sequencia"]:
            return False
        
        self.tabela[id_rota] = self.criar_entrada(seq, pacote["enderecos"], pacote["links"])
        
        for vizinho in pacote["links"]:
            if vizinho not in self.tabela:
                self.tabela[vizinho] = self.criar_entrada(-1, [], {})

        self.rotear()
        return True

    def criar_entrada(self, seq, enderecos, links):
        """Cria uma entrada de roteamento."""
        return {"numero_sequencia": seq, "enderecos": enderecos, "links": links}

    def rotear(self):
        """Aplica o algoritmo de Dijkstra para calcular as rotas."""
        caminhos = self.dijkstra()
        self.atualizar_rotas(caminhos)



    def dijkstra(self):
        """
        Calcula o menor caminho a partir do roteador atual para todos os outros roteadores.
        
        Returns:
            dict: Dicionário com os caminhos de menor custo.
        """
        distancias = {n: float('inf') for n in self.tabela}
        caminhos = {n: None for n in self.tabela}
        visitados = set()

        distancias[self.router_id] = 0

        while len(visitados) < len(self.tabela):
            # Escolher o nó com a menor distância não visitado
            no_atual = min((n for n in distancias if n not in visitados), key=lambda n: distancias[n], default=None)
            if no_atual is None:
                break
            visitados.add(no_atual)

            # Iterar pelos vizinhos e calcular a distância
            for vizinho, link_info in self.tabela[no_atual]["links"].items():
                if vizinho not in visitados:
                    # Aqui, agora extraímos o custo corretamente (link_info deve ser um dicionário)
                    custo = link_info.get('timestamp', 1)  # Substitua 'timestamp' se necessário para o custo real
                    nova_dist = distancias[no_atual] + custo
                    if nova_dist < distancias[vizinho]:
                        distancias[vizinho] = nova_dist
                        caminhos[vizinho] = no_atual

        return caminhos


    def atualizar_rotas(self, caminhos):
        """
        Atualiza as rotas do roteador com base nos caminhos calculados.
        
        Args:
            caminhos (dict): Dicionário com os destinos e gateways intermediários.
        """
        for destino, gateway in caminhos.items():
            if destino != self.router_id:
                pulo = destino
                while pulo and caminhos[pulo] != self.router_id:
                    pulo = caminhos[pulo]
                self.roteamento[destino] = pulo

        self.roteamento = dict(sorted(self.roteamento.items()))

    


class EmissorHello:
    """Emissor de pacotes HELLO."""
    
    def __init__(self, router_id, interfaces, vizinhos=None, intervalo=10, porta=5000):
        self.router_id = router_id
        self.interfaces = interfaces
        self.vizinhos = vizinhos if vizinhos is not None else {}
        self.intervalo = intervalo
        self.porta = porta

    def gerar_hello(self, ip_address):
        """Gera um pacote HELLO para enviar aos vizinhos."""
        return {
            "tipo": "HELLO",
            "id_rota": self.router_id,
            "timestamp": time.time(),
            "ip_address": ip_address,
            "vizinhos_conhecidos": list(self.vizinhos.keys()),
        }

    def enviar_broadcast(self, ip_address, broadcast_ip):
        """Envia pacotes HELLO via broadcast."""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            while True:
                pacote = self.gerar_hello(ip_address)
                try:
                    sock.sendto(json.dumps(pacote).encode("utf-8"), (broadcast_ip, self.porta))
                    print(f"[{self.router_id}] Pacote HELLO enviado para {broadcast_ip}")
                    time.sleep(self.intervalo)
                except Exception as e:
                    print(f"Erro ao enviar pacote: {e}")

    def iniciar(self):
        """Inicia o envio dos pacotes HELLO em interfaces configuradas para broadcast."""
        for interface in self.interfaces:
            if "broadcast" in interface:
                ip = interface["address"]
                broadcast = interface["broadcast"]
                thread = threading.Thread(target=self.enviar_broadcast, args=(ip, broadcast))
                thread.daemon = True
                thread.start()


class EmissorLSA:
    """Emissor de pacotes LSA."""
    
    def __init__(self, router_id, vizinhos_ip, vizinhos_custo, interfaces, lsdb, intervalo=30, porta=5000):
        self.router_id = router_id
        self.vizinhos_ip = vizinhos_ip
        self.vizinhos_custo = vizinhos_custo
        self.intervalo = intervalo
        self.porta = porta
        self.numero_sequencia = 0
        self.lsdb = lsdb
        self.interfaces = interfaces

    def gerar_pacote_lsa(self):
        """Gera um pacote LSA (Link-State Advertisement)."""
        self.numero_sequencia += 1
        pacote_lsa = {
            "tipo": "LSA",
            "id_rota": self.router_id,
            "timestamp": time.time(),
            "numero_sequencia": self.numero_sequencia,
            "enderecos": [item["address"] for item in self.interfaces],
            "links": self.vizinhos_custo.copy(),
        }
        print(f"Pacote LSA gerado: {pacote_lsa}")
        return pacote_lsa

    def enviar_lsa(self):
        """Envia pacotes LSA para os vizinhos."""
        while True:
            pacote = self.gerar_pacote_lsa()
            self.lsdb.atualizar(pacote)  # Atualiza a base de dados LSDB

            for vizinho_id, ip_vizinho in self.vizinhos_ip.items():
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.sendto(json.dumps(pacote).encode("utf-8"), (ip_vizinho, self.porta))
                    print(f"[LSA] Enviado para {vizinho_id} ({ip_vizinho})")
            time.sleep(self.intervalo)

    def iniciar(self):
        """Inicia o envio dos pacotes LSA em uma thread separada."""
        threading.Thread(target=self.enviar_lsa, daemon=True).start()


class Roteador:
    """Gerencia o roteador e sua comunicação com os vizinhos."""
    
    def __init__(self, router_id, porta_comunicacao=5000, intervalo_envio=10):
        self.router_id = router_id
        self.porta_comunicacao = porta_comunicacao
        self.intervalo_envio = intervalo_envio
        self.interfaces = self.obter_interfaces_com_broadcast()
        self.vizinhos = {}
        self.vizinhos_ip = {}
        self.estado_roteador = TabelaRoteamento(router_id, self.vizinhos)
        self.grafo = carregar_grafo("conex_rede.csv")
        
        self.emissor_hello = EmissorHello(router_id, self.interfaces, self.vizinhos, intervalo_envio, porta_comunicacao)
        self.emissor_lsa = EmissorLSA(router_id, self.vizinhos_ip, self.vizinhos, self.interfaces, self.estado_roteador, intervalo_envio, porta_comunicacao)

    def obter_interfaces_com_broadcast(self):
        """Obtém interfaces de rede com broadcast."""
        interfaces = []
        for nome, snics in psutil.net_if_addrs().items():
            for snic in snics:
                if snic.family == socket.AF_INET:
                    ip = snic.address
                    broadcast = snic.broadcast
                    if ip and broadcast:
                        interfaces.append({
                            "interface": nome,
                            "address": ip,
                            "broadcast": broadcast
                        })
        return interfaces

    def iniciar_comunicacao(self):
        """Inicia a comunicação enviando pacotes HELLO e LSA em threads separadas."""
        threading.Thread(target=self.emissor_hello.iniciar, daemon=True).start()
        threading.Thread(target=self.emissor_lsa.iniciar, daemon=True).start()

    def receber_pacotes(self):
        """Recebe pacotes da rede via socket UDP e processa-os."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("", self.porta_comunicacao))

        while True:
            try:
                data, address = sock.recvfrom(4096)
                pacote = json.loads(data.decode("utf-8"))
                print(f"Pacote recebido de {address}: {pacote}")
                self.processar_pacote(pacote)
            except Exception as e:
                print(f"Erro ao processar pacote: {e}")

    def processar_pacote(self, pacote):
        """Processa pacotes recebidos pelo roteador."""
        tipo_pacote = pacote.get("tipo")
        
        if tipo_pacote == "HELLO":
            self.processar_hello(pacote)
        elif tipo_pacote == "LSA":
            self.processar_lsa(pacote)
            
    def processar_hello(self, pacote):
        """Processa pacotes HELLO."""
        print(f"Recebido HELLO de {pacote['id_rota']}")
        vizinho_id = pacote["id_rota"]
        if vizinho_id not in self.vizinhos:
            self.vizinhos[vizinho_id] = {"timestamp": pacote["timestamp"]}
            self.vizinhos_ip[vizinho_id] = pacote["ip_address"]
            print(f"Novo vizinho detectado: {vizinho_id} ({pacote['ip_address']})")
        else:
            self.vizinhos[vizinho_id]["timestamp"] = pacote["timestamp"]

    def processar_lsa(self, pacote):
        """Processa pacotes LSA."""
        print(f"Recebido LSA de {pacote['id_rota']}")
        atualizado = self.estado_roteador.atualizar(pacote)
        if atualizado:
            print(f"Tabela de roteamento atualizada com LSA de {pacote['id_rota']}")
        else:
            print(f"LSA de {pacote['id_rota']} já está atualizado. Nenhuma mudança feita.")

    def iniciar(self):
        """Inicia o roteador e começa a comunicação."""
        threading.Thread(target=self.receber_pacotes, daemon=True).start()
        self.iniciar_comunicacao()
        while True:
            time.sleep(1)


if __name__ == "__main__":
    router_id = os.getenv("hostname", "default_router_id")
    if not router_id:
        raise ValueError("Não achou container")
    
    roteador = Roteador(router_id)
    roteador.iniciar()
