FROM python:3.9-slim

# Installation des dépendances système
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Définir le répertoire de travail
WORKDIR /app

# Copier les fichiers de requirements d'abord pour le cache
COPY requirements.txt .

# Installation des dépendances Python
RUN pip install --no-cache-dir -r requirements.txt

# Installation de Spleeter (modèle de séparation audio)
RUN pip install spleeter

# Pré-télécharger le modèle Spleeter (2 stems) pour éviter le téléchargement au runtime
RUN python -c "import spleeter; from spleeter.separator import Separator; Separator('spleeter:2stems')"

# Copier tous les fichiers de l'application
COPY . .

# Créer les dossiers nécessaires
RUN mkdir -p /tmp/uploads /tmp/separated

# Exposer le port 10000 comme demandé
EXPOSE 10000

# Variables d'environnement
ENV PYTHONUNBUFFERED=1
ENV PORT=10000

# Commande de démarrage
CMD ["python", "app.py"]

