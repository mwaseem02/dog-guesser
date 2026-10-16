import requests
from functools import lru_cache
from urllib.parse import urlparse


# URLs de l'API Dog CEO
IMAGE_URL = "https://dog.ceo/api/breeds/image/random"
BREEDS_URL = "https://dog.ceo/api/breeds/list/all"

# Temps maximal d'attente d'une requête HTTP, en secondes
TIMEOUT = 10


def format_breed_name(name: str) -> str:
    """Normalise un nom de race pour les comparaisons."""
    return name.replace("_", " ").lower()


def display_breed_name(name: str) -> str:
    """Formate un nom de race pour l'affichage."""
    return name.replace("_", " ").title()


@lru_cache(maxsize=1)
def get_breeds() -> dict[str, list[str]]:
    """Récupère la liste des races et la conserve en mémoire."""

    response = requests.get(BREEDS_URL, timeout=TIMEOUT)
    response.raise_for_status()

    data = response.json()

    if not isinstance(data, dict) or data.get("status") != "success":
        raise ValueError("Impossible de récupérer la liste des races.")

    breeds = data.get("message")

    if not isinstance(breeds, dict):
        raise ValueError("Format de réponse des races invalide.")

    return breeds


def get_breed_from_url(
    image_url: str,
    breeds: dict[str, list[str]],
) -> str:
    """Retrouve le nom de la race à partir de l'URL de l'image."""

    # On extrait le chemin de l'URL.
    path = urlparse(image_url).path
    parts = path.split("/")

    # Le dossier de la race se trouve après le segment "breeds".
    try:
        breeds_index = parts.index("breeds")
        breed_folder = parts[breeds_index + 1]
    except (ValueError, IndexError):
        raise ValueError("Format d'URL d'image invalide.") from None

    # Cas 1 : race principale, sans sous-race.
    if breed_folder in breeds:
        return format_breed_name(breed_folder)

    # Cas 2 : sous-race, au format "race-sousrace".
    for breed, sub_breeds in breeds.items():
        for sub_breed in sub_breeds:
            if breed_folder == f"{breed}-{sub_breed}":
                return format_breed_name(f"{sub_breed} {breed}")

    raise ValueError(f"Race introuvable pour : {breed_folder}")


def get_random_dog() -> tuple[str, str]:
    """Retourne l'URL d'une image aléatoire et le nom de sa race."""

    response = requests.get(IMAGE_URL, timeout=TIMEOUT)
    response.raise_for_status()

    data = response.json()

    if not isinstance(data, dict) or data.get("status") != "success":
        raise ValueError("Impossible de récupérer une image.")

    image_url = data.get("message")

    if not isinstance(image_url, str):
        raise ValueError("L'URL de l'image est invalide.")

    # On utilise la liste des races mise en cache.
    breeds = get_breeds()
    breed = get_breed_from_url(image_url, breeds)

    return image_url, breed
