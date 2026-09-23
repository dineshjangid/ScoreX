# Build context is the repo root (needs both engine/ and api/).
FROM python:3.11-slim

WORKDIR /app

# libxml2/libxmlsec1 are needed by the `xmlsec` package (a python3-saml
# dependency) whether or not a prebuilt wheel is available for this
# platform — it's a C extension that links against them at runtime either
# way. build-essential/pkg-config/*-dev only matter if pip has to compile
# from source; harmless to keep installed for a small internal-tool image.
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential pkg-config \
      libxml2-dev libxmlsec1-dev libxmlsec1-openssl \
    && rm -rf /var/lib/apt/lists/*

COPY engine/ /app/engine/
COPY api/ /app/api/

RUN pip install --no-cache-dir /app/engine /app/api

ENV CREDITTOOL_DATA_DIR=/data
RUN mkdir -p /data
VOLUME ["/data"]

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--app-dir", "/app/api", "--host", "0.0.0.0", "--port", "8000"]
