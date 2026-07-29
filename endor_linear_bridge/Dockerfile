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

# Run as a non-root user: the container's environment holds the Linear API key
# and every team's HMAC secret. /data is chowned so the SQLite file (and its
# WAL/SHM siblings) remain writable by that user once the volume is mounted --
# a bind mount inherits the host directory's ownership, so this matters most
# for a named volume, which Docker initializes from the image's copy.
RUN useradd --create-home --uid 10001 bridge \
    && mkdir -p /data \
    && chown -R bridge:bridge /data /app
USER bridge

EXPOSE 8080

# TLS is terminated by the ingress in front of this container.
CMD ["uvicorn", "endor_linear_bridge.app:app", "--host", "0.0.0.0", "--port", "8080"]
