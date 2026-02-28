FROM python:3.9-slim

# Installation des dépendances système
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copier et installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier l'application
COPY . .

# Créer les dossiers nécessaires
RUN mkdir -p /tmp/uploads /tmp/separated

# Port 10000 comme demandé
EXPOSE 10000

ENV PYTHONUNBUFFERED=1
ENV PORT=10000

CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--workers", "1", "--timeout", "300", "app:app"]
