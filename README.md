🐕 Dog Guesser

Dog Guesser est un jeu inspiré de GeoGuessr dans lequel le joueur doit reconnaître la race d'un chien à partir d'une image.

Fonctionnalités
Images aléatoires grâce à l'API Dog CEO.
4 propositions de races par question.
10 questions par partie et 15 secondes par question.
100 points par bonne réponse et 50 points de bonus toutes les 3 bonnes réponses consécutives.
Sauvegarde du record personnel dans un fichier JSON.
Classement global des 10 meilleurs scores.
Mise à jour du record global en temps réel grâce aux WebSockets.
Installation

Python 3.10 ou supérieur est recommandé.

git clone <URL_DU_DEPOT_GITHUB>
cd dog-guesser

python3 -m venv .venv
source .venv/bin/activate

python -m pip install -r requirements.txt

Lancement

Ouvrir un premier terminal dans le dossier du projet et lancer le serveur :

python -m uvicorn server:app --host 127.0.0.1 --port 8000


Ouvrir un second terminal, activer le même environnement virtuel, puis lancer l'interface :

source .venv/bin/activate
streamlit run app.py


L'application est accessible à l'adresse indiquée par Streamlit, généralement http://localhost:8501.

Stockage

Les scores sont conservés dans le dossier data/ au format JSON. Les fichiers sont créés automatiquement lorsque nécessaire.

Technologies
Python
Streamlit
FastAPI
WebSockets
Dog CEO API
