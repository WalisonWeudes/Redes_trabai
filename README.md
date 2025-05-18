
### Docker e Docker Compose
- **Docker**: Certifique-se de ter o Docker instalado na sua máquina. O projeto utiliza containers Docker para simular os roteadores e hosts.
- **Docker Compose**: Usado para orquestrar os containers Docker e suas redes.

## Estrutura do Projeto
- **`gerar.py`**: Script principal para gerar o grafo de rede, configurar as redes e sub-redes, gerar o arquivo `docker-compose.yml` e salvar a visualização da topologia.
- **`requirements.txt`**: Contém as bibliotecas necessárias para o funcionamento do projeto.
- **`router.py`**: Contém a lógica do roteador, incluindo a criação da tabela de roteamento e o envio de pacotes HELLO e LSA.
- **`host.sh`**: Script que configura o gateway e mantém o container do host ativo.
- **Dockerfile (para roteador e host)**: Contém as instruções para construir os containers de roteadores e hosts.

## Como Usar

### 1. Configuração Inicial
Clone o repositório ou faça o download dos arquivos do projeto.

Instale as dependências com o comando:

```bash
pip install -r requirements.txt
```

### 2. Gerar o `docker-compose.yml`
O arquivo `docker-compose.yml` será gerado automaticamente ao rodar o script `gerar.py`. Execute o script com o comando:

```bash
python gerar.py
```

Este comando irá:
- Criar um grafo conectado com 4 roteadores e 2 hosts por roteador.
- Gerar o arquivo `docker-compose.yml`.
- Criar a visualização gráfica da topologia da rede e salvar a imagem como `Topologia_rede.png`.

### 3. Subir os Containers com Docker Compose
Depois de gerar o arquivo `docker-compose.yml`, use o Docker Compose para inicializar os containers de roteadores e hosts:

```bash
docker-compose up --build
```

Este comando irá:
- Criar e iniciar os containers para os roteadores e hosts.
- Configurar automaticamente as redes e sub-redes.
- Conectar os roteadores com links ponto a ponto.

### 4. Acessando os Containers
Após os containers estarem em funcionamento, você pode acessar os containers utilizando os seguintes comandos:

Para acessar o container do roteador:
```bash
docker exec -it <nome_do_container> bash
```

Para acessar o container do host:
```bash
docker exec -it <nome_do_container_host> bash
```

### 5. Visualização da Topologia
O script gera uma imagem representando a topologia da rede. Ela é salva como `Topologia_rede.png` na pasta do projeto. Use um visualizador de imagens para abrir e inspecionar a topologia gerada.

## Arquivo `docker-compose.yml`
O arquivo `docker-compose.yml` gerado terá a estrutura necessária para configurar todos os roteadores e hosts. Ele será estruturado para incluir:
- Roteadores configurados com diferentes sub-redes.
- Hosts com redes privadas específicas conectadas a cada roteador.
- Conexões ponto a ponto entre os roteadores.
