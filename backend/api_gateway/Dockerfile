FROM python:3.12-slim AS base
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

FROM base AS builder
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
# Install into /install prefix so the non-root production user can reach them
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM base AS production
# Non-root system user
RUN addgroup --system --gid 1001 idintel \
    && adduser --system --uid 1001 --gid 1001 --no-create-home idintel

# Copy installed packages from builder into the global site-packages
COPY --from=builder /install /usr/local

COPY . .
RUN chown -R idintel:idintel /app
USER idintel

EXPOSE 8000
CMD ["uvicorn", "api_gateway.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "4", "--proxy-headers"]

FROM base AS development
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "api_gateway.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
