import random
import time

import queue
import threading

from websocket_client import listen_for_records

import requests
import streamlit as st

from dog_api import (
    display_breed_name,
    format_breed_name,
    get_breeds,
    get_random_dog,
)
from storage import load_personal_record, save_personal_record


# --------------------------------------------------
# CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Dog Guesser",
    page_icon="🐕",
    layout="centered",
)

TIME_LIMIT = 15
TOTAL_QUESTIONS = 10

# Streamlit et FastAPI tournent sur la même machine Debian.
API_URL = "http://127.0.0.1:8000"

@st.cache_data(ttl=3600)
def download_dog_image(image_url: str) -> bytes:
    """Télécharge une image et garde son contenu en cache."""
    response = requests.get(image_url, timeout=20)
    response.raise_for_status()

    if not response.content:
        raise ValueError("L'image téléchargée est vide.")

    return response.content


# --------------------------------------------------
# API HTTP : RECORD GLOBAL
# --------------------------------------------------

def get_global_record() -> dict:
    """Récupère le record global depuis FastAPI."""

    response = requests.get(
        f"{API_URL}/record",
        timeout=5,
    )
    response.raise_for_status()

    data = response.json()

    return {
        "pseudo": data.get("pseudo"),
        "score": data["score"],
    }


def submit_global_score(pseudo: str, score: int) -> dict:
    """Envoie un score au serveur pour tenter de battre le record."""

    response = requests.post(
        f"{API_URL}/record",
        json={
            "pseudo": pseudo,
            "score": score,
        },
        timeout=5,
    )
    response.raise_for_status()

    return response.json()


def get_leaderboard() -> list:
    """Récupère les dix meilleurs joueurs."""

    response = requests.get(
        f"{API_URL}/leaderboard",
        timeout=5,
    )
    response.raise_for_status()

    return response.json()["leaderboard"]


# --------------------------------------------------
# CRÉATION DES QUESTIONS
# --------------------------------------------------

def create_question() -> dict:
    """Prépare un chien et quatre propositions de réponse."""

    image_url, correct_breed = get_random_dog()
    breeds = get_breeds()

    all_breeds = []

    for breed, sub_breeds in breeds.items():
        all_breeds.append(format_breed_name(breed))

        for sub_breed in sub_breeds:
            all_breeds.append(
                format_breed_name(f"{sub_breed} {breed}")
            )

    # Supprime les doublons tout en conservant l'ordre.
    all_breeds = list(dict.fromkeys(all_breeds))
    correct_breed = format_breed_name(correct_breed)

    wrong_breeds = [
        breed
        for breed in all_breeds
        if breed != correct_breed
    ]

    if len(wrong_breeds) < 3:
        raise ValueError(
            "Pas assez de races pour créer une question."
        )

    choices = random.sample(wrong_breeds, 3)
    choices.append(correct_breed)
    random.shuffle(choices)

    return {
        "image_url": image_url,
        "correct_breed": correct_breed,
        "choices": choices,
        "answered": False,
        "selected": None,
        "timed_out": False,
        "started_at": None,
    }


# --------------------------------------------------
# RECORD PERSONNEL
# --------------------------------------------------

def update_personal_record() -> None:
    """Sauvegarde le record personnel si le score augmente."""

    if st.session_state.score > st.session_state.personal_record:
        st.session_state.personal_record = st.session_state.score

        try:
            save_personal_record(st.session_state.score)
        except OSError as error:
            print(f"Erreur de sauvegarde du record personnel : {error}")


# --------------------------------------------------
# GESTION DES RÉPONSES
# --------------------------------------------------

def submit_answer(breed: str) -> None:
    """Enregistre une réponse et met à jour le score."""

    question = st.session_state.question

    if question is None or question["answered"]:
        return

    elapsed = time.monotonic() - question["started_at"]

    # Empêche de valider une réponse après expiration du délai.
    if elapsed >= TIME_LIMIT:
        question["answered"] = True
        question["timed_out"] = True
        st.session_state.streak = 0
        st.session_state.bonus_earned = False
        return

    question["selected"] = breed
    question["answered"] = True

    if breed == question["correct_breed"]:
        st.session_state.score += 100
        st.session_state.correct_answers += 1
        st.session_state.streak += 1

        # Bonus toutes les trois bonnes réponses consécutives.
        if st.session_state.streak % 3 == 0:
            st.session_state.score += 50
            st.session_state.bonus_earned = True
        else:
            st.session_state.bonus_earned = False

        update_personal_record()

    else:
        st.session_state.streak = 0
        st.session_state.bonus_earned = False


# --------------------------------------------------
# GESTION DE LA PARTIE
# --------------------------------------------------

def next_question() -> None:
    """Charge une nouvelle question."""

    try:
        st.session_state.question = create_question()
        st.session_state.error = None

    except (
        requests.RequestException,
        ValueError,
        KeyError,
    ) as error:
        print(f"Erreur lors du chargement du chien : {error}")

        st.session_state.question = None
        st.session_state.error = (
            "Impossible de récupérer un chien. "
            "Vérifie ta connexion et réessaie."
        )


def start_game() -> None:
    """Initialise une nouvelle partie."""

    st.session_state.score = 0
    st.session_state.streak = 0
    st.session_state.correct_answers = 0
    st.session_state.question_number = 1
    st.session_state.bonus_earned = False
    st.session_state.game_over = False
    st.session_state.error = None
    st.session_state.question = None

    # Permet de soumettre le score une seule fois par partie.
    st.session_state.score_submitted = False
    st.session_state.submission_message = None

    next_question()


def advance_game() -> None:
    """Passe à la question suivante ou termine la partie."""

    if st.session_state.question_number >= TOTAL_QUESTIONS:
        st.session_state.game_over = True
        st.session_state.question = None
        return

    st.session_state.question_number += 1
    next_question()


# --------------------------------------------------
# ÉCOUTE DES NOUVEAUX RECORDS
# --------------------------------------------------

if "record_queue" not in st.session_state:
    st.session_state.record_queue = queue.Queue()

    listener = threading.Thread(
        target=listen_for_records,
        args=(st.session_state.record_queue,),
        daemon=True,
    )
    listener.start()


@st.fragment(run_every="1s")
def sync_global_record():
    """Actualise le record dès qu'une notification arrive."""

    updated = False
    messages = st.session_state.record_queue

    while True:
        try:
            message = messages.get_nowait()
        except queue.Empty:
            break

        if message["score"] > st.session_state.global_record["score"]:
            st.session_state.global_record = {
                "pseudo": message["pseudo"],
                "score": message["score"],
            }
            st.session_state.global_record_error = None
            updated = True


# --------------------------------------------------
# CONNEXION WEBSOCKET
# --------------------------------------------------

if "record_queue" not in st.session_state:
    st.session_state.record_queue = queue.Queue()

    listener = threading.Thread(
        target=listen_for_records,
        args=(st.session_state.record_queue,),
        daemon=True,
    )
    listener.start()


# --------------------------------------------------
# INITIALISATION DE LA SESSION
# --------------------------------------------------

if "game_over" not in st.session_state:
    st.session_state.personal_record = load_personal_record()

    try:
        st.session_state.global_record = get_global_record()
        st.session_state.global_record_error = None
    except (
        requests.RequestException,
        ValueError,
        KeyError,
    ) as error:
        print(f"Erreur de récupération du record global : {error}")

        st.session_state.global_record = {
            "pseudo": None,
            "score": 0,
        }
        st.session_state.global_record_error = (
            "Serveur des records indisponible."
        )

    start_game()

sync_global_record()


# --------------------------------------------------
# EN-TÊTE ET STATISTIQUES
# --------------------------------------------------

st.title("🐕 Dog Guesser")
st.caption(
    "10 chiens, 15 secondes par question. "
    "Reconnais les races avant la fin du chrono !"
)

col1, col2, col3, col4 = st.columns(4)

col1.metric("Score", st.session_state.score)

col2.metric(
    "Record personnel",
    st.session_state.personal_record,
)

col3.metric(
    "Record global",
    st.session_state.global_record["score"],
)

col4.metric(
    "Série",
    st.session_state.streak,
)

if st.session_state.global_record_error:
    st.caption(st.session_state.global_record_error)
else:
    global_pseudo = st.session_state.global_record["pseudo"]

    if global_pseudo:
        st.caption(f"🏆 Record global détenu par {global_pseudo}")

st.divider()


# --------------------------------------------------
# ÉCRAN DE FIN
# --------------------------------------------------

if st.session_state.game_over:

    st.title("🏆 Partie terminée !")

    score = st.session_state.score
    correct = st.session_state.correct_answers
    accuracy = correct / TOTAL_QUESTIONS * 100

    st.subheader(f"Tu as obtenu {score} points !")

    st.progress(correct / TOTAL_QUESTIONS)

    col1, col2 = st.columns(2)

    col1.metric(
        "Bonnes réponses",
        f"{correct}/{TOTAL_QUESTIONS}",
    )

    col2.metric(
        "Précision",
        f"{accuracy:.0f} %",
    )

    # Message adapté aux performances.
    if correct == TOTAL_QUESTIONS:
        st.success(
            "🐕 Incroyable ! Sans-faute : tu es un véritable "
            "expert en races canines !"
        )
    elif correct >= 8:
        st.success(
            "🎉 Excellent résultat ! Tu connais vraiment "
            "bien les races de chiens."
        )
    elif correct >= 5:
        st.info(
            "👏 Bien joué ! Tu as de bonnes connaissances, "
            "mais tu peux encore progresser."
        )
    else:
        st.warning(
            "🐾 Continue à t'entraîner ! Chaque partie est "
            "une occasion d'apprendre de nouvelles races."
        )

    # Résumé du record personnel.
    if score >= st.session_state.personal_record:
        st.success(
            f"🏆 Tu as égalé ou battu ton record personnel : "
            f"{st.session_state.personal_record} points !"
        )

    # --------------------------------------------------
    # ENVOI DU SCORE AU SERVEUR GLOBAL
    # --------------------------------------------------

    st.divider()
    st.subheader("🌍 Record global")

    if st.session_state.global_record_error:
        st.warning(
            "Le serveur des records était indisponible. "
            "Tu peux réessayer ci-dessous."
        )

    if not st.session_state.score_submitted:

        with st.form("global_record_form"):
            pseudo = st.text_input(
                "Ton pseudo",
                max_chars=20,
                placeholder="Ex. PixelDog",
            )

            submitted = st.form_submit_button(
                "Envoyer mon score",
                width="stretch",
            )

        if submitted:
            pseudo = pseudo.strip()

            if not pseudo:
                st.warning(
                    "Choisis un pseudo avant d'envoyer ton score."
                )

            else:
                try:
                    result = submit_global_score(pseudo, score)

                    # Récupère le record actuel auprès du serveur.
                    st.session_state.global_record = get_global_record()
                    st.session_state.global_record_error = None
                    st.session_state.score_submitted = True

                    if result["record_beaten"]:
                        st.session_state.submission_message = (
                            "success",
                            f"🏆 Nouveau record global : "
                            f"{result['score']} points par "
                            f"{result['pseudo']} !",
                        )
                    else:
                        st.session_state.submission_message = (
                            "info",
                            f"Score envoyé ! Le record global reste à "
                            f"{result['score']} points.",
                        )

                    st.rerun()

                except (
                    requests.RequestException,
                    ValueError,
                    KeyError,
                ) as error:
                    print(f"Erreur lors de l'envoi du score : {error}")

                    st.error(
                        "Impossible de contacter le serveur. "
                        "Vérifie qu'il fonctionne, puis réessaie."
                    )

    # Affiche le résultat de l'envoi après la réexécution.
    if st.session_state.submission_message:
        message_type, message = st.session_state.submission_message

        if message_type == "success":
            st.success(message)
            st.balloons()
        else:
            st.info(message)

    # Actualisation manuelle du record global.
    if st.button("🔄 Actualiser le record global"):
        try:
            st.session_state.global_record = get_global_record()
            st.session_state.global_record_error = None
            st.rerun()
        except (
            requests.RequestException,
            ValueError,
            KeyError,
        ):
            st.session_state.global_record_error = (
                "Impossible de récupérer le record global."
            )
            st.error(st.session_state.global_record_error)

    # Nouvelle partie.
    if st.button("🎮 Rejouer", width="stretch"):
        start_game()
        st.rerun()


    # CLASSEMENT GLOBAL
    st.divider()
    st.subheader("🏆 Top 10 des joueurs")

    try:
        leaderboard = get_leaderboard()

        if leaderboard:
            for index, player in enumerate(leaderboard, start=1):
                st.write(
                    f"**{index}. {player['pseudo']}** — "
                    f"{player['score']} points"
                )
        else:
            st.info("Le classement est encore vide.")

    except requests.RequestException:
        st.warning(
            "Impossible de charger le classement pour le moment."
        )



# --------------------------------------------------
# ERREUR DE CHARGEMENT
# --------------------------------------------------

elif st.session_state.error:

    st.error(st.session_state.error)

    if st.button("Réessayer", width="stretch"):
        next_question()
        st.rerun()


# --------------------------------------------------
# QUESTION EN COURS ET CHRONOMÈTRE
# --------------------------------------------------

elif st.session_state.question is not None:

    @st.fragment(run_every="1s")
    def render_question():
        question = st.session_state.question

        if question is None:
            return

        # Télécharger l'image avant de démarrer le chronomètre.
        try:
            image = download_dog_image(question["image_url"])
        except (requests.RequestException, ValueError):
            st.error("Impossible de charger l'image de ce chien.")

            if st.button("Passer à un autre chien"):
                next_question()
                st.rerun()

            return

        # Le chronomètre démarre après le chargement de l'image.
        if question["started_at"] is None:
            question["started_at"] = time.monotonic()


        elapsed = time.monotonic() - question["started_at"]
        remaining = max(0, TIME_LIMIT - int(elapsed))

        # Expiration du temps.
        if not question["answered"] and elapsed >= TIME_LIMIT:
            question["answered"] = True
            question["timed_out"] = True
            st.session_state.streak = 0
            st.session_state.bonus_earned = False

            # Met à jour les statistiques hors du fragment.
            st.rerun()

        st.subheader(
            f"Question {st.session_state.question_number}"
            f" / {TOTAL_QUESTIONS}"
        )

        st.progress(
            st.session_state.question_number / TOTAL_QUESTIONS
        )

        if not question["answered"]:
            st.subheader(f"⏱️ Temps restant : {remaining} s")
            st.progress(
                max(0.0, min(1.0, remaining / TIME_LIMIT))
            )

        st.image(image, width="stretch")

        st.write("Quelle est la race de ce chien ?")

        for index, breed in enumerate(question["choices"]):
            if st.button(
                display_breed_name(breed),
                key=f"answer_{st.session_state.question_number}_{index}",
                width="stretch",
                disabled=question["answered"],
            ):
                submit_answer(breed)
                st.rerun()

        # Résultat de la question.
        if question["answered"]:

            if question["timed_out"]:
                st.warning(
                    "⏰ Temps écoulé ! La série est interrompue."
                )

            elif question["selected"] == question["correct_breed"]:
                st.success("🎉 Bonne réponse !")

                if st.session_state.bonus_earned:
                    st.balloons()
                    st.success("🔥 Bonus de série : +50 points !")

                    # Empêche de relancer les ballons chaque seconde.
                    st.session_state.bonus_earned = False

            else:
                st.error("❌ Mauvaise réponse.")

            st.info(
                "La bonne réponse était : "
                f"**{display_breed_name(question['correct_breed'])}**"
            )

            if st.button(
                "➡️ Question suivante",
                key=f"next_{st.session_state.question_number}",
                width="stretch",
            ):
                advance_game()
                st.rerun()

    render_question()
