# Project FORESIGHT — single image, used by BOTH Render services (see render.yaml).

FROM python:3.11-slim

# libgomp1 is required by lightgbm at import time (OpenMP runtime) — without it,
# `import lightgbm` crashes on a slim base image with a missing shared library error.
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first (separate layer) so Docker can cache this step and skip
# re-installing everything when only your .py files change, not requirements.txt.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the rest of the project (respects .dockerignore below).
COPY . .

# Render sets $PORT at runtime; it is not known at build time, so no EXPOSE/CMD here
# hardcodes a port — render.yaml's startCommand uses $PORT directly for each service.
