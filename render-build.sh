#!/usr/bin/env bash
set -o errexit

echo "--- Installation de CMake (requis pour dlib) ---"
# Cette étape est parfois nécessaire selon le runtime de Render
pip install cmake 

echo "--- Installation des dépendances ---"
pip install -r requirements.txt

echo "--- Collecte des fichiers statiques ---"
python manage.py collectstatic --no-input

echo "--- Migration de la base de données ---"
python manage.py migrate