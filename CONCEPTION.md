Conception — Dog Guesser
Architecture
Le projet est séparé en deux applications Python :

Client (app.py) : interface Streamlit, affichage des chiens, gestion des réponses, chronomètre et calcul du score.
Serveur (server.py) : API FastAPI, sauvegarde des records globaux et classement dans des fichiers JSON.
dog_api.py : récupération des images et identification des races via l'API Dog CEO.
storage.py : sauvegarde du record personnel.
websocket_client.py : réception des notifications de nouveaux records.
Choix techniques
Streamlit : créer rapidement une interface interactive, entièrement pilotée en Python.
FastAPI : exposer des routes HTTP pour consulter et enregistrer les scores.
WebSocket : diffuser les nouveaux records aux joueurs connectés sans recharger manuellement la page.
JSON : conserver les scores sans ajouter de base de données, adaptée à la taille actuelle du projet.
Dog CEO API : obtenir des images aléatoires et retrouver la race grâce au chemin de l'image.
Règles du jeu
Une partie comporte 10 questions, avec 15 secondes par question et 4 propositions de races.

Bonne réponse : 100 points.
Trois bonnes réponses consécutives : bonus de 50 points.
Record personnel : sauvegardé localement.
Records globaux : classement des 10 meilleurs joueurs et record all-time sauvegardés côté serveur.
Le joueur utilise un pseudo, sans création de compte.

Difficultés rencontrées
Chargement des images : les requêtes vers Dog CEO peuvent échouer temporairement, notamment en cas de problème DNS. Des délais d'attente et une gestion des erreurs permettent d'éviter de bloquer indéfiniment le jeu.
Chronomètre : son démarrage doit être lié au chargement de l'image pour que le joueur dispose bien du temps prévu.
Streamlit et WebSocket : l'écoute des notifications s'effectue dans un thread séparé, avec une file de messages pour transmettre les nouveaux records à l'interface.
Persistance : les scores sont enregistrés dans des fichiers JSON distincts pour séparer les données personnelles des données globales.
Limites
Le jeu dépend de la disponibilité de l'API Dog CEO et du serveur FastAPI. Les fichiers JSON conviennent à ce projet, mais une base de données et une gestion des écritures concurrentes seraient préférables pour une utilisation à plus grande échelle.
