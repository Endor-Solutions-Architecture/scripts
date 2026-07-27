FROM python:3.12-slim

WORKDIR /app

# Install dependencies first so layer caching survives source edits.
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app/endor_linear_bridge/
ENV PYTHONPATH=/app
ENV BRIDGE_CONFIG=/app/config.yaml

# The state database is the only mapping from Endor notification uuid to Linear
# issue. Mount a volume here -- an ephemeral filesystem means duplicate tickets
# after any restart.
VOLUME ["/data"]

EXPOSE 8080

# TLS is terminated by the ingress in front of this container.
CMD ["uvicorn", "endor_linear_bridge.app:app", "--host", "0.0.0.0", "--port", "8080"]
