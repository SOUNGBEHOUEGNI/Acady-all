#!/usr/bin/env bash
# Arrêter le script en cas d'erreur
set -o errexit

# 1. Mise à jour de pip et installation des dépendances
echo "--- Installation des dépendances ---"
pip install --upgrade pip
pip install -r requirements.txt

# 2. Collecte des fichiers statiques (CSS, JS, Images)
# Nécessite WhiteNoise configuré dans settings.py
echo "--- Collecte des fichiers statiques ---"
python manage.py collectstatic --no-input

# 3. Application des migrations de la base de données
echo "--- Migration de la base de données ---"
python manage.py migrate

# 4. (Optionnel) Création d'un superutilisateur automatique
# Utile si vous n'avez pas encore accès à l'admin sur Render
# if [[ $CREATE_SUPERUSER ]]; then
#   python manage.py createsuperuser --no-input
# fi

echo "--- Build terminé avec succès ! ---"