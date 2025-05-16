import time
import socket
import threading
import json
import subprocess
import psutil
import os
import networkx as nx
import csv


# Função para carregar o grafo de rede
def carregar_grafo(csv_path):
    """Carrega o grafo de rede com pesos a partir de um CSV."""
    G = nx.Graph()
    with open(csv_path, newline='') as csvfile:
        leitor = csv.DictReader(csvfile)
        for linha in leitor:
            origem, destino, custo = linha['Origem'], linha['Destino'], linha['Custo']
            custo = int(custo) if custo != '-' else 1
            G.add_edge(origem, destino, weight=custo)
    return G


# Classe para gerenciar a tabela de roteamento
class TabelaRoteamento:
    """Gerencia a tabela de roteamento de um roteador."""
    
    def __init__(self, router_id: str, vizinhos: dict):
        self.router_id = router_id
        self.vizinhos = vizinhos
        self.tabela = {}
        self.roteamento = {}

    def atualizar(self, pacote):
        """Atualiza a tabela de roteamento com um novo pacote."""
        id_rota = pacote["id_rota"]
        seq = pacote["numero_sequencia"]
        entrada = self.tabela.get(id_rota)
        
        if entrada and seq <= entrada["numero_sequencia"]:
            return False
        
        # Atualiza a tabela com o novo pacote
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
        """Calcula o menor caminho utilizando Dijkstra."""
        distancias = {n: float('inf') for n in self.tabela}
        caminhos = {n: None for n in self.tabela}
        visitados = set()

        distancias[self.router_id] = 0

        while len(visitados) < len(self.tabela):
            no_atual = min((n for n in distancias if n not in visitados), key=lambda n: distancias[n], default=None)
            if no_atual is None:
                break
            visitados.add(no_atual)

            for vizinho, custo in self.tabela[no_atual]["links"].items():
                if vizinho not in visitados:
                    nova_dist = distancias[no_atual] + custo
                    if nova_dist < distancias[vizinho]:
                        distancias[vizinho] = nova_dist
                        caminhos[vizinho] = no_atual

        return caminhos

    def atualizar_rotas(self, caminhos):
        """Atualiza as rotas com base nos caminhos calculados."""
        for destino, gateway in caminhos.items():
            if destino != self.router_id:
                pulo = destino
                while pulo and caminhos[pulo] != self.router_id:
                    pulo = caminhos[pulo]
                self.roteamento[destino] = pulo

        self.roteamento = dict(sorted(self.roteamento.items()))


# Classe para enviar pacotes HELLO
class EmissorHello:
    """Emissor de pacotes HELLO."""
    
    def __init__(self, router_id, interfaces, vizinhos, intervalo=10, porta=5000):
        self.router_id = router_id
        self.interfaces = interfaces
        self.vizinhos = vizinhos
        self.intervalo = intervalo
        self.porta = porta

    def gerar_pacote_hello(self, ip_address):
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
                pacote = self.gerar_pacote_hello(ip_address)
                sock.sendto(json.dumps(pacote).encode("utf-8"), (broadcast_ip, self.porta))
                print(f"[{self.router_id}] Pacote HELLO enviado para {broadcast_ip}")
                time.sleep(self.intervalo)

    def iniciar(self):
        """Inicia o envio dos pacotes HELLO."""
        for interface in self.interfaces:
            if "broadcast" in interface:
                ip = interface["address"]
                broadcast = interface["broadcast"]
                thread = threading.Thread(target=self.enviar_broadcast, args=(ip, broadcast), daemon=True)
                thread.start()


# Classe para enviar pacotes LSA
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
        """Gera um pacote LSA."""
        self.numero_sequencia += 1
        return {
            "tipo": "LSA",
            "id_rota": self.router_id,
            "timestamp": time.time(),
            "numero_sequencia": self.numero_sequencia,
            "enderecos": [item["address"] for item in self.interfaces],
            "links": self.vizinhos_custo.copy(),
        }

    def enviar_lsa(self):
        """Envia pacotes LSA para os vizinhos."""
        while True:
            pacote = self.gerar_pacote_lsa()
            self.lsdb.atualizar(pacote)

            for vizinho_id, ip_vizinho in self.vizinhos_ip.items():
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.sendto(json.dumps(pacote).encode("utf-8"), (ip_vizinho, self.porta))
                    print(f"[LSA] Enviado para {vizinho_id} ({ip_vizinho})")
            time.sleep(self.intervalo)

    def iniciar(self):
        """Inicia o envio dos pacotes LSA."""
        threading.Thread(target=self.enviar_lsa, daemon=True).start()


# Classe principal do Roteador
class Roteador:
    """Gerencia o roteador e sua comunicação com os vizinhos."""

    def __init__(self, router_id, porta_comunicacao=5000, intervalo_envio=10):
        self.router_id = router_id
        self.porta_comunicacao = porta_comunicacao
        self.intervalo_envio = intervalo_envio
        self.interfaces = self.obter_interfaces_com_broadcast()
        self.vizinhos = {}
        self.estado_roteador = TabelaRoteamento(router_id, self.vizinhos)
        self.grafo = carregar_grafo("conex_rede.csv")
        
        self.emissor_hello = EmissorHello(router_id, self.interfaces, self.vizinhos, intervalo_envio, porta_comunicacao)
        self.emissor_lsa = EmissorLSA(router_id, self.vizinhos, self.vizinhos, self.interfaces, self.estado_roteador, intervalo_envio, porta_comunicacao)

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
        """Inicia o envio de pacotes HELLO."""
        threading.Thread(target=self.emissor_hello.iniciar, daemon=True).start()

    def receber_pacotes(self):
        """Recebe pacotes da rede e processa-os."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(("", self.porta_comunicacao))

        while True:
            try:
                data, address = sock.recvfrom(4096)
                pacote = json.loads(data.decode("utf-8"))
                self.processar_pacote(pacote)
            except Exception as e:
                print(f"Erro ao processar pacote: {e}")

    def processar_pacote(self, pacote):
        """Processa pacotes recebidos."""
        tipo_pacote = pacote.get("tipo")
        
        if tipo_pacote == "HELLO":
            self.processar_hello(pacote)
        elif tipo_pacote == "LSA":
            self.processar_lsa(pacote)

    def processar_hello(self, pacote):
        """Processa pacotes HELLO."""
        print(f"Recebido HELLO de {pacote['id_rota']}")
        # Lógica de atualização de vizinhos

    def processar_lsa(self, pacote):
        """Processa pacotes LSA."""
        print(f"Recebido LSA de {pacote['id_rota']}")
        # Lógica de atualização de tabela de roteamento

    def iniciar(self):
        """Inicia o roteador e começa a comunicação."""
        threading.Thread(target=self.receber_pacotes, daemon=True).start()
        self.iniciar_comunicacao()
        while True:
            time.sleep(1)


if __name__ == "__main__":
    router_id = os.getenv("hostname")
    if not router_id:
        raise ValueError("Não achou container")
    
    roteador = Roteador(router_id)
    roteador.iniciar()
