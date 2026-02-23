# Dockerfile para Polymarket FastLoop Trader
# ==========================================

FROM python:3.11-slim

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    gcc \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar requirements primero para cachear dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY . .

# Crear directorio de datos
RUN mkdir -p /app/data

# Puerto para health checks (opcional)
EXPOSE 8080

# Comando por defecto (puede ser sobrescrito en Railway)
CMD ["python", "main.py", "--live"]
