# ─── Build stage ───
FROM python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir --prefix=/install .

# ─── Runtime stage ───
FROM python:3.12-slim

LABEL maintainer="TermMind Contributors"
LABEL description="TermMind — AI terminal assistant"
LABEL org.opencontainers.image.source="https://github.com/rudra496/termmind"

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Create non-root user
RUN groupadd -r termmind && useradd -r -g termmind -d /home/termmind -s /bin/bash termmind \
    && mkdir -p /home/termmind/.termmind && chown -R termmind:termmind /home/termmind

# Install shell completions
RUN mkdir -p /home/termmind/.termmind/completions

WORKDIR /workspace

# Copy application
COPY termmind/ /usr/local/lib/python3.12/site-packages/termmind/

# Generate completions at build time
RUN python -c "from termmind.shell import generate_all_completions; generate_all_completions('/home/termmind/.termmind/completions')"

# Set ownership
RUN chown -R termmind:termmind /workspace /home/termmind

USER termmind
ENV HOME=/home/termmind
ENV PATH="/usr/local/bin:${PATH}"

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import termmind; print('ok')" || exit 1

ENTRYPOINT ["termmind"]
CMD ["--help"]
