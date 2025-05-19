FROM debian:bookworm-slim

RUN apt-get update && apt-get install -y \
  iproute2 \
  iputils-ping \
  net-tools \
  nano \
  curl \
  traceroute \
  && rm -rf /var/lib/apt/lists/*

COPY host.sh /host.sh 

RUN chmod +x /host.sh  

# Comando para executar o script Python ao iniciar o container
CMD ["./host.sh"]
