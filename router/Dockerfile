FROM python:3.10-slim-bullseye

RUN apt-get update && apt-get install -y \
  iproute2 \
  iputils-ping \
  net-tools \
  nano \
  tcpdump \
  traceroute \
  && rm -rf /var/lib/apt/lists/*

RUN pip install psutil
RUN pip install --no-cache-dir networkx
RUN echo "net.ipv4.ip_forward=1" >> /etc/sysctl.conf

WORKDIR /app 
COPY router.py .
COPY conex_rede.csv .


CMD ["python","-u", "router.py"]