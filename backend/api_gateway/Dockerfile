FROM python:3.12-slim AS base
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# Security: non-root user
RUN addgroup --system idintel && adduser --system --group idintel

FROM base AS builder
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM base AS production
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
COPY . .
RUN chown -R idintel:idintel /app
USER idintel
EXPOSE 8000
CMD ["uvicorn", "api_gateway.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4", "--proxy-headers"]

FROM base AS development
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "api_gateway.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
