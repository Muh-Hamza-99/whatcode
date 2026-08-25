FROM node:20-slim

# --- system deps: git, gh CLI, python3, curl ---
RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl ca-certificates gnupg python3 python3-pip python3-venv \
    && mkdir -p -m 755 /etc/apt/keyrings \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
        -o /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
        > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y --no-install-recommends gh \
    && rm -rf /var/lib/apt/lists/*

# --- Claude Code CLI ---
RUN npm install -g @anthropic-ai/claude-code

# --- Python deps, in a venv to keep the system Python clean ---
WORKDIR /app
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY run.py .

RUN useradd -m -s /bin/bash job
ENV HOME=/home/job

RUN chown -R job:job /app /opt/venv /home/job
USER job

# ANTHROPIC_API_KEY (injected via Secret Manager at deploy time) is picked
# up automatically by the `claude` CLI for non-interactive auth.
CMD ["python3", "run.py"]
