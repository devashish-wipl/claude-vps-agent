FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1

# System deps: ssh client (Linux targets), sshpass (password auth), curl + node (for Claude Code CLI auth)
RUN apt-get update && apt-get install -y --no-install-recommends \
        openssh-client \
        sshpass \
        ca-certificates \
        curl \
        gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Claude Code CLI — used by the Agent SDK for subscription auth (`claude login`)
RUN npm install -g @anthropic-ai/claude-code

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY agent ./agent
COPY main.py .

# inventory + playbooks dirs are mounted at runtime via docker-compose
RUN mkdir -p /app/inventory /app/playbooks/generated

ENTRYPOINT ["python", "main.py"]
