FROM python:3.11-slim

WORKDIR /app

# Dependencias del sistema para crawl4ai (Playwright) y pdfplumber
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Instalar browsers de Playwright para crawl4ai
RUN playwright install chromium --with-deps

# Copiar código
COPY . .

# Puerto que expone Render
EXPOSE 8000

# Comando de arranque
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
