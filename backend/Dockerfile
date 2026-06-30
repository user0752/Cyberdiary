# ---- P2-1: multi-stage build, smaller final image, non-root user ----

# Stage 1: builder — install deps into a venv we can copy verbatim
FROM python:3.13-slim AS builder

WORKDIR /app

# Build deps for any wheels that need compilation (cryptography, etc.)
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Stage 2: runtime — only the venv + app code, no compiler toolchain
FROM python:3.13-slim AS runtime

# Run as a non-root user so a container escape cannot write to the host as root.
RUN groupadd --system --gid 1001 app \
    && useradd --system --uid 1001 --gid app --create-home --home-dir /home/app app

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY . .

# Wiki markdown files are written here at runtime — chown so the non-root
# user can create and modify them.
RUN mkdir -p data/wiki \
    && chown -R app:app /app

USER app

EXPOSE 8000

# Single worker is intentional for the 4c/4G target + SQLite. See audit
# report P1-3 for the rationale on not scaling workers yet.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
