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
    """
    Carrega o grafo de rede com pesos a partir de um arquivo CSV.

    O arquivo CSV deve conter as colunas 'Origem', 'Destino' e 'Custo', onde:
    - 'Origem' e 'Destino' representam os nós conectados por uma aresta.
    - 'Custo' representa o peso da aresta (se for '-', assume-se o peso como 1).

    A função cria um grafo não direcionado utilizando a biblioteca NetworkX,
    adicionando as arestas e seus respectivos pesos.

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


# Classe para gerenciar a tabela de roteamento
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
        Esta função verifica se o pacote recebido contém informações mais recentes
        do que as já armazenadas na tabela de roteamento. Caso positivo, a tabela
        é atualizada com os dados do pacote. Além disso, novos vizinhos encontrados
        no pacote são adicionados à tabela com entradas padrão. Após a atualização,
        a função de roteamento é chamada para recalcular as rotas.
        Args:
            pacote (dict): Um dicionário contendo as informações do pacote, incluindo:
                - "id_rota" (str): Identificador da rota.
                - "numero_sequencia" (int): Número de sequência do pacote.
                - "enderecos" (list): Lista de endereços associados à rota.
                - "links" (list): Lista de vizinhos conectados à rota.
        Returns:
            bool: Retorna True se a tabela foi atualizada com sucesso, ou False
            se o pacote não contém informações mais recentes.
        """
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
        """
        Cria uma entrada de roteamento.

        Args:
            seq (int): Número de sequência associado à entrada de roteamento.
            enderecos (list): Lista de endereços envolvidos na entrada de roteamento.
            links (list): Lista de links associados à entrada de roteamento.

        Returns:
            dict: Um dicionário contendo o número de sequência, os endereços e os links.
        """
        """Cria uma entrada de roteamento."""
        return {"numero_sequencia": seq, "enderecos": enderecos, "links": links}

    def rotear(self):
        """
        Aplica o algoritmo de Dijkstra para calcular as rotas e atualiza as rotas do roteador.

        Esta função utiliza o algoritmo de Dijkstra para determinar os caminhos mais curtos
        na rede e, em seguida, atualiza as rotas do roteador com base nesses caminhos.
        """
        """Aplica o algoritmo de Dijkstra para calcular as rotas."""
        caminhos = self.dijkstra()
        self.atualizar_rotas(caminhos)

    def dijkstra(self):
        """
        Calcula o menor caminho a partir do roteador atual para todos os outros
        roteadores na tabela utilizando o algoritmo de Dijkstra.
        O algoritmo encontra o caminho de menor custo em um grafo ponderado,
        atualizando as distâncias mínimas e os caminhos para cada nó.
        Returns:
            dict: Um dicionário onde as chaves são os roteadores de destino e os
            valores são os roteadores predecessores no caminho de menor custo.
        """
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
        """
        Atualiza as rotas de roteamento do roteador com base nos caminhos calculados.
        Esta função recebe um dicionário de caminhos, onde as chaves representam destinos
        e os valores representam os gateways intermediários para alcançar esses destinos.
        Para cada destino, a função determina o próximo salto (pulo) necessário para
        alcançar o destino a partir do roteador atual, garantindo que o roteamento seja
        atualizado corretamente.
        Após processar todos os destinos, as rotas são ordenadas em ordem crescente
        com base nas chaves (destinos).
        Args:
            caminhos (dict): Um dicionário onde as chaves são os destinos e os valores
                             são os gateways intermediários para alcançar esses destinos.
        """
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

    def gerar_hello(self, ip_address):
        """
        Gera um pacote HELLO para enviar aos vizinhos.

        Esta função cria e retorna um dicionário representando um pacote do tipo HELLO.
        O pacote contém informações sobre o roteador, incluindo seu identificador, 
        timestamp atual, endereço IP e a lista de vizinhos conhecidos.

        Parâmetros:
            ip_address (str): O endereço IP do roteador que receberá o pacote HELLO.

        Retorna:
            dict: Um dicionário contendo os dados do pacote HELLO.
        """
        """Gera um pacote HELLO para enviar aos vizinhos."""
        return {
            "tipo": "HELLO",
            "id_rota": self.router_id,
            "timestamp": time.time(),
            "ip_address": ip_address,
            "vizinhos_conhecidos": list(self.vizinhos.keys()),
        }

    def enviar_broadcast(self, ip_address, broadcast_ip):
        """
        Envia pacotes HELLO via broadcast.

        Args:
            ip_address (str): O endereço IP do roteador que está enviando o pacote.
            broadcast_ip (str): O endereço IP de broadcast para onde os pacotes serão enviados.

        Comportamento:
            - Cria um socket x' configurado para permitir envio de pacotes em broadcast.
            - Gera pacotes HELLO usando o método `gerar_pacote_hello`.
            - Envia os pacotes para o endereço de broadcast especificado em intervalos regulares.
            - Exibe no console uma mensagem indicando o envio de cada pacote.
        """
        """Envia pacotes HELLO via broadcast."""
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            while True:
                pacote = self.gerar_hello(ip_address)
                sock.sendto(json.dumps(pacote).encode("utf-8"), (broadcast_ip, self.porta))
                print(f"[{self.router_id}] Pacote HELLO enviado para {broadcast_ip}")
                time.sleep(self.intervalo)

    def iniciar(self):
        """
        Inicia o envio dos pacotes HELLO em interfaces configuradas para broadcast.

        Para cada interface que possui a configuração de broadcast, esta função cria
        e inicia uma nova thread para enviar pacotes HELLO de forma contínua. O envio
        é realizado utilizando o método `enviar_broadcast`, que recebe o endereço IP
        e o endereço de broadcast da interface como argumentos.

        A execução das threads é configurada como daemon, garantindo que elas sejam
        encerradas automaticamente quando o programa principal for finalizado.
        """
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
        """
        Gera um pacote LSA (Link-State Advertisement).

        Este método cria e retorna um dicionário representando um pacote LSA, que contém 
        informações sobre o roteador, como seu ID, timestamp, número de sequência, 
        endereços das interfaces e os custos dos links para os vizinhos.

        Returns:
            dict: Um dicionário contendo os seguintes campos:
                - "tipo" (str): O tipo do pacote, neste caso "LSA".
                - "id_rota" (str): O identificador do roteador.
                - "timestamp" (float): O timestamp atual no formato de tempo Unix.
                - "numero_sequencia" (int): O número de sequência do pacote LSA.
                - "enderecos" (list): Uma lista de endereços das interfaces do roteador.
                - "links" (dict): Um dicionário contendo os custos dos links para os vizinhos.
        """
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
        """
        Envia pacotes LSA (Link-State Advertisement) para os roteadores vizinhos.
        Esta função é responsável por gerar pacotes LSA, atualizar a base de dados
        de estado de enlace (LSDB) com o pacote gerado e enviá-lo para todos os
        vizinhos conhecidos. O envio é realizado utilizando sockets UDP.
        O processo é repetido continuamente em intervalos definidos.
        Métodos utilizados:
        - gerar_pacote_lsa: Gera o pacote LSA a ser enviado.
        - lsdb.atualizar: Atualiza a base de dados LSDB com o pacote gerado.
        Atributos utilizados:
        - vizinhos_ip (dict): Um dicionário contendo os IDs dos vizinhos como chave
          e seus respectivos endereços IP como valor.
        - porta (int): A porta utilizada para enviar os pacotes LSA.
        - intervalo (int): O intervalo de tempo (em segundos) entre os envios de pacotes.
        Exemplo de saída:
        [LSA] Enviado para <vizinho_id> (<ip_vizinho>)
        """
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
        """
        Inicia o envio dos pacotes LSA em uma thread separada.

        Esta função cria e inicia uma nova thread em modo daemon para executar o método
        `enviar_lsa`, que é responsável por enviar pacotes LSA (Link-State Advertisement).
        O uso de uma thread separada permite que o envio dos pacotes ocorra de forma
        assíncrona, sem bloquear a execução principal do programa.
        """
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
        """
        Obtém interfaces de rede com suporte a broadcast.

        Esta função utiliza a biblioteca `psutil` para iterar sobre as interfaces de rede disponíveis
        e retorna uma lista contendo informações sobre as interfaces que possuem suporte a broadcast.
        Para cada interface encontrada, são coletados o nome da interface, o endereço IP e o endereço
        de broadcast.

        Returns:
            list: Uma lista de dicionários, onde cada dicionário contém as seguintes chaves:
                - "interface" (str): Nome da interface de rede.
                - "address" (str): Endereço IP associado à interface.
                - "broadcast" (str): Endereço de broadcast associado à interface.
        """
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
        """
        Inicia a comunicação enviando pacotes HELLO em uma thread separada.

        Esta função cria e inicia uma nova thread em modo daemon para executar o método
        `iniciar` do objeto `emissor_hello`. O envio de pacotes HELLO é utilizado para
        estabelecer ou manter a comunicação com outros dispositivos na rede.
        """
        """Inicia o envio de pacotes HELLO."""
        threading.Thread(target=self.emissor_hello.iniciar, daemon=True).start()

    def receber_pacotes(self):
        """
        Recebe pacotes da rede via socket UDP e processa-os.
        Esta função cria um socket UDP, vincula-o à porta de comunicação especificada
        e entra em um loop infinito para receber pacotes da rede. Cada pacote recebido
        é decodificado de JSON e processado pela função `processar_pacote`.
        Exceções durante o processamento de pacotes são capturadas e exibidas no console.
        Raises:
            Exception: Caso ocorra algum erro ao processar o pacote.
        """
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
        """
        Processa pacotes recebidos pelo roteador.
        Esta função identifica o tipo do pacote recebido e delega o processamento
        para a função apropriada com base no tipo do pacote.
        Args:
            pacote (dict): Um dicionário contendo os dados do pacote. Deve incluir
                           a chave "tipo" que indica o tipo do pacote.
        Tipos de Pacotes:
            - "HELLO": Pacote de saudação, processado pela função `processar_hello`.
            - "LSA": Pacote de anúncio de estado de link, processado pela função `processar_lsa`.
        """
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
