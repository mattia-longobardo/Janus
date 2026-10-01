FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl libpcap0.8 libcap2-bin nmap ieee-data \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && cp "$(readlink -f /usr/local/bin/python3.12)" /usr/local/bin/janus-sniff \
    && setcap cap_net_raw+ep /usr/local/bin/janus-sniff
COPY backend/ .
COPY entrypoint.sh /app/entrypoint.sh

ENV PYTHONPATH=/app/backend PYTHONUNBUFFERED=1
USER 1000:1000
EXPOSE 8000
ENTRYPOINT ["sh", "/app/entrypoint.sh"]
CMD ["api"]
